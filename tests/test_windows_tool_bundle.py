import hashlib
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.stage_windows_tools import stage_tool_bundle, verify_tool_bundle


def _inputs(root: Path) -> tuple[Path, Path, Path, tuple[str, str, str, str]]:
    archiver = root / "archiver.exe"
    archiver.write_bytes(b"test archiver")
    calibre = root / "Calibre"
    calibre.mkdir()
    (calibre / "calibre-customize.exe").write_bytes(b"customize")
    (calibre / "calibre-debug.exe").write_bytes(b"debug")
    (calibre / "LICENSE").write_text("GPL", encoding="utf-8")
    quick_start = calibre / "app" / "resources" / "quick_start"
    quick_start.mkdir(parents=True)
    (quick_start / "eng.epub").write_bytes(b"upstream example")
    plugin = root / "KFX Input.zip"
    with ZipFile(plugin, "w") as archive:
        archive.writestr("plugin.txt", "test")
    hashes = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        archiver, calibre / "calibre-customize.exe", calibre / "calibre-debug.exe", plugin))
    return archiver, calibre, plugin, hashes


def test_stage_creates_self_contained_relative_layout(tmp_path: Path) -> None:
    archiver, calibre, plugin, digest = _inputs(tmp_path)
    bundle = tmp_path / "moved" / "KindlePDF"

    stage_tool_bundle(bundle, archiver, calibre, plugin, expected_hashes=digest)

    assert verify_tool_bundle(bundle, expected_hashes=digest)
    assert (bundle / "tools" / "Calibre" / "LICENSE").is_file()
    assert not list((bundle / "tools").rglob("*.epub"))
    assert not (tmp_path / "tools").exists()


def test_stage_refuses_unverified_archiver(tmp_path: Path) -> None:
    archiver, calibre, plugin, _digest = _inputs(tmp_path)
    bundle = tmp_path / "KindlePDF"

    with pytest.raises(ValueError, match="hash"):
        stage_tool_bundle(bundle, archiver, calibre, plugin,
                          expected_hashes=("0" * 64, "0" * 64, "0" * 64, "0" * 64))

    assert not (bundle / "tools").exists()
