"""Converte manifesto e capítulos extraídos em um modelo seguro e ordenado."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

import html5lib

from .model import BookModel, Chapter, UnpackedBook

DC = "http://purl.org/dc/elements/1.1/"
MAX_XML_BYTES = 2 * 1024 * 1024
MAX_HTML_BYTES = 64 * 1024 * 1024
CSS_URL = re.compile(r"url\(\s*['\"]?([^'\")]+)", re.IGNORECASE)
CSS_IMPORT = re.compile(r"@import\s+['\"]([^'\"]+)", re.IGNORECASE)


class UnsafeResourceError(ValueError):
    pass


class InvalidBookError(ValueError):
    pass


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _safe_reference(reference: str, base: Path, root: Path) -> Path | None:
    value = reference.strip()
    if not value or value.startswith("#"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith("//"):
        raise UnsafeResourceError("Referência remota ou com esquema não permitida.")
    decoded = unquote(parsed.path)
    if not decoded or "\\" in decoded or "\x00" in decoded:
        raise UnsafeResourceError("Referência de recurso inválida.")
    target = (base.parent / decoded).resolve()
    if not target.is_relative_to(root):
        raise UnsafeResourceError("Recurso escapa do diretório extraído.")
    return target


def _read_xml(path: Path) -> ET.Element:
    if not path.is_file() or path.stat().st_size > MAX_XML_BYTES:
        raise InvalidBookError("Manifesto ou capítulo ausente ou excessivo.")
    try:
        return ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise InvalidBookError("XML do livro inválido.") from exc


def _read_html(path: Path) -> ET.Element:
    if not path.is_file() or path.stat().st_size > MAX_HTML_BYTES:
        raise InvalidBookError("Capítulo HTML ausente ou excessivo.")
    try:
        with path.open("rb") as source:
            tree = html5lib.parse(source, treebuilder="etree")
        for element in tree.iter():
            if isinstance(element.tag, str):
                element.tag = _normalize_html_name(element.tag)
            element.attrib.update(
                {
                    _normalize_html_name(key): value
                    for key, value in tuple(element.attrib.items())
                    if ":" in key.rsplit("}", 1)[-1]
                }
            )
            for key in tuple(element.attrib):
                if ":" in key.rsplit("}", 1)[-1]:
                    del element.attrib[key]
        return tree
    except (OSError, ValueError) as exc:
        raise InvalidBookError("HTML do livro inválido.") from exc


def _normalize_html_name(name: str) -> str:
    if name.startswith("{"):
        namespace, local = name.rsplit("}", 1)
        return namespace + "}" + local.replace(":", "-")
    return name.replace(":", "-")


def _text_of(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None


def _css_references(css: Path, root: Path, add_resource, visited: set[Path]) -> None:
    if css in visited or not css.is_file():
        return
    visited.add(css)
    if css.stat().st_size > MAX_XML_BYTES:
        raise InvalidBookError("CSS excessivo.")
    contents = css.read_text(encoding="utf-8", errors="replace")
    for reference in CSS_URL.findall(contents) + CSS_IMPORT.findall(contents):
        target = _safe_reference(reference, css, root)
        if target is not None:
            add_resource(target)
            if target.suffix.lower() == ".css":
                _css_references(target, root, add_resource, visited)


def _svg_references(svg: Path, root: Path, add_resource) -> None:
    tree = _read_xml(svg)
    for element in tree.iter():
        tag = _local_name(element.tag)
        if tag == "script":
            raise UnsafeResourceError("Script em SVG não permitido.")
        if tag == "style" and element.text:
            for reference in CSS_URL.findall(element.text) + CSS_IMPORT.findall(element.text):
                target = _safe_reference(reference, svg, root)
                if target is not None:
                    add_resource(target)
        for key, value in element.attrib.items():
            attr = _local_name(key)
            if attr in {"base", "srcset"}:
                raise UnsafeResourceError("Base ou conjunto de fontes não permitido em SVG.")
            if attr in {"href", "src", "data"}:
                target = _safe_reference(value, svg, root)
                if target is not None:
                    add_resource(target)
            for reference in CSS_URL.findall(value):
                target = _safe_reference(reference, svg, root)
                if target is not None:
                    add_resource(target)


def prepare_book(unpacked: UnpackedBook) -> BookModel:
    """Lê a ordem do spine e valida referências antes de devolver HTML local."""
    root = unpacked.root.resolve()
    manifest_path = unpacked.manifest_path.resolve()
    if not manifest_path.is_relative_to(root):
        raise UnsafeResourceError("Manifesto fora do diretório extraído.")
    package = _read_xml(manifest_path)
    metadata = package.find("{*}metadata")
    manifest = package.find("{*}manifest")
    spine = package.find("{*}spine")
    if metadata is None or manifest is None or spine is None:
        raise InvalidBookError("Pacote OPF incompleto.")
    title = _text_of(metadata.find(f"{{{DC}}}title"))
    if not title:
        raise InvalidBookError("Livro sem título no OPF.")
    language = _text_of(metadata.find(f"{{{DC}}}language"))

    items: dict[str, tuple[Path, str]] = {}
    for item in manifest.findall("{*}item"):
        item_id, href = item.get("id"), item.get("href")
        if not item_id or not href or item_id in items:
            raise InvalidBookError("Item do manifesto inválido ou duplicado.")
        path = _safe_reference(href, manifest_path, root)
        if path is None:
            raise InvalidBookError("Item do manifesto sem caminho.")
        items[item_id] = (path, item.get("media-type", ""))

    ordered_ids: list[str] = []
    for itemref in spine.findall("{*}itemref"):
        ref = itemref.get("idref")
        if not ref or ref not in items:
            raise InvalidBookError("Spine aponta para item inexistente.")
        ordered_ids.append(ref)
    if not ordered_ids:
        raise InvalidBookError("Spine vazio.")

    resources: list[Path] = []
    warnings: list[str] = []

    def add_resource(path: Path) -> None:
        if path.is_file():
            if path not in resources:
                resources.append(path)
                if path.suffix.lower() == ".svg":
                    _svg_references(path, root, add_resource)
        else:
            warning = f"Recurso ausente: {path.relative_to(root).as_posix()}"
            if warning not in warnings:
                warnings.append(warning)

    chapter_ids = set(ordered_ids)
    for item_id, (path, _) in items.items():
        if item_id not in chapter_ids:
            add_resource(path)

    chapters: list[Chapter] = []
    for item_id in ordered_ids:
        path, media_type = items[item_id]
        if media_type not in {"application/xhtml+xml", "text/html"}:
            raise InvalidBookError("Spine contém item que não é HTML.")
        tree = _read_html(path) if media_type == "text/html" else _read_xml(path)
        chapter_title = None
        for element in tree.iter():
            if _local_name(element.tag) == "h1":
                chapter_title = _text_of(element)
                if chapter_title:
                    break
        if not chapter_title:
            for element in tree.iter():
                if _local_name(element.tag) == "title":
                    chapter_title = _text_of(element)
                    break
        for element in tree.iter():
            tag = _local_name(element.tag)
            if tag == "script":
                raise UnsafeResourceError("Script em capítulo não permitido.")
            if tag == "style" and element.text:
                for reference in CSS_URL.findall(element.text) + CSS_IMPORT.findall(element.text):
                    target = _safe_reference(reference, path, root)
                    if target is not None:
                        add_resource(target)
            for key, value in element.attrib.items():
                attr = _local_name(key)
                if attr in {"base", "srcset"} or (tag == "base" and attr == "href"):
                    raise UnsafeResourceError("Base ou conjunto de fontes não permitido em capítulo.")
                if attr == "style":
                    for reference in CSS_URL.findall(value) + CSS_IMPORT.findall(value):
                        target = _safe_reference(reference, path, root)
                        if target is not None:
                            add_resource(target)
                elif attr in {"src", "poster", "data"} or (
                    attr == "href" and tag in {"link", "image", "use"}
                ):
                    target = _safe_reference(value, path, root)
                    if target is not None:
                        add_resource(target)
                elif attr == "href" and tag == "a" and not urlsplit(value).scheme:
                    _safe_reference(value, path, root)
        chapters.append(
            Chapter(
                id=item_id,
                title=chapter_title,
                html=ET.tostring(tree, encoding="unicode"),
                source_path=path,
            )
        )

    visited_css: set[Path] = set()
    for resource in tuple(resources):
        if resource.suffix.lower() == ".css":
            _css_references(resource, root, add_resource, visited_css)
    return BookModel(title, language, tuple(chapters), tuple(resources), tuple(warnings))
