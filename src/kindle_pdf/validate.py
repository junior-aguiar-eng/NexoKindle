"""Inspeção estrutural e textual de PDF antes da publicação."""

from dataclasses import dataclass
from collections import Counter
import re
import unicodedata
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET

import pymupdf

from .model import BookModel

ValidationStatus = Literal["valid", "review_required", "invalid"]
BLOCK_TAGS = {"p", "div", "li", "br", "td", "th", "tr", "table", "tbody", "thead", "tfoot", "blockquote",
              "section", "article", "dl", "dt", "dd", "ul", "ol", "caption",
              "figure", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass(frozen=True, slots=True)
class ValidationReport:
    status: ValidationStatus
    pages: int
    text_chars: int
    chapters_found: int
    warnings: tuple[str, ...]


def validate_pdf(pdf_path: Path, expected: BookModel) -> ValidationReport:
    """Classifica legibilidade, títulos de capítulos, notas e imagens."""
    warnings = list(expected.warnings)
    try:
        with pymupdf.open(pdf_path) as document:
            pages = len(document)
            text = "\n".join(_page_content(page, index) for index, page in enumerate(document, 1))
            reading_order = "\n".join(_page_content(page, index, sort=True)
                                     for index, page in enumerate(document, 1))
            image_count = sum(len(page.get_image_info()) for page in document)
            chapter_outlines = [title for level, title, _page in document.get_toc() if level == 1]
    except (OSError, RuntimeError, ValueError):
        return ValidationReport("invalid", 0, 0, 0, ("PDF ausente ou ilegível.",))
    if pages == 0 or not text.strip():
        return ValidationReport("invalid", pages, 0, 0, ("PDF sem texto extraível.",))
    normalized = _normal(text)
    # A ordem de pintura e a ordem geométrica divergem em listas e colunas.
    # Compare ambas sem descartar marcadores nem texto substantivo.
    content_views = tuple(dict.fromkeys(
        _compact(view) for extracted in (text, reading_order)
        for view in (extracted, re.sub(r"\u2010[ \t]*\n", "", extracted))
    ))
    expected_outlines = [f"{index}. {chapter.title or 'Seção'}" for index, chapter in enumerate(expected.chapters, 1)]
    chapters_found = sum(actual == planned for actual, planned in zip(chapter_outlines, expected_outlines))
    missing_text_title = any(
        chapter.title and not _visual_only(chapter.html) and _normal(chapter.title) not in normalized
        for chapter in expected.chapters
    )
    if chapters_found != len(expected.chapters) or len(chapter_outlines) != len(expected_outlines) or missing_text_title:
        warnings.append("Título de capítulo ausente no texto extraído.")
        status: ValidationStatus = "invalid"
    else:
        status = "valid"
    expected_images = 0
    vector_images = 0
    body_fragments: Counter[str] = Counter()
    for chapter in expected.chapters:
        try:
            tree = ET.fromstring(chapter.html)
        except ET.ParseError:
            warnings.append("HTML esperado inválido.")
            status = "invalid"
            continue
        body = next((node for node in tree.iter() if node.tag.rsplit("}", 1)[-1].lower() == "body"), None)
        if body is not None:
            body_fragments.update(_body_fragments(body))
        for element in tree.iter():
            tag = element.tag.rsplit("}", 1)[-1].lower()
            attributes = {key.rsplit("}", 1)[-1].lower(): value for key, value in element.attrib.items()}
            note_class = set(attributes.get("class", "").lower().split())
            is_note = tag == "aside" or (
                tag in {"div", "p", "li"} and (
                    note_class & {"footnote", "endnote"}
                    or "footnote" in attributes.get("type", "").lower()
                    or attributes.get("role", "").lower() == "doc-footnote"
                )
            )
            if is_note:
                note = _compact(_element_text(element))
                if note and not any(note in view for view in content_views):
                    warnings.append("Nota ausente no texto extraído.")
                    if status == "valid":
                        status = "review_required"
            image_ref = (element.get("src") or element.get("href") or "").lower().split("?", 1)[0]
            if tag in {"img", "image"} and image_ref.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                expected_images += 1
            if tag in {"img", "object"} and image_ref.endswith(".svg"):
                vector_images += 1
    if image_count < expected_images:
        warnings.append("Imagem raster ausente no PDF.")
        if status == "valid":
            status = "review_required"
    if vector_images:
        warnings.append("Figura SVG requer inspeção visual.")
        if status == "valid":
            status = "review_required"
    if body_fragments:
        expected_chars = sum(len(fragment) * count for fragment, count in body_fragments.items())
        found = sum(len(fragment) * min(count, max(view.count(fragment) for view in content_views))
                    for fragment, count in body_fragments.items())
        coverage = found / expected_chars
        if coverage < 1:
            warnings.append("Conteúdo do corpo do livro não foi integralmente confirmado no PDF.")
            if coverage < 0.5:
                status = "invalid"
            elif status == "valid":
                status = "review_required"
    if warnings and status == "valid":
        status = "review_required"
    return ValidationReport(status, pages, len(text.strip()), chapters_found, tuple(dict.fromkeys(warnings)))


def _compact(text: str) -> str:
    return "".join(_normal(unicodedata.normalize("NFKC", text).replace("\u00ad", "")).split())


def _words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    return re.findall(r"\w+", text.casefold())


def _page_content(page: pymupdf.Page, number: int, *, sort: bool = False) -> str:
    """Exclui apenas o contador de página do rodapé central do renderizador."""
    blocks = page.get_text("blocks")
    candidates = [index for index, block in enumerate(blocks)
                  if block[1] > page.rect.height * 0.9
                  and abs((block[0] + block[2]) / 2 - page.rect.width / 2) < 12
                  and block[4].strip() == str(number)]
    footer = max(candidates, key=lambda index: blocks[index][1]) if candidates else None
    if sort:
        text = page.get_text(sort=True)
        if footer is not None:
            # O rodapé já foi identificado por posição e valor, não por ser um número.
            text = re.sub(r"\n[ \t]*" + str(number) + r"[ \t]*\n?\Z", "", text)
        return text
    return "\n".join(block[4] for index, block in enumerate(blocks)
                     if index != footer and block[6] == 0)


def _is_note(element: ET.Element) -> bool:
    tag = element.tag.rsplit("}", 1)[-1].lower()
    attrs = {key.rsplit("}", 1)[-1].lower(): value for key, value in element.attrib.items()}
    return tag == "aside" or bool(
        set(attrs.get("class", "").lower().split()) & {"footnote", "endnote"}
        or "footnote" in attrs.get("type", "").lower()
        or attrs.get("role", "").lower() == "doc-footnote"
    )


def _element_text(element: ET.Element) -> str:
    parts = [element.text or ""]
    for child in element:
        block = child.tag.rsplit("}", 1)[-1].lower() in BLOCK_TAGS
        if block:
            parts.append(" ")
        parts.append(_element_text(child))
        if block:
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


def _body_text(element: ET.Element) -> str:
    tag = element.tag.rsplit("}", 1)[-1].lower()
    if tag in {"head", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"} or _is_note(element):
        return ""
    parts = [element.text or ""]
    for child in element:
        block = child.tag.rsplit("}", 1)[-1].lower() in BLOCK_TAGS
        if block:
            parts.append(" ")
        parts.append(_body_text(child))
        if block:
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts)


def _body_fragments(element: ET.Element) -> list[str]:
    """Separa blocos de conteúdo; preserva caracteres e frequência sem depender de espaços do PDF."""
    fragments: list[str] = []
    run: list[str] = []

    def flush() -> None:
        normalized = _compact("".join(run))
        if normalized:
            fragments.append(normalized)
        run.clear()

    def walk(node: ET.Element) -> None:
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag in {"head", "script", "style", "h1", "h2", "h3", "h4", "h5", "h6"} or _is_note(node):
            flush()
            return
        block = tag in BLOCK_TAGS
        if block:
            flush()
        run.append(node.text or "")
        for child in node:
            walk(child)
            run.append(child.tail or "")
        if block:
            flush()

    walk(element)
    flush()
    return fragments


def _normal(text: str) -> str:
    return " ".join(text.casefold().split())


def _visual_only(html: str) -> bool:
    try:
        tree = ET.fromstring(html)
    except ET.ParseError:
        return False
    body = next((node for node in tree.iter() if node.tag.rsplit("}", 1)[-1].lower() == "body"), None)
    if body is None or " ".join(body.itertext()).strip():
        return False
    return any(node.tag.rsplit("}", 1)[-1].lower() in {"img", "svg"} for node in body.iter())
