"""Contrato estável do diagnóstico, compartilhável por CLI e interface gráfica."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DetectionStatus = Literal[
    "supported", "unsupported_format", "protected_or_unreadable", "invalid_file"
]
DrmState = Literal["protected", "not_detected", "unknown"]


@dataclass(frozen=True, slots=True)
class Detection:
    status: DetectionStatus
    format: str
    drm_state: DrmState
    size_bytes: int | None
    sha256: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class UnpackedBook:
    root: Path
    manifest_path: Path
    resource_dir: Path
    format: str


@dataclass(frozen=True, slots=True)
class Chapter:
    id: str
    title: str | None
    html: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class BookModel:
    title: str
    language: str | None
    chapters: tuple[Chapter, ...]
    resources: tuple[Path, ...]
    warnings: tuple[str, ...]
