"""The frozen application must still run KindleUnpack in a child process."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from kindle_pdf import unpack
from scripts import portable_app


def test_frozen_kindleunpack_uses_internal_worker(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.azw3"
    source.write_bytes(b"test")
    destination = tmp_path / "output"
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        (destination / "mobi8").mkdir(parents=True)
        (destination / "mobi8" / "content.opf").write_text("<package/>")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(unpack.sys, "frozen", True, raising=False)
    monkeypatch.delenv("KINDLEUNPACK_SCRIPT", raising=False)
    monkeypatch.setattr(unpack.subprocess, "run", fake_run)
    manifest = unpack._unpack_kindle(source, destination)

    assert manifest == destination / "mobi8" / "content.opf"
    worker = str(Path(unpack.sys.executable).with_name("KindlePDF-CLI.exe"))
    assert calls[0][0] == [worker, "--internal-kindleunpack", str(source), str(destination)]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["creationflags"] == unpack.subprocess.CREATE_NO_WINDOW


def test_frozen_worker_calls_vendored_main(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(portable_app.kindleunpack, "main", lambda args: called.append(args) or 0)
    assert portable_app.main(["--internal-kindleunpack", "in.azw3", "out"]) == 0
    assert called == [["kindleunpack", "in.azw3", "out"]]


def test_portable_launcher_dispatches_cli_and_gui(monkeypatch) -> None:
    monkeypatch.setattr(portable_app.cli, "main", lambda argv: ("cli", argv))
    monkeypatch.setattr(portable_app.gui, "launch_gui", lambda: "gui")
    assert portable_app.main(["diagnosticar", "a.epub"]) == ("cli", ["diagnosticar", "a.epub"])
    assert portable_app.main([]) == "gui"


def test_frozen_external_script_override_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(unpack.sys, "frozen", True, raising=False)
    monkeypatch.setenv("KINDLEUNPACK_SCRIPT", str(tmp_path / "other.py"))
    with pytest.raises(unpack.ToolUnavailableError, match="empacotado"):
        unpack._unpack_kindle(tmp_path / "in.azw3", tmp_path / "out")
