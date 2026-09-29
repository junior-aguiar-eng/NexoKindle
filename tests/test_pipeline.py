from pathlib import Path

import pymupdf

from kindle_pdf.pipeline import ConvertOptions, convert_one
from kindle_pdf.render import PrintStyle
from tests.book_fixtures import CHAPTER, INTRO, make_epub, make_text_epub


def test_convert_one_keeps_same_title_books_distinct(tmp_path: Path) -> None:
    first = make_text_epub(tmp_path / "first.epub")
    second = make_text_epub(tmp_path / "second.epub", {
        "OEBPS/Text/a-capitulo.xhtml": CHAPTER.replace(b"Corpo do capitulo.", b"Outro corpo juridico."),
    })
    output = tmp_path / "pdfs"

    a = convert_one(first, output, ConvertOptions())
    b = convert_one(second, output, ConvertOptions())

    assert a.status == b.status == "converted"
    assert a.sha256 != b.sha256
    assert a.pdf_path != b.pdf_path
    assert a.pdf_path.is_file() and b.pdf_path.is_file()
    with pymupdf.open(a.pdf_path) as pdf:
        assert "Corpo do capitulo." in " ".join(page.get_text() for page in pdf)


def test_failed_renderer_preserves_existing_pdf_and_cleans_temp(tmp_path: Path) -> None:
    source = make_text_epub(tmp_path / "livro.epub")
    output = tmp_path / "pdfs"
    output.mkdir()
    existing = output / "Livro.pdf"
    existing.write_bytes(b"existing valid output")

    def broken_renderer(book, target, style):
        target.write_bytes(b"partial")
        raise RuntimeError("simulated interruption")

    result = convert_one(source, output, ConvertOptions(renderer=broken_renderer))

    assert result.status == "failed"
    assert result.pdf_path is None
    assert existing.read_bytes() == b"existing valid output"
    assert not list(output.rglob("*.tmp.pdf"))
    assert not list(output.glob("*.pdf")) == []


def test_review_required_is_stored_outside_published_pdfs(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub", {
        "OEBPS/Text/z-intro.xhtml": INTRO.replace(b"../Images/figura.svg", b"../Images/ausente.svg"),
    })
    output = tmp_path / "pdfs"

    result = convert_one(source, output, ConvertOptions())

    assert result.status == "review_required"
    assert result.pdf_path is None
    assert result.review_path is not None and result.review_path.is_file()
    assert result.review_path.parent == output / "review"
    assert not list(output.glob("*.pdf"))


def test_protected_book_does_not_create_output(tmp_path: Path) -> None:
    source = tmp_path / "protected.azw"
    source.write_bytes(b"\xeaDRMION\xeeProtectedData")

    result = convert_one(source, tmp_path / "pdfs", ConvertOptions())

    assert result.status == "protected_or_unreadable"
    assert result.pdf_path is None
    assert not (tmp_path / "pdfs").exists()


def test_review_symlink_cannot_publish_outside_destination(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub")
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "pdfs"
    output.mkdir()
    try:
        (output / "review").symlink_to(outside, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("Criação de symlink indisponível neste Windows.")

    result = convert_one(source, output, ConvertOptions())
    assert result.status == "failed"
    assert not list(outside.iterdir())
