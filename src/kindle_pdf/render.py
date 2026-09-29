"""Renderiza capítulos locais com WeasyPrint em um PDF temporário."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

import tinycss2

from .model import BookModel, Chapter

CSS_URL = re.compile(r"url\(\s*(['\"]?)([^'\")]+)\1\s*\)", re.IGNORECASE)
CSS_IMPORT = re.compile(r"@import\s+(['\"])([^'\"]+)\1", re.IGNORECASE)


class UnsafeRenderInputError(ValueError):
    pass


class RenderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PrintStyle:
    renderer: Path | None = None
    page_size: str = "A4"
    margin_mm: int = 20
    font_size_pt: int = 11


def _renderer_path(style: PrintStyle) -> Path:
    name = "weasyprint.exe" if sys.platform == "win32" else "weasyprint"
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    renderer = style.renderer or os.environ.get("WEASYPRINT_EXE") or bundled / "weasyprint" / name
    path = Path(renderer).resolve()
    if not path.is_file():
        raise RenderError("Renderizador local não encontrado.")
    return path


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1].replace(":", "-").lower()


def _resource_url(reference: str, source: Path, allowed: set[Path]) -> str:
    parsed = urlsplit(reference.strip())
    if parsed.scheme or parsed.netloc or reference.startswith("//"):
        raise UnsafeRenderInputError("Recurso remoto ou com esquema não permitido.")
    decoded = unquote(parsed.path)
    if not decoded and parsed.fragment:
        return f"#{parsed.fragment}"
    if not decoded or "\\" in decoded or "\x00" in decoded:
        raise UnsafeRenderInputError("Caminho de recurso inválido.")
    path = (source.parent / decoded).resolve()
    if path.is_file() and path not in allowed:
        raise UnsafeRenderInputError("Recurso fora do conjunto do livro.")
    return path.as_uri() + (f"#{parsed.fragment}" if parsed.fragment else "")


def _css_local(css: str, source: Path, allowed: set[Path]) -> str:
    _validate_css(css, source, allowed)

    def replace_url(match: re.Match[str]) -> str:
        return f'url("{_resource_url(match.group(2), source, allowed)}")'

    def replace_import(match: re.Match[str]) -> str:
        return f'@import "{_resource_url(match.group(2), source, allowed)}"'

    return CSS_IMPORT.sub(replace_import, CSS_URL.sub(replace_url, css))


def _validate_css(css: str, source: Path, allowed: set[Path]) -> None:
    """Rejeita imports e qualquer URL não pertencente aos recursos do livro."""
    for node in tinycss2.parse_stylesheet(css, skip_comments=False, skip_whitespace=False):
        if getattr(node, "type", None) == "at-rule" and node.lower_at_keyword == "import":
            raise UnsafeRenderInputError("Importação CSS não permitida.")

    def walk(nodes) -> None:
        for node in nodes:
            kind = getattr(node, "type", None)
            if kind == "url":
                _resource_url(node.value, source, allowed)
            elif kind == "function" and node.lower_name == "url":
                arguments = [item for item in node.arguments if item.type not in {"whitespace", "comment"}]
                if len(arguments) != 1 or arguments[0].type not in {"string", "url"}:
                    raise UnsafeRenderInputError("URL CSS ambígua.")
                _resource_url(arguments[0].value, source, allowed)
            for child_name in ("prelude", "content", "arguments"):
                children = getattr(node, child_name, None)
                if children and not (kind == "function" and node.lower_name == "url" and child_name == "arguments"):
                    walk(children)

    walk(tinycss2.parse_component_value_list(css))


def _validate_svg_resource(path: Path, allowed: set[Path]) -> None:
    if path.stat().st_size > 2 * 1024 * 1024:
        raise UnsafeRenderInputError("SVG excessivo.")
    try:
        tree = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise UnsafeRenderInputError("SVG inválido.") from exc
    for element in tree.iter():
        if _local_name(element.tag) == "script":
            raise UnsafeRenderInputError("Script em SVG não permitido.")
        if _local_name(element.tag) == "style" and element.text:
            _validate_css(element.text, path, allowed)
        for key, value in element.attrib.items():
            attr = _local_name(key)
            if attr in {"href", "src", "data", "poster"} and not value.startswith("#"):
                _resource_url(value, path, allowed)
            _validate_css(value, path, allowed)


def _html_fragment(chapter: Chapter, source_indexes: dict[Path, int], allowed: set[Path], index: int) -> tuple[str, str]:
    try:
        tree = ET.fromstring(chapter.html)
    except ET.ParseError as exc:
        raise UnsafeRenderInputError("Capítulo não contém HTML normalizado.") from exc
    head = None
    body = None
    for element in tree.iter():
        if _local_name(element.tag) == "head":
            head = element
        if _local_name(element.tag) == "body":
            body = element
    if body is None:
        raise UnsafeRenderInputError("Capítulo sem corpo HTML.")
    for element in tree.iter():
        element.tag = _local_name(element.tag)
        attributes = dict(element.attrib)
        element.attrib.clear()
        for key, value in attributes.items():
            attr = _local_name(key)
            if attr == "rel" and "attachment" in value.lower().split():
                raise UnsafeRenderInputError("Anexo PDF não permitido.")
            if attr in {"srcset", "base"} or (element.tag == "base" and attr == "href"):
                raise UnsafeRenderInputError("Base ou fontes alternativas não permitidas.")
            if attr in {"src", "poster", "data"} or (element.tag in {"link", "image", "use"} and attr == "href"):
                value = f"#c{index}-{value[1:]}" if element.tag == "use" and value.startswith("#") else _resource_url(value, chapter.source_path, allowed)
            elif attr == "href" and element.tag == "a" and urlsplit(value).scheme:
                if urlsplit(value).scheme.lower() not in {"http", "https", "mailto"}:
                    raise UnsafeRenderInputError("Link com esquema não permitido.")
            elif attr == "href" and element.tag == "a":
                parsed = urlsplit(value)
                target_path = (chapter.source_path.parent / unquote(parsed.path)).resolve() if parsed.path else chapter.source_path.resolve()
                target_index = source_indexes.get(target_path)
                if target_index is not None and parsed.fragment:
                    value = f"#c{target_index}-{parsed.fragment}"
                elif target_index is not None:
                    value = f"#chapter-{target_index}"
                elif parsed.path:
                    value = _resource_url(value, chapter.source_path, allowed)
            elif attr == "id":
                value = f"c{index}-{value}"
            elif attr == "style":
                value = _css_local(value, chapter.source_path, allowed)
            element.attrib[attr] = value
        if element.tag == "script":
            raise UnsafeRenderInputError("Script em capítulo não permitido.")
        if element.tag == "style" and element.text:
            element.text = _css_local(element.text, chapter.source_path, allowed)
    head_html = "" if head is None else "".join(
        ET.tostring(child, encoding="unicode", method="html")
        for child in head if child.tag == "style" or (child.tag == "link" and "stylesheet" in child.attrib.get("rel", "").lower().split())
    )
    content = "".join(ET.tostring(child, encoding="unicode", method="html") for child in body)
    if body.text and body.text.strip():
        content = escape(body.text) + content
    body_text = " ".join(body.itertext()).strip()
    visual_only = not body_text and any(element.tag in {"img", "svg"} for element in body.iter())
    if chapter.title and not visual_only and chapter.title.casefold() not in body_text.casefold():
        content = f"<h1>{escape(chapter.title)}</h1>" + content
    outline_label = escape(f"{index}. {chapter.title or 'Seção'}", quote=True)
    return head_html, f'<section class="chapter" id="chapter-{index}" data-chapter-label="{outline_label}">{content}</section>'


def _print_css(style: PrintStyle) -> str:
    if style.page_size not in {"A4", "Letter"} or not 10 <= style.margin_mm <= 35 or not 9 <= style.font_size_pt <= 14:
        raise ValueError("Estilo de impressão fora dos limites permitidos.")
    return f"""
