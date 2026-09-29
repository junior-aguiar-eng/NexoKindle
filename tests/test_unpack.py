import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from kindle_pdf.unpack import ExtractionError, UnsafeArchiveError, UnsupportedBookError, unpack_book
from tests.book_fixtures import CONTAINER, make_epub
from tests.test_detect import mobi_fixture


def test_unpack_epub_preserves_manifest_and_input(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub")
    before = hashlib.sha256(source.read_bytes()).hexdigest()

    unpacked = unpack_book(source, tmp_path / "work")

    assert unpacked.format == "epub"
    assert unpacked.manifest_path.name == "content.opf"
    assert unpacked.manifest_path.is_relative_to(unpacked.root)
    assert (unpacked.root / "OEBPS/Text/z-intro.xhtml").is_file()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_unpack_rejects_zip_traversal_without_writing_outside_workdir(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "escape.epub")
    with ZipFile(source, "a") as archive:
        archive.writestr("../outside.txt", "bad")

    with pytest.raises(UnsafeArchiveError):
        unpack_book(source, tmp_path / "work")

    assert not (tmp_path / "outside.txt").exists()


def test_unpack_rejects_protected_kindle_input(tmp_path: Path) -> None:
    source = tmp_path / "protected.azw"
    source.write_bytes(b"\xeaDRMION\xeeProtectedData")

    with pytest.raises(UnsupportedBookError):
        unpack_book(source, tmp_path / "work")

    assert not (tmp_path / "work" / "book").exists()


def test_unpack_invokes_local_kindleunpack_with_literal_paths(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "book & notes.mobi"
    source.write_bytes(mobi_fixture(version=8))
    tool = tmp_path / "fake-kindleunpack.py"
    tool.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "assert len(sys.argv) == 3\n"
        "assert Path(sys.argv[1]).name == 'book & notes.mobi'\n"
        "root = Path(sys.argv[2]) / 'mobi8' / 'OEBPS'\n"
        "root.mkdir(parents=True)\n"
        "(root / 'content.opf').write_text('<package/>')\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KINDLEUNPACK_SCRIPT", str(tool))

    unpacked = unpack_book(source, tmp_path / "work")

    assert unpacked.format == "azw3"
    assert unpacked.manifest_path == unpacked.root / "mobi8/OEBPS/content.opf"


def test_unpack_epub_cleans_partial_output_after_manifest_error(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub", {"META-INF/container.xml": b"<invalid"})

    with pytest.raises(ExtractionError):
        unpack_book(source, tmp_path / "work")

    assert not (tmp_path / "work/book").exists()
    make_epub(source, {"META-INF/container.xml": CONTAINER})
    assert unpack_book(source, tmp_path / "work").manifest_path.is_file()


def test_bundled_kindleunpack_is_available() -> None:
    from kindle_pdf import unpack

    script = Path(unpack.__file__).resolve().parent / "_vendor/KindleUnpack/lib/kindleunpack.py"
    license_file = script.parents[1] / "COPYING.txt"
    assert script.is_file()
    assert license_file.is_file()
