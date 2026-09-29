import hashlib
import zipfile
from pathlib import Path

from kindle_pdf.detect import detect_book


def mobi_fixture(version: int, crypto_type: int = 0) -> bytes:
    palm = bytearray(78)
    palm[60:68] = b"BOOKMOBI"
    palm[76:78] = (1).to_bytes(2, "big")
    record_index = (86).to_bytes(4, "big") + bytes(4)
    record = bytearray(264)
    record[12:14] = crypto_type.to_bytes(2, "big")
    record[16:20] = b"MOBI"
    record[20:24] = (232).to_bytes(4, "big")
    record[36:40] = version.to_bytes(4, "big")
    return bytes(palm) + record_index + bytes(record)


def test_drmion_wins_over_misleading_extension(tmp_path: Path) -> None:
    sample = tmp_path / "livro.azw3"
    payload = b"DRMION" + b"\0" * 8 + b"ProtectedData" + b"\0" * 16
    sample.write_bytes(payload)

    result = detect_book(sample)

    assert result.status == "protected_or_unreadable"
    assert result.format == "kindle_drmion"
    assert result.drm_state == "protected"
    assert result.size_bytes == len(payload)
    assert result.sha256 == hashlib.sha256(payload).hexdigest()


def test_real_ms_kindle_prefix_is_detected_as_protected(tmp_path: Path) -> None:
    sample = tmp_path / "livro.azw"
    sample.write_bytes(b"\xeaDRMION\xee" + b"ProtectedData")

    result = detect_book(sample)

    assert result.format == "kindle_drmion"
    assert result.status == "protected_or_unreadable"


def test_unknown_content_is_not_promoted_by_azw3_extension(tmp_path: Path) -> None:
    sample = tmp_path / "livro.azw3"
    sample.write_bytes(b"not a kindle file")

    result = detect_book(sample)

    assert result.status == "unsupported_format"
    assert result.format == "unknown"
    assert result.drm_state == "unknown"


def test_palm_header_distinguishes_kf8_from_mobi(tmp_path: Path) -> None:
    sample = tmp_path / "sem-extensao"
    sample.write_bytes(mobi_fixture(version=8))
    assert detect_book(sample).format == "azw3"
    assert detect_book(sample).status == "supported"

    sample.write_bytes(mobi_fixture(version=6))
    assert detect_book(sample).format == "mobi"
    assert detect_book(sample).status == "supported"


def test_palm_drm_is_reported_as_protected(tmp_path: Path) -> None:
    sample = tmp_path / "livro.mobi"
    sample.write_bytes(mobi_fixture(version=8, crypto_type=2))

    result = detect_book(sample)

    assert result.format == "azw3"
    assert result.status == "protected_or_unreadable"
    assert result.drm_state == "protected"


def test_truncated_palm_record_is_invalid(tmp_path: Path) -> None:
    sample = tmp_path / "livro.mobi"
    sample.write_bytes(mobi_fixture(version=8)[:90])

    assert detect_book(sample).status == "invalid_file"


def test_epub_requires_internal_mimetype_and_container(tmp_path: Path) -> None:
    sample = tmp_path / "livro.bin"
    with zipfile.ZipFile(sample, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", "<container/>")

    result = detect_book(sample)

    assert result.status == "supported"
    assert result.format == "epub"
    assert result.drm_state == "not_detected"


def test_epub_with_encryption_manifest_is_not_treated_as_clear(tmp_path: Path) -> None:
    sample = tmp_path / "livro.epub"
    with zipfile.ZipFile(sample, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", "<container/>")
        archive.writestr("META-INF/encryption.xml", "<encryption/>")

    result = detect_book(sample)

    assert result.status == "protected_or_unreadable"
    assert result.drm_state == "protected"


def test_kfx_zip_is_recognized_without_claiming_core_conversion(tmp_path: Path) -> None:
    sample = tmp_path / "livro.kfx-zip"
    with zipfile.ZipFile(sample, "w") as archive:
        archive.writestr("book.azw", b"CONT" + bytes(80))
        archive.writestr("book.azw.res", b"CONT" + bytes(20))

    result = detect_book(sample)

    assert result.format == "kfx_zip"
    assert result.status == "unsupported_format"


def test_empty_missing_and_oversized_files_are_invalid(tmp_path: Path) -> None:
    empty = tmp_path / "empty.azw3"
    empty.write_bytes(b"")
    assert detect_book(empty).status == "invalid_file"
    assert detect_book(empty).sha256 == hashlib.sha256(b"").hexdigest()
    assert detect_book(tmp_path / "absent").status == "invalid_file"

    large = tmp_path / "large.azw3"
    large.write_bytes(b"DRMION" + b"x" * 50)
    result = detect_book(large, max_size_bytes=32)
    assert result.status == "invalid_file"
    assert result.sha256 is None


def test_directory_is_not_a_book(tmp_path: Path) -> None:
    assert detect_book(tmp_path).status == "invalid_file"


def test_replaced_path_does_not_pair_old_hash_with_new_header(
    tmp_path: Path, monkeypatch
) -> None:
    sample = tmp_path / "livro.mobi"
    original = mobi_fixture(version=8, crypto_type=0)
    replacement = mobi_fixture(version=8, crypto_type=2)
    sample.write_bytes(original)
    original_open = Path.open
    reads = 0

    def replace_before_second_read(path: Path, mode: str = "r", *args, **kwargs):
        nonlocal reads
        if path == sample and mode == "rb":
            reads += 1
            if reads == 2:
                sample.write_bytes(replacement)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", replace_before_second_read)
    result = detect_book(sample)

    assert result.sha256 == hashlib.sha256(original).hexdigest()
    assert result.status == "supported"
    assert result.drm_state == "not_detected"