@page {{ size: {style.page_size}; margin: {style.margin_mm}mm;
  @bottom-center {{ content: counter(page); font-size: 9pt; color: #666; }} }}
html {{ color: #202020; }}
body {{ font-family: Georgia, 'Noto Serif', serif; font-size: {style.font_size_pt}pt;
  line-height: 1.48; overflow-wrap: break-word; }}
section.chapter {{ break-before: page; bookmark-level: 1; bookmark-label: attr(data-chapter-label); }}
section.chapter:first-of-type {{ break-before: auto; }}
p {{ margin: 0 0 .75em; text-align: justify; orphans: 3; widows: 3; }}
h1, h2, h3, h4 {{ break-after: avoid; line-height: 1.2; text-align: left; }}
h1 {{ bookmark-level: none; }}
h1 {{ font-size: 18pt; margin: 0 0 .85em; }}
h2 {{ font-size: 14pt; margin: 1.2em 0 .55em; }}
blockquote {{ margin: 1em 0 1em 1.3em; padding-left: .9em; border-left: 2px solid #bbb; }}
blockquote p {{ text-align: left; }}
aside {{ margin: 1.2em 0; padding: .45em .7em; border-top: 1px solid #aaa; font-size: .88em; }}
table {{ border-collapse: collapse; width: 100%; margin: 1em 0; break-inside: avoid; }}
th, td {{ border: 1px solid #999; padding: .35em .5em; text-align: left; }}
img, svg {{ max-width: 100%; height: auto; }}
pre, code {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
"""


def render_pdf(book: BookModel, target_tmp: Path, style: PrintStyle) -> Path:
    """Cria PDF temporário pesquisável sem acessar recursos de rede."""
    if not book.chapters:
        raise UnsafeRenderInputError("Livro sem capítulos.")
    target = Path(target_tmp).resolve()
    if target.suffix.lower() != ".pdf" or target.exists():
        raise RenderError("Destino temporário inválido ou já existente.")
    allowed = {path.resolve() for path in book.resources} | {chapter.source_path.resolve() for chapter in book.chapters}
    source_indexes = {chapter.source_path.resolve(): index for index, chapter in enumerate(book.chapters, 1)}
    heads: list[str] = []
    sections: list[str] = []
    for index, chapter in enumerate(book.chapters, 1):
        head, section = _html_fragment(chapter, source_indexes, allowed, index)
        heads.append(head)
        sections.append(section)
    for path in book.resources:
        if path.suffix.lower() == ".css" and path.is_file():
            _css_local(path.read_text(encoding="utf-8", errors="replace"), path, allowed)
        if path.suffix.lower() == ".svg" and path.is_file():
            _validate_svg_resource(path, allowed)
    renderer = _renderer_path(style)
    css = _print_css(style)
    html = (f'<!doctype html><html lang="{escape(book.language or "und", quote=True)}"><head>'
            f'<meta charset="utf-8"><title>{escape(book.title)}</title>'
            + "".join(heads) + f"<style>{css}</style></head><body>" + "".join(sections) + "</body></html>")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="kindle-pdf-render-", dir=target.parent) as scratch:
            source = Path(scratch) / "print.html"
            source.write_text(html, encoding="utf-8")
            completed = subprocess.run(
                [str(renderer), "--allowed-protocols", "file", "--no-http-redirects", str(source), str(target)],
                shell=False, capture_output=True, text=True, errors="replace", timeout=600, check=False,
            )
            if completed.returncode != 0 or not target.is_file():
                raise RenderError(f"Renderizador falhou com código {completed.returncode}.")
    except (OSError, subprocess.TimeoutExpired) as exc:
        target.unlink(missing_ok=True)
        raise RenderError("Falha ao executar renderizador local.") from exc
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
