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
from .drm import DecryptResult, SecretInput

ARCHIVER_25218_SHA256 = "a06d8946901cf962a8024e8a4c34cb9ebcd7d61b5ebd443e41d7738474096157"
MAX_BOOK_COPY_BYTES = 2 * 1024**3
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
                 archiver_sha256: str | None = ARCHIVER_25218_SHA256) -> None:
        self.archiver_exe = Path(archiver_exe).resolve()
        self.calibre_customize_exe = Path(calibre_customize_exe).resolve()
        self.calibre_debug_exe = Path(calibre_debug_exe).resolve()
        self.kfx_input_zip = Path(kfx_input_zip).resolve()
        self.key_cache_path = Path(key_cache_path).resolve() if key_cache_path is not None else None
        self.drive_mapper = drive_mapper or _mapped_drive
        self.run_command = run_command or _run_silent
        self.archiver_sha256 = archiver_sha256

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

    def _preflight(self, source: Path) -> bool:
        if sys.platform != "win32" or not source.parent.name.endswith("_EBOK"):
            return False
        if not all(path.is_file() for path in (self.archiver_exe, self.calibre_customize_exe,
                                               self.calibre_debug_exe, self.kfx_input_zip)):
            return False
        if self.archiver_sha256 is not None and _sha256(self.archiver_exe) != self.archiver_sha256.lower():
            return False
        key_cache = self._external_key_cache(source)
        if key_cache is None or key_cache.exists():
            # Essa versão copia essa pasta para fora da área temporária se ela existir.
            return False
        return True

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
        if not self._preflight(source):
            return DecryptResult("unsupported")
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
                if self.run_command(command, cwd=work, env=archiver_env, timeout=900) != 0:
                    return DecryptResult("failed")
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
