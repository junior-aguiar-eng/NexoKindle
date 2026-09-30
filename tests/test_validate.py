import os
from pathlib import Path

import pymupdf
import pytest

from kindle_pdf.model import BookModel, Chapter
from kindle_pdf.render import PrintStyle, render_pdf
from kindle_pdf.validate import validate_pdf
from tests.print_fixtures import make_print_book


@pytest.mark.parametrize('omit_cell', [False, True])
def test_table_sections_preserve_cell_comparison_and_detect_cell_loss(tmp_path, omit_cell):
    html = '<html><body><h1>Chapter</h1><table><tbody><tr><td>First term</td><td>First definition</td></tr><tr><td>Second term</td><td>Second definition</td></tr></tbody></table></body></html>'
    book = BookModel('Book', 'en', (Chapter('a', 'Chapter', html, tmp_path/'chapter.xhtml'),), (), ())
    pdf = tmp_path/'table.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page()
        text = 'Chapter\nFirst term\nFirst definition\n1.\nSecond term'
        if not omit_cell:
            text += '\nSecond definition'
        page.insert_text((72,72), text)
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert (validate_pdf(pdf, book).status == 'valid') is (not omit_cell)


def test_extraction_spacing_inside_words_does_not_imply_content_loss(tmp_path):
    book = BookModel('Book', 'pt-BR', (Chapter('a','Chapter','<html><body><h1>Chapter</h1><p>coordenar advogado</p></body></html>',tmp_path/'chapter.xhtml'),), (), ())
    pdf=tmp_path/'spacing.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((72,72),'Chapter\ncoorde nar advo gado')
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert validate_pdf(pdf,book).status=='valid'


def test_repeated_body_paragraph_must_not_be_approved_when_one_copy_is_lost(tmp_path):
    book=BookModel('Book','en',(Chapter('a','Chapter','<html><body><h1>Chapter</h1><p>Unique body paragraph.</p><p>Unique body paragraph.</p></body></html>',tmp_path/'chapter.xhtml'),), (), ())
    pdf=tmp_path/'repeated.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((72,72),'Chapter\nUnique body paragraph.')
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert validate_pdf(pdf,book).status!='valid'


def test_generated_list_labels_do_not_interrupt_body_comparison(tmp_path):
    paragraph='This complete explanatory paragraph contains substantive material that continues after a page break.'
    book=BookModel('Book','en',(Chapter('a','Chapter',f'<html><body><h1>Chapter</h1><p>{paragraph}</p></body></html>',tmp_path/'chapter.xhtml'),), (), ())
    pdf=tmp_path/'labels.pdf'
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((40,150),'22)')
        page.insert_text((72,72),'Chapter\nThis complete explanatory paragraph contains substantive\nmaterial that continues after a page break.')
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert validate_pdf(pdf,book).status=='valid'


@pytest.mark.renderer
def test_automatic_hyphenation_does_not_imply_missing_content(tmp_path):
    source=tmp_path/'chapter.xhtml'
    source.write_text('')
    book=BookModel('Book','pt-BR',(Chapter('a','Chapter','<html><body><h1>Chapter</h1><p style="hyphens:auto;width:25mm">necessariamente multiplicidade interessados compromisso</p></body></html>',source),), (), ())
    pdf=render_pdf(book,tmp_path/'hyphenated.pdf',PrintStyle())
    assert validate_pdf(pdf,book).status=='valid'


def test_page_number_does_not_interrupt_complete_note(tmp_path):
    source = tmp_path / 'chapter.xhtml'
    book = BookModel('Book', 'en', (Chapter('a', 'Chapter', '<html><body><h1>Chapter</h1><aside>Alpha beta.</aside></body></html>', source),), (), ())
    pdf = tmp_path / 'pages.pdf'
    with pymupdf.open() as doc:
        first = doc.new_page()
        first.insert_text((72,72), 'Chapter\nAlpha')
        first.insert_text((290,815), '1')
        second = doc.new_page()
        second.insert_text((72,72), 'beta.')
        second.insert_text((290,815), '2')
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert validate_pdf(pdf, book).status == 'valid'


def test_lexical_hyphen_and_adjacent_note_marker_preserve_body_coverage(tmp_path):
    source = tmp_path / 'chapter.xhtml'
    book = BookModel('Book', 'pt-BR', (Chapter('a', 'Chapter', '<html><body><h1>Chapter</h1><p>A punição<a>1</a> pode reduzi-los.</p></body></html>', source),), (), ())
    pdf = tmp_path / 'hyphen.pdf'
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72,72), 'Chapter\nA punição1 pode reduzi-\nlos.')
        doc.set_toc([[1,'1. Chapter',1]])
        doc.save(pdf)
    assert validate_pdf(pdf, book).status == 'valid'


@pytest.mark.renderer
def test_inline_note_punctuation_is_not_reported_missing(tmp_path):
    source = tmp_path / "chapter.xhtml"
    source.write_text("")
    book = BookModel("Book", "en", (Chapter("a", "Chapter", '<html><body><h1>Chapter</h1><p>Complete body.</p><aside>Alpha <em>beta</em>.</aside></body></html>', source),), (), ())
    pdf = render_pdf(book, tmp_path / "note.pdf", PrintStyle())
    assert validate_pdf(pdf, book).status == "valid"


def test_title_and_outline_do_not_approve_missing_body(tmp_path):
    source = tmp_path / "chapter.xhtml"
    book = BookModel("Book", "en", (Chapter("a", "Chapter", '<html><body><h1>Chapter</h1><p>Essential substantive body completely absent.</p></body></html>', source),), (), ())
    pdf = tmp_path / "incomplete.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((72, 72), "Chapter")
        doc.set_toc([[1, "1. Chapter", 1]])
        doc.save(pdf)
    assert validate_pdf(pdf, book).status == "invalid"


@pytest.mark.renderer
def test_body_loss_requires_review_even_with_title_and_outline(tmp_path):
    source = tmp_path / "chapter.xhtml"
    source.write_text("")
    html = '<html><body><h1>Chapter</h1><p>First complete paragraph with several words.</p><p>Second substantive paragraph was removed entirely.</p></body></html>'
    expected = BookModel("Book", "en", (Chapter("a", "Chapter", html, source),), (), ())
    actual = BookModel("Book", "en", (Chapter("a", "Chapter", html.replace('<p>Second substantive paragraph was removed entirely.</p>', ''), source),), (), ())
    pdf = render_pdf(actual, tmp_path / "partial.pdf", PrintStyle())
    assert validate_pdf(pdf, expected).status != "valid"


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
