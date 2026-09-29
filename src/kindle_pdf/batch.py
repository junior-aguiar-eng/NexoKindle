"""Conversão sequencial e checkpoint de lote."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Callable

from .detect import detect_book
from .pipeline import PIPELINE_VERSION, ConversionResult, ConvertOptions, convert_one, options_signature


@dataclass(frozen=True, slots=True)
class BatchReport:
    results: tuple[ConversionResult, ...]
    resumed_count: int
    manifest_path: Path
    cancelled: bool = False


def convert_batch(paths: list[Path], output_dir: Path, options: ConvertOptions,
                  on_result: Callable[[int, int, ConversionResult], None] | None = None,
                  should_cancel: Callable[[], bool] | None = None) -> BatchReport:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / ".kindle-pdf-batch.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"schema_version": 1, "records": {}}
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("records"), dict):
        raise ValueError("Manifesto de lote inválido.")
    records = manifest["records"]
    signature = options_signature(options)
    if not manifest_path.exists():
        _save_manifest(manifest_path, manifest)
    results: list[ConversionResult] = []
    resumed = 0
    cancelled = False
    for index, path in enumerate(paths, 1):
        if should_cancel is not None and should_cancel():
            cancelled = True
            break
        source = Path(path).resolve()
        detection = detect_book(source)
        if should_cancel is not None and should_cancel():
            cancelled = True
            break
        key_material = json.dumps([str(source), detection.sha256, signature, PIPELINE_VERSION],
                                  ensure_ascii=False, sort_keys=True)
        key = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        previous = records.get(key)
        reusable = None
        resumable_input = detection.status == "supported" or (
            detection.status == "protected_or_unreadable"
            and options.decrypt_adapter is not None and options.credential is not None
        )
        if (isinstance(previous, dict) and resumable_input
                and previous.get("input_sha256") == detection.sha256
                and previous.get("options") == signature
                and previous.get("pipeline_version") == PIPELINE_VERSION
                and previous.get("status") in {"converted", "review_required"}):
            relative = previous.get("output")
            if isinstance(relative, str):
                candidate = (destination / relative).resolve()
                if candidate.is_relative_to(destination) and candidate.is_file():
                    if _sha256(candidate) == previous.get("output_sha256"):
                        reusable = candidate
        if should_cancel is not None and should_cancel():
            cancelled = True
            break
        if reusable is not None:
            status = previous["status"]
            result = ConversionResult(source, detection.sha256, status,
                                      reusable if status == "converted" else None,
                                      reusable if status == "review_required" else None,
                                      tuple(previous.get("diagnostics", ())))
            resumed += 1
        else:
            result = convert_one(source, destination, options)
        results.append(result)
        artifact = result.pdf_path or result.review_path
        records[key] = {
            "input_sha256": result.sha256,
            "options": signature,
            "pipeline_version": PIPELINE_VERSION,
            "status": result.status,
            "output": artifact.relative_to(destination).as_posix() if artifact else None,
            "output_sha256": _sha256(artifact) if artifact else None,
            "diagnostics": list(result.diagnostics),
        }
        _save_manifest(manifest_path, manifest)
        if on_result is not None:
            on_result(index, len(paths), result)
    return BatchReport(tuple(results), resumed, manifest_path, cancelled)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _save_manifest(target: Path, manifest: dict) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".kindle-pdf-batch-",
                                         suffix=".tmp", dir=target.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(manifest, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
