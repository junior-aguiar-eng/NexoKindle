"""Orquestra uma conversão local sem publicar saídas incompletas."""

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Callable, Literal

from .detect import detect_book
from .drm import DecryptAdapter, SecretInput, diagnose_protected
from .model import BookModel
from .prepare import InvalidBookError, UnsafeResourceError, prepare_book
from .render import PrintStyle, RenderError, UnsafeRenderInputError, render_pdf
from .unpack import ExtractionError, ToolUnavailableError, UnsafeArchiveError, UnsupportedBookError, unpack_book
from .validate import validate_pdf

PIPELINE_VERSION = "0.6.0"
ConversionStatus = Literal["converted", "review_required", "unsupported", "protected_or_unreadable", "failed"]
RenderCallable = Callable[[BookModel, Path, PrintStyle], Path]


@dataclass(frozen=True, slots=True)
class ConvertOptions:
    style: PrintStyle = field(default_factory=PrintStyle)
    renderer: RenderCallable = render_pdf
    decrypt_adapter: DecryptAdapter | None = field(default=None, repr=False)
    credential: SecretInput | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class ConversionResult:
    input_path: Path
    sha256: str | None
    status: ConversionStatus
    pdf_path: Path | None
    review_path: Path | None
    diagnostics: tuple[str, ...]


def options_signature(options: ConvertOptions) -> dict:
    style = asdict(options.style)
    style["renderer"] = str(options.style.renderer.resolve()) if options.style.renderer else None
    return {
        "style": style,
        "renderer_callable": f"{options.renderer.__module__}.{options.renderer.__qualname__}",
        "renderer_executable": str(os.environ.get("WEASYPRINT_EXE", "")) if options.renderer is render_pdf else None,
        "kindleunpack_script": str(os.environ.get("KINDLEUNPACK_SCRIPT", "")),
        "decrypt_adapter": (
            f"{type(options.decrypt_adapter).__module__}.{type(options.decrypt_adapter).__qualname__}"
            if options.decrypt_adapter is not None else None
        ),
    }


def _safe_title(title: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")[:90].strip(" .")
    reserved = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
    return "Livro" if not value or value.upper().split(".")[0] in reserved else value


def _name(title: str, source_sha: str, options: ConvertOptions) -> str:
    fingerprint = hashlib.sha256(json.dumps(options_signature(options), sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]
    return f"{_safe_title(title)}--{source_sha[:16]}--{fingerprint}.pdf"


def _publish_no_clobber(source: Path, target: Path, root: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.parent.resolve().is_relative_to(root):
        raise OSError("Diretório de publicação fora do destino.")
    # O arquivo temporário reside no mesmo volume; link falha se o destino existir.
    os.link(source, target)


def convert_one(input_path: Path, output_dir: Path, options: ConvertOptions) -> ConversionResult:
    source = Path(input_path).resolve()
    destination = Path(output_dir).resolve()
    detected = detect_book(source)
    protected = detected.status == "protected_or_unreadable"
    if protected and (options.decrypt_adapter is None or options.credential is None):
        return ConversionResult(source, detected.sha256, "protected_or_unreadable", None, None, (detected.reason,))
    if detected.status != "supported" and not protected:
        status: ConversionStatus = "protected_or_unreadable" if detected.status == "protected_or_unreadable" else "unsupported"
        return ConversionResult(source, detected.sha256, status, None, None, (detected.reason,))
    if not detected.sha256:
        return ConversionResult(source, None, "failed", None, None, ("Hash do arquivo indisponível.",))
    try:
        destination.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".kindle-pdf-", dir=destination) as scratch:
            work = Path(scratch)
            readable_source = source
            if protected:
                assert options.credential is not None
                decrypted = diagnose_protected(source, options.credential, work / "decrypted", options.decrypt_adapter)
                if decrypted.status != "decrypted" or decrypted.output_path is None:
                    return ConversionResult(source, detected.sha256, "protected_or_unreadable", None, None,
                                            (f"Adaptador: {decrypted.status}.",))
                readable_source = decrypted.output_path
            unpacked = unpack_book(readable_source, work / "unpacked")
            book = prepare_book(unpacked)
            filename = _name(book.title, detected.sha256, options)
            target = destination / filename
            review_target = destination / "review" / filename
            if target.exists() or review_target.exists():
                return ConversionResult(source, detected.sha256, "failed", None, None, ("Saída já existe; publicação recusada.",))
            temporary_pdf = work / "output.tmp.pdf"
            produced = Path(options.renderer(book, temporary_pdf, options.style)).resolve()
            if produced != temporary_pdf.resolve() or not produced.is_file():
                raise RenderError("Renderizador não entregou o PDF temporário esperado.")
            validation = validate_pdf(produced, book)
            if validation.status == "invalid":
                return ConversionResult(source, detected.sha256, "failed", None, None, validation.warnings)
            if detect_book(source).sha256 != detected.sha256:
                return ConversionResult(source, detected.sha256, "failed", None, None, ("Arquivo de entrada mudou durante a conversão.",))
            if validation.status == "review_required":
                _publish_no_clobber(produced, review_target, destination)
                return ConversionResult(source, detected.sha256, "review_required", None, review_target, validation.warnings)
            _publish_no_clobber(produced, target, destination)
            return ConversionResult(source, detected.sha256, "converted", target, None, validation.warnings)
    except (UnsafeArchiveError, UnsafeResourceError, UnsafeRenderInputError, InvalidBookError, UnsupportedBookError) as exc:
        return ConversionResult(source, detected.sha256, "unsupported", None, None, (str(exc),))
    except (ExtractionError, ToolUnavailableError, RenderError) as exc:
        return ConversionResult(source, detected.sha256, "failed", None, None, (str(exc),))
    except (OSError, ValueError, RuntimeError):
        return ConversionResult(source, detected.sha256, "failed", None, None, ("Falha ao renderizar ou publicar o PDF.",))
