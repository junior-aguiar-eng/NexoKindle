"""Extração local de EPUB e adaptação para KindleUnpack sem DRM."""

import os
import shutil
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path, PurePosixPath

from .detect import detect_book
from .model import UnpackedBook

MAX_EXTRACTED_BYTES = 1024**3
MAX_ENTRIES = 10000
MAX_CONTAINER_BYTES = 1024 * 1024


class UnsafeArchiveError(ValueError):
    pass


class UnsupportedBookError(ValueError):
    pass


class ToolUnavailableError(RuntimeError):
    pass


class ExtractionError(RuntimeError):
    pass


def _safe_relative(name: str) -> Path:
    if not name or "\\" in name or name.startswith("/"):
        raise UnsafeArchiveError("Caminho inválido dentro do pacote.")
    pure = PurePosixPath(name)
    if any(part in ("", ".", "..") or ":" in part for part in pure.parts):
        raise UnsafeArchiveError("Caminho inseguro dentro do pacote.")
    return Path(*pure.parts)


def _unpack_epub(source: Path, destination: Path) -> Path:
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise UnsafeArchiveError("EPUB com entradas em excesso.")
        total_size = 0
        seen: set[str] = set()
        for entry in entries:
            relative = _safe_relative(entry.filename.rstrip("/"))
            marker = str(relative).casefold()
            if marker in seen:
                raise UnsafeArchiveError("EPUB com nomes de arquivos duplicados.")
            seen.add(marker)
            mode = entry.external_attr >> 16
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise UnsafeArchiveError("EPUB contém link simbólico.")
            total_size += entry.file_size
            if total_size > MAX_EXTRACTED_BYTES:
                raise UnsafeArchiveError("EPUB excede o limite de dados extraídos.")
        destination.mkdir(parents=True, exist_ok=False)
        for entry in entries:
            relative = _safe_relative(entry.filename.rstrip("/"))
            target = destination / relative
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as input_stream, target.open("xb") as output_stream:
                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)

    container = destination / "META-INF" / "container.xml"
    if not container.is_file() or container.stat().st_size > MAX_CONTAINER_BYTES:
        raise ExtractionError("Manifesto de contêiner EPUB ausente ou excessivo.")
    try:
        root = ET.parse(container).getroot()
    except ET.ParseError as exc:
        raise ExtractionError("Manifesto de contêiner EPUB inválido.") from exc
    rootfile = root.find(".//{*}rootfile")
    if rootfile is None or not rootfile.get("full-path"):
        raise ExtractionError("EPUB sem caminho do pacote OPF.")
    manifest = destination / _safe_relative(rootfile.attrib["full-path"])
    if not manifest.is_file():
        raise ExtractionError("Pacote OPF referenciado não existe.")
    return manifest


def _unpack_kindle(source: Path, destination: Path) -> Path:
    configured = os.environ.get("KINDLEUNPACK_SCRIPT")
    bundled = Path(__file__).resolve().parent / "_vendor" / "KindleUnpack" / "lib" / "kindleunpack.py"
    script = Path(configured).resolve() if configured else bundled
    frozen = bool(getattr(sys, "frozen", False))
    if frozen and configured:
        raise ToolUnavailableError("KINDLEUNPACK_SCRIPT não é aceito no aplicativo empacotado.")
    if not frozen and not script.is_file():
        raise ToolUnavailableError("KindleUnpack local não configurado.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ExtractionError("Diretório de extração já existe.")
    try:
        if frozen and sys.platform == "win32":
            worker = str(Path(sys.executable).with_name("KindlePDF-CLI.exe"))
        else:
            worker = sys.executable
        command = ([worker, "--internal-kindleunpack", str(source), str(destination)]
                   if frozen else [sys.executable, str(script), str(source), str(destination)])
        completed = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=180,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if frozen and sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExtractionError("Falha ao executar KindleUnpack local.") from exc
    if completed.returncode != 0:
        raise ExtractionError(f"KindleUnpack falhou com código {completed.returncode}.")
    manifests = list(destination.rglob("*.opf"))
    if not manifests:
        raise ExtractionError("KindleUnpack não produziu manifesto OPF.")
    manifests.sort(key=lambda path: ("mobi8" not in path.parts, len(path.parts)))
    return manifests[0]


def unpack_book(input_path: Path, work_dir: Path) -> UnpackedBook:
    """Extrai conteúdo compatível em uma pasta nova, preservando o original."""
    source = Path(input_path).resolve()
    detection = detect_book(source)
    if detection.status != "supported" or detection.format not in {"epub", "azw3", "mobi"}:
        raise UnsupportedBookError(detection.reason)
    destination = Path(work_dir).resolve() / "book"
    if destination.exists():
        raise ExtractionError("Diretório de extração já existe.")
    try:
        if detection.format == "epub":
            manifest = _unpack_epub(source, destination)
        else:
            manifest = _unpack_kindle(source, destination)
    except Exception:
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        raise
    return UnpackedBook(
        root=destination,
        manifest_path=manifest,
        resource_dir=manifest.parent,
        format=detection.format,
    )
