"""Fluxo Windows injetável; executáveis reais ficam fora dos testes."""

from contextlib import contextmanager
from pathlib import Path
from zipfile import ZipFile

from kindle_pdf.batch import convert_batch
from kindle_pdf.drm import SecretInput
from kindle_pdf.drm_windows import WindowsKindleAdapter
from kindle_pdf.pipeline import ConvertOptions
from tests.book_fixtures import make_text_epub


def _protected_book(root: Path) -> Path:
    folder = root / "TESTBOOK_EBOK"
    folder.mkdir()
    source = folder / "TESTBOOK.azw"
    source.write_bytes(b"\xeaDRMION\xeeProtectedData")
    (folder / "TESTBOOK.voucher").write_bytes(b"fake voucher")
    return source


@contextmanager
def _local_drive(volume: Path):
    yield volume


def test_windows_chain_converts_one_book_and_cleans_sensitive_workspace(tmp_path: Path) -> None:
    source = _protected_book(tmp_path)
    archiver = tmp_path / "archiver.exe"
    customize = tmp_path / "calibre-customize.exe"
    debug = tmp_path / "calibre-debug.exe"
    plugin = tmp_path / "KFX Input.zip"
    for tool in (archiver, customize, debug, plugin):
        tool.write_bytes(b"test tool")
    calls = []

    def run_command(command, *, cwd, env, timeout):
        calls.append(Path(command[0]).name)
        assert Path(env["TEMP"]).is_relative_to(tmp_path)
        if Path(command[0]) == archiver:
            assert (Path(command[1]) / "TESTBOOK_EBOK" / "TESTBOOK.voucher").is_file()
            archive = Path(command[2]) / "TESTBOOK.kfx-zip"
            with ZipFile(archive, "w") as zipfile:
                zipfile.writestr("book.azw", b"CONT" + b"test")
        elif Path(command[0]) == customize:
            assert command[-1] == str(plugin)
            assert Path(env["CALIBRE_CONFIG_DIRECTORY"]).is_relative_to(tmp_path)
        elif Path(command[0]) == debug:
            make_text_epub(Path(command[-1]))
        return 0

    adapter = WindowsKindleAdapter(
        archiver_exe=archiver, calibre_customize_exe=customize,
        calibre_debug_exe=debug, kfx_input_zip=plugin,
        key_cache_path=tmp_path / "absent-key-cache",
        drive_mapper=_local_drive, run_command=run_command,
        archiver_sha256=None,
    )
    output = tmp_path / "pdfs"
    report = convert_batch([source], output, ConvertOptions(
        decrypt_adapter=adapter, credential=SecretInput("LOCAL-SESSION-ONLY")))

    assert report.results[0].status == "converted"
    assert report.results[0].pdf_path.is_file()
    assert calls == ["archiver.exe", "calibre-customize.exe", "calibre-debug.exe"]
    assert source.read_bytes() == b"\xeaDRMION\xeeProtectedData"
    assert "LOCAL-SESSION-ONLY" not in report.manifest_path.read_text(encoding="utf-8")
    assert not any(path.is_dir() for path in output.glob(".kindle-pdf-*"))
    assert not list(output.rglob("*.k4i"))
    assert not list(output.rglob("*.keyfile"))
    assert not list(output.rglob("*.epub"))
    assert not list(output.rglob("*.kfx-zip"))


def test_windows_chain_rejects_external_key_cache_without_running_tool(tmp_path: Path) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "outside-key-cache"
    key_cache.mkdir()
    (key_cache / "key.pcp").write_bytes(b"fake")
    tools = [tmp_path / name for name in ("archiver.exe", "calibre-customize.exe", "calibre-debug.exe", "KFX Input.zip")]
    for tool in tools:
        tool.write_bytes(b"test tool")
    calls = []

    adapter = WindowsKindleAdapter(
        archiver_exe=tools[0], calibre_customize_exe=tools[1],
        calibre_debug_exe=tools[2], kfx_input_zip=tools[3],
        key_cache_path=key_cache, drive_mapper=_local_drive,
        run_command=lambda *a, **kw: calls.append(a) or 0, archiver_sha256=None,
    )
    result = adapter.decrypt(source, tmp_path / "scratch", SecretInput("LOCAL-SESSION-ONLY"))
    assert result.status == "unsupported"
    assert calls == []


def test_key_cache_is_bound_to_selected_kindle_package(tmp_path: Path, monkeypatch) -> None:
    local = tmp_path / "Local"
    packages = local / "Packages"
    first = packages / "AMZNKindle.AmazonKindleReadingApp_first"
    second = packages / "AMZNKindle.AmazonKindleReadingApp_second"
    for package in (first, second):
        (package / "LocalState" / "Classic" / "Content" / "TEST_EBOK").mkdir(parents=True)
    source = second / "LocalState" / "Classic" / "Content" / "TEST_EBOK" / "TEST_EBOK.azw"
    source.write_bytes(b"EA DRMION data")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    adapter = WindowsKindleAdapter(archiver_exe=tmp_path / "a.exe",
                                  calibre_customize_exe=tmp_path / "b.exe",
                                  calibre_debug_exe=tmp_path / "c.exe",
                                  kfx_input_zip=tmp_path / "d.zip")
    assert adapter._external_key_cache(source) == second / "LocalCache" / "Local" / "Microsoft" / "Crypto" / "PCPKSP"
