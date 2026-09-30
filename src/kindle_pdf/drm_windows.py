"""Cadeia opcional Windows: arquivador externo, KFX Input local e EPUB."""

from contextlib import contextmanager
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, ContextManager

from .detect import detect_book
from .drm import DecryptResult, DecryptStatus, SecretInput

ARCHIVER_25218_SHA256 = "a06d8946901cf962a8024e8a4c34cb9ebcd7d61b5ebd443e41d7738474096157"
MAX_BOOK_COPY_BYTES = 2 * 1024**3
MAX_KEY_CACHE_FILES = 1000
MAX_KEY_CACHE_BYTES = 64 * 1024**2
FIXED_KEY_RELATIVE = (Path("d8c37e00045ea5de98d93811f777d227040edd50")
                      / "4111704e63913bc011faadfaf420c7573b17ac83.PCPKEY")
DriveMapper = Callable[[Path], ContextManager[Path]]
CommandRunner = Callable[..., int]
if sys.platform == "win32":
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    _NO_WINDOW = 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _profile_key_cache() -> Path:
    """Usa a mesma pasta LocalAppData que o arquivador Windows consulta."""
    folder = ctypes.create_unicode_buffer(32768)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x001C, None, 0, folder) != 0:
        raise OSError("LocalAppData indisponível.")
    return Path(folder.value) / "Microsoft" / "Crypto" / "PCPKSP"


def _is_reparse_point(path: Path) -> bool:
    return bool(path.lstat().st_file_attributes & 0x400)


class _ExternalKeyCacheError(Exception):
    pass


@contextmanager
def _profile_key_copy_guard(source: Path, target: Path):
    """Permite a cópia externa apenas sem colisão e remove cópias verificadas."""
    if not source.exists():
        yield
        return
    if not source.is_dir() or _is_reparse_point(source):
        raise _ExternalKeyCacheError
    if target.exists() and (not target.is_dir() or _is_reparse_point(target)):
        raise _ExternalKeyCacheError
    files = [path for path in source.rglob("*") if path.is_file()]
    entries = list(source.rglob("*"))
    if len(files) > MAX_KEY_CACHE_FILES or any(_is_reparse_point(path) for path in entries):
        raise _ExternalKeyCacheError
    if any(not path.is_file() and not path.is_dir() for path in entries):
        raise _ExternalKeyCacheError
    if sum(path.stat().st_size for path in files) > MAX_KEY_CACHE_BYTES:
        raise _ExternalKeyCacheError
    expected = {path.relative_to(source): _sha256(path) for path in files}
    # A ferramenta também tenta gravar esse nome fixo com conteúdo vazio se a origem faltar.
    expected.setdefault(FIXED_KEY_RELATIVE, hashlib.sha256(b"").hexdigest())
    parents = {target / parent for relative in expected for parent in relative.parents if parent != Path(".")}
    parents.update(target / path.relative_to(source) for path in entries if path.is_dir())
    if any((target / relative).exists() for relative in expected):
        raise _ExternalKeyCacheError
    if any(path.exists() and (not path.is_dir() or _is_reparse_point(path)) for path in parents):
        raise _ExternalKeyCacheError
    created_directories = {path for path in parents if not path.exists()}
    target_preexisted = target.exists()
    try:
        yield
    finally:
        # Nunca remove nem altera um arquivo anterior à operação ou modificado depois da cópia.
        cleanup_failed = False
        for relative, digest in expected.items():
            copied = target / relative
            if copied.is_file() and not _is_reparse_point(copied):
                if _sha256(copied) != digest:
                    cleanup_failed = True
                else:
                    copied.unlink()
            elif copied.exists():
                cleanup_failed = True
        for folder in sorted(created_directories, key=lambda path: len(path.parts), reverse=True):
            if folder.is_dir() and not _is_reparse_point(folder) and not any(folder.iterdir()):
                folder.rmdir()
        if target.exists() and not _is_reparse_point(target):
            if not target_preexisted and not any(target.iterdir()):
                target.rmdir()
        if cleanup_failed:
            raise _ExternalKeyCacheError


