"""Livro EPUB sintético para testar ordem, notas e recursos locais."""

from pathlib import Path
from zipfile import ZipFile


CONTAINER = b'''<?xml version="1.0" encoding="utf-8"?>
<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>'''

OPF = b'''<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">urn:test:livro</dc:identifier>
    <dc:title>Livro Juridico de Teste</dc:title>
    <dc:language>pt-BR</dc:language>
  </metadata>
  <manifest>
    <item id="capitulo-1" href="Text/a-capitulo.xhtml" media-type="application/xhtml+xml"/>
    <item id="intro" href="Text/z-intro.xhtml" media-type="application/xhtml+xml"/>
    <item id="imagem" href="Images/figura.svg" media-type="image/svg+xml"/>
    <item id="estilo" href="Styles/book.css" media-type="text/css"/>
  </manifest>
  <spine><itemref idref="intro"/><itemref idref="capitulo-1"/></spine>
</package>'''

INTRO = b'''<html xmlns="http://www.w3.org/1999/xhtml"><head>
<title>Introducao</title><link rel="stylesheet" href="../Styles/book.css"/></head>
<body><h1>Introducao</h1><p>Texto inicial <a href="a-capitulo.xhtml#nota-1" epub:type="noteref"
xmlns:epub="http://www.idpf.org/2007/ops">1</a>.</p>
<img src="../Images/figura.svg" alt="Figura"/></body></html>'''

CHAPTER = b'''<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Capitulo 1</title></head>
<body><h1>Capitulo 1</h1><p>Corpo do capitulo.</p><aside id="nota-1">Nota interna.</aside></body></html>'''


def make_epub(path: Path, replacements: dict[str, bytes] | None = None) -> Path:
    files = {
        "mimetype": b"application/epub+zip",
        "META-INF/container.xml": CONTAINER,
        "OEBPS/content.opf": OPF,
        "OEBPS/Text/z-intro.xhtml": INTRO,
        "OEBPS/Text/a-capitulo.xhtml": CHAPTER,
        "OEBPS/Images/figura.svg": b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        "OEBPS/Styles/book.css": b"h1 { font-weight: bold; }",
    }
    files.update(replacements or {})
    with ZipFile(path, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return path


def make_text_epub(path: Path, replacements: dict[str, bytes] | None = None) -> Path:
    plain_intro = INTRO.replace(b'<img src="../Images/figura.svg" alt="Figura"/>', b'')
    return make_epub(path, {"OEBPS/Text/z-intro.xhtml": plain_intro, **(replacements or {})})
