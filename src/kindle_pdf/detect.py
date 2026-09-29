"""Identificação conservadora por estrutura, sem extrair nem modificar livros."""

import hashlib
import os
import zipfile
from pathlib import Path
from typing import BinaryIO

from .model import Detection, DetectionStatus, DrmState

DEFAULT_MAX_SIZE_BYTES = 1024**3
HASH_CHUNK_BYTES = 1024 * 1024


def _result(
    status: DetectionStatus,
    format: str,
    drm_state: DrmState,
    size_bytes: int | None,
    sha256: str | None,
    reason: str,
) -> Detection:
    return Detection(status, format, drm_state, size_bytes, sha256, reason)


def _detect_palm(stream: BinaryIO, size: int, sha256: str, header: bytes) -> Detection:
    if len(header) < 86:
        return _result("invalid_file", "mobi", "unknown", size, sha256, "Cabeçalho Palm truncado.")
    records = int.from_bytes(header[76:78], "big")
    first_record = int.from_bytes(header[78:82], "big")
    if records < 1 or first_record < 78 + 8 * records or first_record + 40 > size:
        return _result("invalid_file", "mobi", "unknown", size, sha256, "Índice de registros Palm inválido.")
    stream.seek(first_record)
    record = stream.read(40)
    if record[16:20] != b"MOBI":
        return _result("unsupported_format", "palm_book", "unknown", size, sha256, "Registro inicial sem cabeçalho MOBI.")
    version = int.from_bytes(record[36:40], "big")
    crypto_type = int.from_bytes(record[12:14], "big")
    book_format = "azw3" if version == 8 else "mobi" if 1 <= version <= 7 else "mobi_unknown"
    if crypto_type:
        return _result("protected_or_unreadable", book_format, "protected", size, sha256, "Cabeçalho MOBI indica proteção.")
    if book_format == "mobi_unknown":
        return _result("unsupported_format", book_format, "unknown", size, sha256, "Versão MOBI não reconhecida.")
    return _result("supported", book_format, "not_detected", size, sha256, "Estrutura MOBI preliminar compatível; extração ainda não validada.")


def _detect_zip(stream: BinaryIO, size: int, sha256: str) -> Detection:
    try:
        with zipfile.ZipFile(stream) as archive:
            names = set(archive.namelist())
            if "mimetype" in names:
                mimetype_info = archive.getinfo("mimetype")
                if mimetype_info.file_size > 128:
                    return _result("invalid_file", "zip", "unknown", size, sha256, "Mimetype ZIP excessivo.")
                mimetype = archive.read("mimetype")
                if mimetype == b"application/epub+zip":
                    if "META-INF/container.xml" not in names:
                        return _result("invalid_file", "epub", "unknown", size, sha256, "EPUB sem manifesto de contêiner.")
                    if "META-INF/encryption.xml" in names:
                        return _result("protected_or_unreadable", "epub", "protected", size, sha256, "EPUB contém manifesto de criptografia.")
                    return _result("supported", "epub", "not_detected", size, sha256, "Estrutura EPUB preliminar compatível.")
            for info in archive.infolist():
                if info.filename.lower().endswith(".azw") and info.file_size >= 4:
                    with archive.open(info) as member:
                        if member.read(4) == b"CONT":
                            return _result("unsupported_format", "kfx_zip", "unknown", size, sha256, "KFX-ZIP reconhecido; adaptador do núcleo ainda não disponível.")
            return _result("unsupported_format", "zip", "unknown", size, sha256, "ZIP sem estrutura EPUB ou KFX reconhecida.")
    except (zipfile.BadZipFile, RuntimeError, EOFError, ValueError):
        return _result("invalid_file", "zip", "unknown", size, sha256, "ZIP inválido ou ilegível.")


def detect_book(path: Path, max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES) -> Detection:
    """Devolve um diagnóstico JSON-serializável sem alterar o caminho recebido."""
    path = Path(path)
    try:
        if not path.is_file():
            return _result("invalid_file", "unknown", "unknown", None, None, "Caminho ausente ou não é arquivo regular.")
        size = path.stat().st_size
        if size > max_size_bytes:
            return _result("invalid_file", "unknown", "unknown", size, None, "Arquivo acima do limite de diagnóstico.")
        digest = hashlib.sha256()
        first = b""
        bytes_read = 0
        with path.open("rb") as stream:
            initial_stat = os.fstat(stream.fileno())
            while chunk := stream.read(HASH_CHUNK_BYTES):
                if not first:
                    first = chunk[:4096]
                digest.update(chunk)
                bytes_read += len(chunk)
            sha256 = digest.hexdigest()
            if bytes_read != size:
                return _result("invalid_file", "unknown", "unknown", bytes_read, sha256, "Arquivo mudou durante a leitura.")
            if size == 0:
                result = _result("invalid_file", "unknown", "unknown", size, sha256, "Arquivo vazio.")
            elif first.startswith((b"\xeaDRMION", b"DRMION")):
                result = _result("protected_or_unreadable", "kindle_drmion", "protected", size, sha256, "Contêiner Kindle protegido; não é AZW3/MOBI direto.")
            elif first[60:68] == b"BOOKMOBI":
                result = _detect_palm(stream, size, sha256, first)
            elif first.startswith((b"PK\x03\x04", b"PK\x05\x06")):
                result = _detect_zip(stream, size, sha256)
            else:
                result = _result("unsupported_format", "unknown", "unknown", size, sha256, "Assinatura de formato não reconhecida.")
            final_stat = os.fstat(stream.fileno())
            if (initial_stat.st_size, initial_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
                return _result("invalid_file", "unknown", "unknown", final_stat.st_size, None, "Arquivo mudou durante o diagnóstico.")
            return result
    except OSError:
        return _result("invalid_file", "unknown", "unknown", None, None, "Falha de leitura do arquivo.")
