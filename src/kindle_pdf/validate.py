"""Inspeção estrutural e textual de PDF antes da publicação."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
import xml.etree.ElementTree as ET

import pymupdf

from .model import BookModel

ValidationStatus = Literal["valid", "review_required", "invalid"]


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
            text = "\n".join(page.get_text() for page in document)
            image_count = sum(len(page.get_image_info()) for page in document)
            chapter_outlines = [title for level, title, _page in document.get_toc() if level == 1]
    except (OSError, RuntimeError, ValueError):
        return ValidationReport("invalid", 0, 0, 0, ("PDF ausente ou ilegível.",))
    if pages == 0 or not text.strip():
        return ValidationReport("invalid", pages, 0, 0, ("PDF sem texto extraível.",))
    normalized = _normal(text)
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
    for chapter in expected.chapters:
        try:
            tree = ET.fromstring(chapter.html)
        except ET.ParseError:
            warnings.append("HTML esperado inválido.")
            status = "invalid"
            continue
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
                note = _normal(" ".join(element.itertext()))
                if note and note not in normalized:
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
    if warnings and status == "valid":
        status = "review_required"
    return ValidationReport(status, pages, len(text.strip()), chapters_found, tuple(warnings))


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
