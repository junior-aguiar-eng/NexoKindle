"""Interface de terminal para diagnóstico de arquivos locais."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .detect import detect_book
from .batch import convert_batch
from .drm import SecretInput
from .drm_windows import WindowsKindleAdapter
from .pipeline import ConvertOptions, ConversionResult, convert_one

EXIT_CODES = {
    "supported": 0,
    "unsupported_format": 2,
    "invalid_file": 3,
    "protected_or_unreadable": 4,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kindle-pdf")
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("diagnosticar", help="diagnostica um arquivo sem convertê-lo")
    diagnose.add_argument("caminho", type=Path)
    single = commands.add_parser("converter", help="converte um livro local")
    single.add_argument("caminho", type=Path)
    single.add_argument("--saida", type=Path, required=True)
    single.add_argument("--json", action="store_true")
    _windows_arguments(single)
    folder = commands.add_parser("converter-pasta", help="converte livros de uma pasta")
    folder.add_argument("caminho", type=Path)
    folder.add_argument("--saida", type=Path, required=True)
    folder.add_argument("--json", action="store_true")
    _windows_arguments(folder)
    args = parser.parse_args(argv)

    if args.command == "diagnosticar":
        detection = detect_book(args.caminho)
        print(json.dumps(asdict(detection), ensure_ascii=False, sort_keys=True))
        return EXIT_CODES[detection.status]
    if args.command == "converter":
        result = convert_one(args.caminho, args.saida, _convert_options(args, parser))
        payload = _result_json(result)
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True) if args.json else _human(result))
        return _conversion_exit((result,))
    if not args.caminho.is_dir():
        parser.error("A pasta de entrada não existe.")
    extensions = {".epub", ".azw", ".azw3", ".mobi", ".kfx", ".zip"}
    output = args.saida.resolve()
    paths = sorted((item for item in args.caminho.rglob("*")
                    if item.is_file() and item.suffix.lower() in extensions
                    and not item.resolve().is_relative_to(output)), key=lambda item: str(item).casefold())
    progress = None if args.json else lambda index, total, result: print(f"[{index}/{total}] {_human(result)}", flush=True)
    report = convert_batch(paths, args.saida, _convert_options(args, parser), on_result=progress)
    if args.json:
        print(json.dumps({"results": [_result_json(item) for item in report.results],
                          "resumed_count": report.resumed_count,
                          "manifest_path": str(report.manifest_path)}, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Retomados: {report.resumed_count}; manifesto: {report.manifest_path}")
    return _conversion_exit(report.results)


def _windows_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--kindle-windows", action="store_true", help="usa o adaptador externo do Kindle Windows")
    command.add_argument("--archiver-exe", type=Path)
    command.add_argument("--calibre-dir", type=Path)
    command.add_argument("--kfx-input-zip", type=Path)


def _convert_options(args, parser: argparse.ArgumentParser) -> ConvertOptions:
    if not args.kindle_windows:
        if any((args.archiver_exe, args.calibre_dir, args.kfx_input_zip)):
            parser.error("Use --kindle-windows com os caminhos das ferramentas locais.")
        return ConvertOptions()
    if not all((args.archiver_exe, args.calibre_dir, args.kfx_input_zip)):
        parser.error("--kindle-windows requer --archiver-exe, --calibre-dir e --kfx-input-zip.")
    adapter = WindowsKindleAdapter(
        archiver_exe=args.archiver_exe,
        calibre_customize_exe=args.calibre_dir / "calibre-customize.exe",
        calibre_debug_exe=args.calibre_dir / "calibre-debug.exe",
        kfx_input_zip=args.kfx_input_zip,
    )
    return ConvertOptions(decrypt_adapter=adapter, credential=SecretInput("kindle-windows-local-session"))


def _result_json(result: ConversionResult) -> dict:
    return {"input_path": str(result.input_path), "sha256": result.sha256,
            "status": result.status,
            "pdf_path": str(result.pdf_path) if result.pdf_path else None,
            "review_path": str(result.review_path) if result.review_path else None,
            "diagnostics": list(result.diagnostics)}


def _human(result: ConversionResult) -> str:
    target = result.pdf_path or result.review_path
    return f"{result.input_path.name}: {result.status}" + (f" → {target}" if target else "")


def _conversion_exit(results: tuple[ConversionResult, ...]) -> int:
    statuses = {result.status for result in results}
    if statuses & {"unsupported", "failed"}:
        return 1
    if "protected_or_unreadable" in statuses:
        return 4
    if "review_required" in statuses:
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
