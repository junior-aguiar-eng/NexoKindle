from pathlib import Path

import pymupdf
import pytest


@pytest.mark.renderer
def test_smoke_pdf_contains_text(tmp_path: Path) -> None:
    from scripts.portable_smoke import make_smoke_pdf

    output = make_smoke_pdf(tmp_path / "smoke.pdf")

    assert output == tmp_path / "smoke.pdf"
    with pymupdf.open(output) as pdf:
        assert len(pdf) == 1
        assert "Teste portátil" in pdf[0].get_text()


def test_bundled_renderer_uses_platform_filename(tmp_path: Path, monkeypatch) -> None:
    from scripts.portable_smoke import find_renderer

    monkeypatch.delenv("WEASYPRINT_EXE", raising=False)
    renderer = tmp_path / "weasyprint" / "weasyprint"
    renderer.parent.mkdir()
    renderer.write_bytes(b"worker")

    assert find_renderer(tmp_path, platform="linux") == renderer
