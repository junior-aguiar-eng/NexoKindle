import os
from pathlib import Path

import pymupdf
import pytest

from kindle_pdf.model import BookModel, Chapter
from kindle_pdf.render import PrintStyle, render_pdf
from kindle_pdf.validate import validate_pdf
from tests.print_fixtures import make_print_book


@pytest.mark.renderer
def test_validate_pdf_accepts_complete_textual_book(tmp_path: Path) -> None:
    book = make_print_book(tmp_path / "book")
    pdf = render_pdf(book, tmp_path / "book.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    report = validate_pdf(pdf, book)

    assert report.status == "valid"
    assert report.pages >= 2
    assert report.text_chars > 100
    assert report.chapters_found == len(book.chapters)
    assert report.warnings == ()


def test_validate_pdf_rejects_unreadable_or_textless_output(tmp_path: Path) -> None:
    book = make_print_book(tmp_path / "book")
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"not a pdf")
    assert validate_pdf(invalid, book).status == "invalid"

    empty = tmp_path / "empty.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(empty)
    assert validate_pdf(empty, book).status == "invalid"


@pytest.mark.renderer
def test_validate_pdf_marks_missing_note_or_image_for_review(tmp_path: Path) -> None:
    book = make_print_book(tmp_path / "book")
    pdf = render_pdf(book, tmp_path / "book.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))
    extra_note = Chapter(
        book.chapters[1].id,
        book.chapters[1].title,
        book.chapters[1].html.replace("Nota interna verificável.", "Nota que não está no PDF."),
        book.chapters[1].source_path,
    )
    expected = BookModel(book.title, book.language, (book.chapters[0], extra_note), book.resources, book.warnings)
    assert validate_pdf(pdf, expected).status == "review_required"

    expected_with_warning = BookModel(book.title, book.language, book.chapters, book.resources, ("Recurso ausente: capa.jpg",))
    assert validate_pdf(pdf, expected_with_warning).status == "review_required"


@pytest.mark.renderer
def test_validate_accepts_image_only_cover_without_visible_cover_label(tmp_path: Path) -> None:
    from tests.print_fixtures import PNG

    source = tmp_path / "cover.xhtml"
    source.write_text("", encoding="utf-8")
    image = tmp_path / "cover.png"
    image.write_bytes(PNG)
    book = BookModel(
        "Teste", "pt-BR",
        (
            Chapter("cover", "Cover", '<html><body><svg width="100" height="100"><image href="cover.png" width="100" height="100"/></svg></body></html>', source),
            Chapter("text", "Capítulo 1", '<html><body><h1>Capítulo 1</h1><p>Texto legível.</p></body></html>', source),
        ),
        (image,), (),
    )
    pdf = render_pdf(book, tmp_path / "book.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    report = validate_pdf(pdf, book)

    assert report.status == "valid"
    assert report.chapters_found == 2


@pytest.mark.renderer
def test_validate_rejects_missing_second_chapter_with_repeated_title(tmp_path: Path) -> None:
    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    first = Chapter("a", "Capítulo", '<html><body><h1>Capítulo</h1><p>Primeiro conteúdo.</p></body></html>', source)
    second = Chapter("b", "Capítulo", '<html><body><h1>Capítulo</h1><p>Segundo conteúdo.</p></body></html>', source)
    complete = BookModel("Livro", "pt-BR", (first, second), (), ())
    incomplete = BookModel("Livro", "pt-BR", (first,), (), ())
    pdf = render_pdf(incomplete, tmp_path / "incomplete.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    report = validate_pdf(pdf, complete)

    assert report.status == "invalid"
    assert report.chapters_found == 1


@pytest.mark.renderer
def test_validate_marks_second_missing_image_and_div_footnote_for_review(tmp_path: Path) -> None:
    book = make_print_book(tmp_path / "book")
    pdf = render_pdf(book, tmp_path / "book.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))
    first = Chapter(
        book.chapters[0].id, book.chapters[0].title,
        book.chapters[0].html.replace('</body>', '<img src="../Images/figura.png" alt="Outra figura"/></body>'),
        book.chapters[0].source_path,
    )
    second = Chapter(
        book.chapters[1].id, book.chapters[1].title,
        book.chapters[1].html.replace('</body>', '<div class="footnote">Nota em div ausente.</div></body>'),
        book.chapters[1].source_path,
    )
    expected = BookModel(book.title, book.language, (first, second), book.resources, ())

    report = validate_pdf(pdf, expected)

    assert report.status == "review_required"
    assert any("imagem" in warning.lower() for warning in report.warnings)
    assert any("nota" in warning.lower() for warning in report.warnings)
