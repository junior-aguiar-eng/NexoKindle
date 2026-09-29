import os
from pathlib import Path
import subprocess

import pymupdf
import pytest

from kindle_pdf.model import BookModel, Chapter
from kindle_pdf.render import PrintStyle, RenderError, UnsafeRenderInputError, render_pdf
from tests.print_fixtures import make_print_book


@pytest.mark.renderer
def test_render_pdf_has_text_chapters_note_table_and_image(tmp_path: Path) -> None:
    book = make_print_book(tmp_path / "book")
    output = tmp_path / "book.tmp.pdf"
    style = PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"]))

    result = render_pdf(book, output, style)

    assert result == output
    with pymupdf.open(output) as pdf:
        text = "\n".join(page.get_text() for page in pdf)
        assert len(pdf) >= 2
        assert "Introdução" in text
        assert "Capítulo 1" in text
        assert "Nota interna verificável." in text
        assert "Processo" in text
        assert sum(len(page.get_images()) for page in pdf) >= 1
        assert any(link.get("page", -1) >= 0 and link.get("nameddest") == "c2-nota-1" for page in pdf for link in page.get_links())


def test_render_rejects_remote_image_even_for_direct_book_model(tmp_path: Path) -> None:
    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    book = BookModel(
        "Teste", "pt-BR",
        (Chapter("one", "Um", '<html><body><h1>Um</h1><img src="https://example.test/a.png" /></body></html>', source),),
        (), (),
    )

    with pytest.raises(UnsafeRenderInputError):
        render_pdf(book, tmp_path / "out.pdf", PrintStyle(renderer=Path("unused")))

    assert not (tmp_path / "out.pdf").exists()


@pytest.mark.renderer
def test_render_rebases_inline_svg_image_to_local_resource(tmp_path: Path) -> None:
    from tests.print_fixtures import PNG

    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    image = tmp_path / "cover.png"
    image.write_bytes(PNG)
    book = BookModel(
        "Teste", "pt-BR",
        (Chapter("cover", "Cover", '<html><body><svg width="100" height="100"><image href="cover.png" width="100" height="100"/></svg></body></html>', source),),
        (image,), (),
    )

    pdf_path = render_pdf(book, tmp_path / "cover.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    with pymupdf.open(pdf_path) as pdf:
        assert sum(len(page.get_images()) for page in pdf) >= 1
        assert "Cover" not in " ".join(page.get_text() for page in pdf)


@pytest.mark.renderer
def test_render_removes_partial_pdf_after_renderer_timeout(tmp_path: Path, monkeypatch) -> None:
    book = make_print_book(tmp_path / "book")
    target = tmp_path / "partial.tmp.pdf"

    def timeout_after_partial(args, **kwargs):
        target.write_bytes(b"partial")
        raise subprocess.TimeoutExpired(args, 600)

    monkeypatch.setattr(subprocess, "run", timeout_after_partial)

    with pytest.raises(RenderError):
        render_pdf(book, target, PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    assert not target.exists()


@pytest.mark.renderer
def test_render_rejects_css_import_hidden_by_comment(tmp_path: Path) -> None:
    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    stylesheet = tmp_path / "book.css"
    stylesheet.write_text('@import/**/"file:///C:/outside.css";', encoding="utf-8")
    book = BookModel(
        "Teste", "pt-BR",
        (Chapter("one", "Um", '<html><head><link rel="stylesheet" href="book.css"/></head><body><h1>Um</h1><p>Texto.</p></body></html>', source),),
        (stylesheet,), (),
    )

    with pytest.raises(UnsafeRenderInputError):
        render_pdf(book, tmp_path / "out.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))

    assert not (tmp_path / "out.tmp.pdf").exists()


def test_render_rebases_external_svg_use_reference(tmp_path: Path) -> None:
    from kindle_pdf.render import _html_fragment

    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    sprite = tmp_path / "sprite.svg"
    sprite.write_text('<svg xmlns="http://www.w3.org/2000/svg"><symbol id="shape"/></svg>', encoding="utf-8")
    chapter = Chapter("one", None, '<html><body><svg><use href="sprite.svg#shape"/></svg></body></html>', source)

    _head, body = _html_fragment(chapter, {source.resolve(): 1}, {source.resolve(), sprite.resolve()}, 1)

    assert sprite.as_uri() + "#shape" in body


@pytest.mark.renderer
def test_render_rejects_attachment_link_to_local_file(tmp_path: Path) -> None:
    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    book = BookModel(
        "Teste", "pt-BR",
        (Chapter("one", "Um", '<html><body><h1>Um</h1><a href="file:///C:/outside.txt" rel="attachment">Arquivo</a></body></html>', source),),
        (), (),
    )

    with pytest.raises(UnsafeRenderInputError):
        render_pdf(book, tmp_path / "out.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))


@pytest.mark.renderer
def test_render_rejects_local_file_reference_inside_svg_resource(tmp_path: Path) -> None:
    source = tmp_path / "chapter.xhtml"
    source.write_text("", encoding="utf-8")
    svg = tmp_path / "figure.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///C:/outside.png"/></svg>', encoding="utf-8")
    book = BookModel(
        "Teste", "pt-BR",
        (Chapter("one", "Um", '<html><body><h1>Um</h1><img src="figure.svg"/></body></html>', source),),
        (svg,), (),
    )

    with pytest.raises(UnsafeRenderInputError):
        render_pdf(book, tmp_path / "out.tmp.pdf", PrintStyle(renderer=Path(os.environ["WEASYPRINT_EXE"])))