def _run_silent(command: list[str], *, cwd: Path, env: dict[str, str], timeout: int) -> int:
    completed = subprocess.run(
        command, cwd=cwd, env=env, timeout=timeout, shell=False,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW if sys.platform == "win32" else 0,
        check=False,
    )
    return completed.returncode


@contextmanager
def _mapped_drive(volume: Path):
    """Isola o C:\\Data fixo da ferramenta sob uma unidade temporária SUBST."""
    if sys.platform != "win32":
        raise OSError("Adaptador disponível somente no Windows.")
    occupied = ctypes.windll.kernel32.GetLogicalDrives()
    letter = next((value for value in "RSTUVWXYZ" if not occupied & (1 << (ord(value) - 65))), None)
    if letter is None:
        raise OSError("Nenhuma letra de unidade temporária disponível.")
    subst = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "subst.exe"
    flags = subprocess.CREATE_NO_WINDOW
    mapped = subprocess.run([str(subst), f"{letter}:", str(volume)], shell=False,
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, creationflags=flags, check=False)
    if mapped.returncode != 0:
        raise OSError("Não foi possível mapear a área temporária.")
    try:
        yield Path(f"{letter}:\\")
    finally:
        unmapped = subprocess.run([str(subst), f"{letter}:", "/D"], shell=False,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, creationflags=flags, check=False)
        if unmapped.returncode != 0:
            raise OSError("Não foi possível remover o mapeamento temporário.")


