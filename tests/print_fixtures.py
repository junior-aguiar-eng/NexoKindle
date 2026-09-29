"""Livro sintético de impressão com capítulos, nota, imagem e tabela."""

from pathlib import Path
import struct
import zlib

from kindle_pdf.model import BookModel, Chapter

def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))


def _test_png() -> bytes:
    row = b"\x00" + (b"\x1f\x5f\xaa" * 32) + (b"\xd9\xa4\x41" * 32)
    pixels = row * 64
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )


PNG = _test_png()


def make_print_book(root: Path) -> BookModel:
    text = root / "Text"
    images = root / "Images"
    text.mkdir(parents=True)
    images.mkdir(parents=True)
    first = text / "intro.xhtml"
    second = text / "capitulo.xhtml"
    image = images / "figura.png"
    image.write_bytes(PNG)
    first.write_text("", encoding="utf-8")
    second.write_text("", encoding="utf-8")
    return BookModel(
        "Livro Jurídico de Teste",
        "pt-BR",
        (
            Chapter(
                "intro",
                "Introdução",
                '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Introdução</h1>'
                '<p>Texto inicial e chamada <a href="capitulo.xhtml#nota-1">1</a>.</p>'
                '<img src="../Images/figura.png" alt="Figura de teste" style="width:35mm;height:35mm" />'
                '</body></html>',
                first,
            ),
            Chapter(
                "capitulo",
                "Capítulo 1",
                '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>Capítulo 1</h1>'
                '<blockquote><p>' + "Citação jurídica extensa. " * 15 + '</p></blockquote>'
                '<table><thead><tr><th>Fonte</th><th>Tema</th></tr></thead>'
                '<tbody><tr><td>Lei</td><td>Processo</td></tr></tbody></table>'
                '<aside id="nota-1">Nota interna verificável.</aside>'
                '</body></html>',
                second,
            ),
        ),
        (image,),
        (),
    )
