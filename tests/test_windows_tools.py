import hashlib
from pathlib import Path
from zipfile import ZipFile

from kindle_pdf.windows_tools import resolve_windows_tools, windows_tools_status


def _tools(app_dir: Path) -> tuple[str, str, str, str]:
    tools = app_dir / "tools"
    (tools / "Calibre").mkdir(parents=True)
    (tools / "MSIXKFXArchiver_x64_1_25218.exe").write_bytes(b"archiver")
    (tools / "Calibre" / "calibre-customize.exe").write_bytes(b"customize")
    (tools / "Calibre" / "calibre-debug.exe").write_bytes(b"debug")
    with ZipFile(tools / "KFX Input.zip", "w") as archive:
        archive.writestr("plugin.txt", "test")
    return tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in (
        tools / "MSIXKFXArchiver_x64_1_25218.exe", tools / "Calibre" / "calibre-customize.exe",
        tools / "Calibre" / "calibre-debug.exe", tools / "KFX Input.zip"))


def test_resolves_complete_tools_relative_to_moved_app(tmp_path: Path) -> None:
    app_dir = tmp_path / "other place" / "KindlePDF"
    expected = _tools(app_dir)

    adapter = resolve_windows_tools(app_dir, expected_hashes=expected)

    assert adapter is not None
    assert adapter.archiver_exe == (app_dir / "tools" / "MSIXKFXArchiver_x64_1_25218.exe").resolve()
    assert adapter.kfx_input_zip == (app_dir / "tools" / "KFX Input.zip").resolve()
    assert adapter.allow_profile_key_copy is True


def test_missing_or_wrong_archiver_is_not_accepted(tmp_path: Path) -> None:
    app_dir = tmp_path / "KindlePDF"
    expected = _tools(app_dir)

    assert resolve_windows_tools(app_dir, expected_hashes=("0" * 64, *expected[1:])) is None
    assert windows_tools_status(app_dir, expected_hashes=("0" * 64, *expected[1:])) == "incompatible"
    (app_dir / "tools" / "KFX Input.zip").unlink()
    assert resolve_windows_tools(app_dir) is None
    assert windows_tools_status(app_dir) == "missing"


def test_modified_calibre_or_plugin_is_rejected(tmp_path: Path) -> None:
    app_dir = tmp_path / "KindlePDF"
    expected = _tools(app_dir)
    (app_dir / "tools" / "Calibre" / "calibre-debug.exe").write_bytes(b"changed")
    assert windows_tools_status(app_dir, expected_hashes=expected) == "incompatible"