class WindowsKindleAdapter:
    """Usa ferramentas externas explicitamente fornecidas, sem embuti-las no pacote."""

    def __init__(self, *, archiver_exe: Path, calibre_customize_exe: Path,
                 calibre_debug_exe: Path, kfx_input_zip: Path,
                 key_cache_path: Path | None = None, drive_mapper: DriveMapper | None = None,
                 run_command: CommandRunner | None = None,
                 archiver_sha256: str | None = ARCHIVER_25218_SHA256,
                 allow_profile_key_copy: bool = False,
                 profile_key_cache_path: Path | None = None) -> None:
        self.archiver_exe = Path(archiver_exe).resolve()
        self.calibre_customize_exe = Path(calibre_customize_exe).resolve()
        self.calibre_debug_exe = Path(calibre_debug_exe).resolve()
        self.kfx_input_zip = Path(kfx_input_zip).resolve()
        self.key_cache_path = Path(key_cache_path).resolve() if key_cache_path is not None else None
        self.drive_mapper = drive_mapper or _mapped_drive
        self.run_command = run_command or _run_silent
        self.archiver_sha256 = archiver_sha256
        self.allow_profile_key_copy = allow_profile_key_copy
        self.profile_key_cache_path = profile_key_cache_path

    def _external_key_cache(self, source: Path) -> Path | None:
        if self.key_cache_path is not None:
            return self.key_cache_path
        packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Packages"
        content = Path(source).resolve().parent.parent
        for package in packages.glob("AMZNKindle.AmazonKindleReadingApp*"):
            if content == (package / "LocalState" / "Classic" / "Content").resolve():
                return package / "LocalCache" / "Local" / "Microsoft" / "Crypto" / "PCPKSP"
        matches = list(packages.glob("AMZNKindle.AmazonKindleReadingApp*"))
        if len(matches) != 1:
            return None
        return matches[0] / "LocalCache" / "Local" / "Microsoft" / "Crypto" / "PCPKSP"

    def cache_identity(self) -> dict[str, str | None]:
        """Identifica ferramentas da conversão sem incluir cache de chaves."""
        paths = {
            "archiver": self.archiver_exe,
            "calibre_customize": self.calibre_customize_exe,
            "calibre_debug": self.calibre_debug_exe,
            "kfx_input": self.kfx_input_zip,
        }
        return {name: _sha256(path) if path.is_file() else None for name, path in paths.items()}

    def _preflight(self, source: Path) -> DecryptStatus | None:
        if sys.platform != "win32" or not source.parent.name.endswith("_EBOK"):
            return "unsupported"
        if not all(path.is_file() for path in (self.archiver_exe, self.calibre_customize_exe,
                                               self.calibre_debug_exe, self.kfx_input_zip)):
            return "unsupported"
        if self.archiver_sha256 is not None and _sha256(self.archiver_exe) != self.archiver_sha256.lower():
            return "unsupported"
        key_cache = self._external_key_cache(source)
        if key_cache is None:
            return "unsupported"
        if key_cache.exists() and not self.allow_profile_key_copy:
            # Essa versão copia essa pasta para fora da área temporária se ela existir.
            return "external_key_cache"
        return None

    @staticmethod
    def _copy_book(source: Path, books_root: Path) -> None:
        source_dir = source.parent
        entries = list(source_dir.iterdir())
        if not entries or any(not item.is_file() or item.is_symlink() for item in entries):
            raise ValueError("Pasta do livro contém entrada incompatível.")
        if sum(item.stat().st_size for item in entries) > MAX_BOOK_COPY_BYTES:
            raise ValueError("Livro excede o limite de cópia temporária.")
        target = books_root / source_dir.name
        target.mkdir(parents=True)
        for item in entries:
            shutil.copy2(item, target / item.name)

    def decrypt(self, input_path: Path, output_dir: Path, credential: SecretInput) -> DecryptResult:
        source = Path(input_path).resolve()
        preflight_failure = self._preflight(source)
        if preflight_failure is not None:
            return DecryptResult(preflight_failure)
        destination = Path(output_dir).resolve()
        try:
            destination.mkdir(parents=True, exist_ok=True)
            volume = destination / "volume"
            volume.mkdir()
            with self.drive_mapper(volume) as drive:
                books = drive / "books"
                books.mkdir()
                self._copy_book(source, books)
                archived = drive / "archived"
                archived.mkdir()
                work = drive / "work"
                work.mkdir()
                temp = drive / "temp"
                temp.mkdir()
                archiver_env = dict(os.environ, TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp))
                command = [str(self.archiver_exe), str(books), str(archived),
                           str(work / "keys.k4i"), "default", str(work / "books.keyfile")]
                key_cache = self._external_key_cache(source)
                if key_cache is None:
                    return DecryptResult("unsupported")
                profile = self.profile_key_cache_path or _profile_key_cache()
                try:
                    with _profile_key_copy_guard(key_cache, profile):
                        if self.run_command(command, cwd=work, env=archiver_env, timeout=900) != 0:
                            return DecryptResult("failed")
                except _ExternalKeyCacheError:
                    return DecryptResult("external_key_cache")
            archives = [item for item in (volume / "archived").rglob("*")
                        if item.is_file() and item.name.lower().endswith(".kfx-zip")]
            if len(archives) != 1 or detect_book(archives[0]).format != "kfx_zip":
                return DecryptResult("unsupported")
            calibre_config = destination / "calibre-config"
            calibre_cache = destination / "calibre-cache"
            calibre_temp = destination / "calibre-temp"
            for folder in (calibre_config, calibre_cache, calibre_temp):
                folder.mkdir()
            calibre_env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=str(calibre_config),
                               CALIBRE_CACHE_DIRECTORY=str(calibre_cache), CALIBRE_TEMP_DIR=str(calibre_temp),
                               TEMP=str(calibre_temp), TMP=str(calibre_temp), TMPDIR=str(calibre_temp))
            if self.run_command([str(self.calibre_customize_exe), "--add-plugin", str(self.kfx_input_zip)],
                                cwd=destination, env=calibre_env, timeout=180) != 0:
                return DecryptResult("failed")
            epub = destination / "converted.epub"
            if self.run_command([str(self.calibre_debug_exe), "-r", "KFX Input", "--",
                                 str(archives[0]), str(epub)], cwd=destination,
                                env=calibre_env, timeout=1200) != 0:
                return DecryptResult("failed")
            return DecryptResult("decrypted", epub) if detect_book(epub).status == "supported" else DecryptResult("failed")
        except Exception:
            # A ferramenta externa pode emitir tokens em erros; nenhum detalhe é propagado.
            return DecryptResult("failed")
