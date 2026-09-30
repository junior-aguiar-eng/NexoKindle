"""Fluxo Windows injetável; executáveis reais ficam fora dos testes."""

from contextlib import contextmanager
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

from kindle_pdf.batch import convert_batch
from kindle_pdf.drm import SecretInput
from kindle_pdf.drm_windows import WindowsKindleAdapter
from kindle_pdf.pipeline import ConvertOptions
from tests.book_fixtures import make_text_epub


def test_changed_windows_tool_invalidates_conversion_identity(tmp_path):
    from kindle_pdf.pipeline import options_signature
    tools = [tmp_path / name for name in ('archiver.exe', 'customize.exe', 'debug.exe', 'plugin.zip')]
    for tool in tools:
        tool.write_bytes(b"first tool")
    adapter = WindowsKindleAdapter(archiver_exe=tools[0], calibre_customize_exe=tools[1], calibre_debug_exe=tools[2], kfx_input_zip=tools[3])
    options = ConvertOptions(decrypt_adapter=adapter)
    before = options_signature(options)
    tools[3].write_bytes(b"changed plugin")
    assert options_signature(options) != before


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


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
@pytest.mark.renderer
@pytest.mark.parametrize("with_key_cache", [False, True])
def test_windows_chain_converts_one_book_and_cleans_sensitive_workspace(
    tmp_path: Path, with_key_cache: bool,
) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "source-keys"
    profile = tmp_path / "profile-keys"
    if with_key_cache:
        key_cache.mkdir()
        (key_cache / "book.key").write_bytes(b"synthetic key")
        (key_cache / "empty-folder").mkdir()
        profile.mkdir()
        (profile / "unrelated.key").write_bytes(b"existing")
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
            if with_key_cache:
                (profile / "book.key").write_bytes((key_cache / "book.key").read_bytes())
                (profile / "empty-folder").mkdir()
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
        key_cache_path=key_cache, profile_key_cache_path=profile,
        allow_profile_key_copy=True,
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
    if with_key_cache:
        assert (profile / "unrelated.key").read_bytes() == b"existing"
        assert not (profile / "book.key").exists()
        assert not (profile / "empty-folder").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
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
    assert result.status == "external_key_cache"
    assert calls == []


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
@pytest.mark.parametrize("archiver_exit", [0, 1])
def test_profile_key_copy_is_removed_after_archiver(tmp_path: Path, archiver_exit: int) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "source-keys"
    key_cache.mkdir()
    (key_cache / "book.key").write_bytes(b"synthetic key")
    profile = tmp_path / "profile-keys"
    profile.mkdir()
    (profile / "unrelated.key").write_bytes(b"existing")
    tools = [tmp_path / name for name in ("archiver.exe", "calibre-customize.exe", "calibre-debug.exe", "KFX Input.zip")]
    for tool in tools:
        tool.write_bytes(b"test tool")
    calls = []

    def run_command(command, *, cwd, env, timeout):
        calls.append(Path(command[0]).name)
        if Path(command[0]) == tools[0]:
            (profile / "book.key").write_bytes((key_cache / "book.key").read_bytes())
            return archiver_exit
        return 1

    adapter = WindowsKindleAdapter(
        archiver_exe=tools[0], calibre_customize_exe=tools[1], calibre_debug_exe=tools[2],
        kfx_input_zip=tools[3], key_cache_path=key_cache, profile_key_cache_path=profile,
        allow_profile_key_copy=True, drive_mapper=_local_drive, run_command=run_command,
        archiver_sha256=None,
    )
    result = adapter.decrypt(source, tmp_path / "scratch", SecretInput("LOCAL-SESSION-ONLY"))
    assert result.status == ("unsupported" if archiver_exit == 0 else "failed")
    assert calls == ["archiver.exe"]
    assert (profile / "unrelated.key").read_bytes() == b"existing"
    assert not (profile / "book.key").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
