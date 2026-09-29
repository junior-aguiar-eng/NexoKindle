"""Small PDF rendering probe for a self-contained application bundle."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import pymupdf


SMOKE_TEXT = "Teste portátil"
SMOKE_HTML = f"""<!doctype html>
<html lang="pt-BR">
  <head><meta charset="utf-8"><title>Teste portátil</title></head>
  <body><h1>{SMOKE_TEXT}</h1><p>PDF local com texto pesquisável.</p></body>
</html>"""


def find_renderer(bundle_root: Path, platform: str = sys.platform) -> Path:
    """Find the local worker without relying on a system installation."""
    worker_name = "weasyprint.exe" if platform == "win32" else "weasyprint"
    executable = Path(
        os.environ.get("WEASYPRINT_EXE")
        or bundle_root / "weasyprint" / worker_name
    )
    if not executable.is_file():
        raise FileNotFoundError(f"Renderizador portátil ausente: {executable}")
    return executable


def make_smoke_pdf(output_path: Path) -> Path:
    """Render and verify one local text page."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    executable = find_renderer(bundle_root)
    with tempfile.TemporaryDirectory(prefix="kindle-pdf-smoke-") as work_dir:
        source = Path(work_dir) / "smoke.html"
        source.write_text(SMOKE_HTML, encoding="utf-8")
        subprocess.run(
            [str(executable), "--allowed-protocols", "file", str(source), str(output_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    with pymupdf.open(output_path) as pdf:
        if len(pdf) != 1 or SMOKE_TEXT not in pdf[0].get_text():
            output_path.unlink(missing_ok=True)
            raise RuntimeError("O PDF portátil não contém o texto esperado.")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prova local de PDF portátil")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = make_smoke_pdf(args.output)
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
