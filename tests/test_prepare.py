from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from kindle_pdf.prepare import UnsafeResourceError, prepare_book
from kindle_pdf.unpack import unpack_book
from tests.book_fixtures import INTRO, OPF, make_epub


def test_prepare_follows_spine_and_keeps_note_and_image(tmp_path: Path) -> None:
    unpacked = unpack_book(make_epub(tmp_path / "livro.epub"), tmp_path / "work")

    book = prepare_book(unpacked)

    assert book.title == "Livro Juridico de Teste"
    assert book.language == "pt-BR"
    assert [chapter.id for chapter in book.chapters] == ["intro", "capitulo-1"]
    assert [chapter.title for chapter in book.chapters] == ["Introducao", "Capitulo 1"]
    assert "noteref" in book.chapters[0].html
    assert "Nota interna." in book.chapters[1].html
    assert any(path.name == "figura.svg" for path in book.resources)
    assert any(path.name == "book.css" for path in book.resources)
    assert all(path.is_relative_to(unpacked.root) for path in book.resources)
    assert book.warnings == ()


def test_prepare_reports_missing_resource_without_losing_text(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub")
    unpacked = unpack_book(source, tmp_path / "work")
    (unpacked.root / "OEBPS/Images/figura.svg").unlink()

    book = prepare_book(unpacked)

    assert len(book.chapters) == 2
    assert any("figura.svg" in warning for warning in book.warnings)


@pytest.mark.parametrize(
    "reference",
    ["../../../../escape.png", "https://example.test/image.png", "//example.test/image.png"],
)
def test_prepare_rejects_escaping_or_remote_resource(tmp_path: Path, reference: str) -> None:
    unsafe_intro = INTRO.replace(b"../Images/figura.svg", reference.encode())
    source = make_epub(
        tmp_path / "livro.epub", {"OEBPS/Text/z-intro.xhtml": unsafe_intro}
    )
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)


def test_prepare_rejects_remote_css_import(tmp_path: Path) -> None:
    source = make_epub(
        tmp_path / "livro.epub",
        {"OEBPS/Styles/book.css": b'@import url("https://example.test/style.css");'},
    )
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)


def test_prepare_accepts_legacy_html_with_unquoted_attributes(tmp_path: Path) -> None:
    legacy_opf = OPF.replace(
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="application/xhtml+xml"',
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="text/html"',
    )
    legacy_html = b'<html><head><title>Capitulo 1</title></head><body><h1>Capitulo 1</h1><p id=nota-1>Nota interna.</p><img src=../Images/figura.svg></body></html>'
    source = make_epub(
        tmp_path / "livro.epub",
        {
            "OEBPS/content.opf": legacy_opf,
            "OEBPS/Text/a-capitulo.xhtml": legacy_html,
        },
    )
    unpacked = unpack_book(source, tmp_path / "work")

    book = prepare_book(unpacked)

    assert book.chapters[1].title == "Capitulo 1"
    assert "Nota interna." in book.chapters[1].html
    assert any(path.name == "figura.svg" for path in book.resources)


def test_prepare_accepts_legacy_html_larger_than_xml_limit(tmp_path: Path) -> None:
    legacy_opf = OPF.replace(
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="application/xhtml+xml"',
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="text/html"',
    )
    legacy_html = b"<html><body><h1>Capitulo 1</h1><p>" + b"a" * (2 * 1024 * 1024) + b"</p></body></html>"
    source = make_epub(tmp_path / "livro.epub", {
        "OEBPS/content.opf": legacy_opf,
        "OEBPS/Text/a-capitulo.xhtml": legacy_html,
    })
    unpacked = unpack_book(source, tmp_path / "work")

    book = prepare_book(unpacked)

    assert len(book.chapters) == 2
    assert book.chapters[1].title == "Capitulo 1"


def test_prepare_rejects_remote_reference_inside_svg(tmp_path: Path) -> None:
    source = make_epub(tmp_path / "livro.epub", {
        "OEBPS/Images/figura.svg": b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/img.png"/></svg>',
    })
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)


def test_prepare_rejects_remote_reference_inside_style_element(tmp_path: Path) -> None:
    unsafe_intro = INTRO.replace(
        b"</head>", b'<style>body { background: url(https://example.test/bg.png) }</style></head>'
    )
    source = make_epub(tmp_path / "livro.epub", {"OEBPS/Text/z-intro.xhtml": unsafe_intro})
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)


def test_legacy_html_is_normalized_to_parseable_xhtml(tmp_path: Path) -> None:
    legacy_opf = OPF.replace(
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="application/xhtml+xml"',
        b'id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="text/html"',
    )
    source = make_epub(tmp_path / "livro.epub", {
        "OEBPS/content.opf": legacy_opf,
        "OEBPS/Text/a-capitulo.xhtml": b'<html><body><mbp:pagebreak/><h1>Capitulo 1</h1></body></html>',
    })
    unpacked = unpack_book(source, tmp_path / "work")

    book = prepare_book(unpacked)

    ET.fromstring(book.chapters[1].html)


@pytest.mark.parametrize(
    "injection",
    [
        b'<base href="https://example.test/"/>',
        b'<img srcset="https://example.test/large.png 2x"/>',
    ],
)
def test_prepare_rejects_other_remote_loading_attributes(
    tmp_path: Path, injection: bytes
) -> None:
    source = make_epub(tmp_path / "livro.epub", {
        "OEBPS/Text/z-intro.xhtml": INTRO.replace(b"</head>", injection + b"</head>"),
    })
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)


def test_prepare_rejects_remote_image_inside_inline_svg(tmp_path: Path) -> None:
    svg_image = b'<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/cover.png"/></svg>'
    unsafe_intro = INTRO.replace(b'<img src="../Images/figura.svg" alt="Figura"/>', svg_image)
    source = make_epub(tmp_path / "livro.epub", {"OEBPS/Text/z-intro.xhtml": unsafe_intro})
    unpacked = unpack_book(source, tmp_path / "work")

    with pytest.raises(UnsafeResourceError):
        prepare_book(unpacked)