def test_profile_key_collision_blocks_archiver(tmp_path: Path) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "source-keys"
    key_cache.mkdir()
    (key_cache / "book.key").write_bytes(b"new")
    profile = tmp_path / "profile-keys"
    profile.mkdir()
    (profile / "book.key").write_bytes(b"existing")
    tools = [tmp_path / name for name in ("archiver.exe", "calibre-customize.exe", "calibre-debug.exe", "KFX Input.zip")]
    for tool in tools:
        tool.write_bytes(b"test tool")
    calls = []
    adapter = WindowsKindleAdapter(
        archiver_exe=tools[0], calibre_customize_exe=tools[1], calibre_debug_exe=tools[2],
        kfx_input_zip=tools[3], key_cache_path=key_cache, profile_key_cache_path=profile,
        allow_profile_key_copy=True, drive_mapper=_local_drive,
        run_command=lambda *a, **kw: calls.append(a) or 0, archiver_sha256=None,
    )
    result = adapter.decrypt(source, tmp_path / "scratch", SecretInput("LOCAL-SESSION-ONLY"))
    assert result.status == "external_key_cache"
    assert calls == []
    assert (profile / "book.key").read_bytes() == b"existing"


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
def test_profile_key_copy_changed_by_other_process_is_not_deleted(tmp_path: Path) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "source-keys"
    key_cache.mkdir()
    (key_cache / "book.key").write_bytes(b"new")
    profile = tmp_path / "profile-keys"
    profile.mkdir()
    tools = [tmp_path / name for name in ("archiver.exe", "calibre-customize.exe", "calibre-debug.exe", "KFX Input.zip")]
    for tool in tools:
        tool.write_bytes(b"test tool")

    def run_command(command, *, cwd, env, timeout):
        (profile / "book.key").write_bytes(b"changed after copying")
        return 1

    adapter = WindowsKindleAdapter(
        archiver_exe=tools[0], calibre_customize_exe=tools[1], calibre_debug_exe=tools[2],
        kfx_input_zip=tools[3], key_cache_path=key_cache, profile_key_cache_path=profile,
        allow_profile_key_copy=True, drive_mapper=_local_drive, run_command=run_command,
        archiver_sha256=None,
    )
    result = adapter.decrypt(source, tmp_path / "scratch", SecretInput("LOCAL-SESSION-ONLY"))
    assert result.status == "external_key_cache"
    assert (profile / "book.key").read_bytes() == b"changed after copying"


@pytest.mark.skipif(sys.platform != "win32", reason="Adaptador disponível somente no Windows")
@pytest.mark.parametrize("fixed_key_exists", [False, True])
def test_archiver_fixed_key_path_is_guarded(tmp_path: Path, fixed_key_exists: bool) -> None:
    source = _protected_book(tmp_path)
    key_cache = tmp_path / "source-keys"
    key_cache.mkdir()
    (key_cache / "book.key").write_bytes(b"synthetic")
    profile = tmp_path / "profile-keys"
    fixed = (profile / "d8c37e00045ea5de98d93811f777d227040edd50"
             / "4111704e63913bc011faadfaf420c7573b17ac83.PCPKEY")
    fixed.parent.mkdir(parents=True)
    if fixed_key_exists:
        fixed.write_bytes(b"previous Windows key")
    tools = [tmp_path / name for name in ("archiver.exe", "calibre-customize.exe", "calibre-debug.exe", "KFX Input.zip")]
    for tool in tools:
        tool.write_bytes(b"test tool")
    calls = []

    def run_command(command, *, cwd, env, timeout):
        calls.append(Path(command[0]).name)
        fixed.write_bytes(b"")
        return 1

    adapter = WindowsKindleAdapter(
        archiver_exe=tools[0], calibre_customize_exe=tools[1], calibre_debug_exe=tools[2],
        kfx_input_zip=tools[3], key_cache_path=key_cache, profile_key_cache_path=profile,
        allow_profile_key_copy=True, drive_mapper=_local_drive, run_command=run_command,
        archiver_sha256=None,
    )
    result = adapter.decrypt(source, tmp_path / "scratch", SecretInput("LOCAL-SESSION-ONLY"))
    assert result.status == ("external_key_cache" if fixed_key_exists else "failed")
    assert calls == ([] if fixed_key_exists else ["archiver.exe"])
    if fixed_key_exists:
        assert fixed.read_bytes() == b"previous Windows key"
    else:
        assert not fixed.exists()


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
