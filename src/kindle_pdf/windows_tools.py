"""Resolve ferramentas opcionais de uma instalação local autocontida."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import is_zipfile

from .drm_windows import ARCHIVER_25218_SHA256, WindowsKindleAdapter

TOOL_HASHES = (
    ARCHIVER_25218_SHA256,
    "78876fcbc0b7014b65a835fa37fcd43092e24c27b34bfa5654a1145a1669ddc6",
    "9d76517ce9166e5bff5201dddfdd6d45f68fc3b0d9193c7edd7ba73f38a590dc",
    "338809c18e5f9bb721dc3570a64cf6f7add4a1711c8183e6179e90fcbadf3c1d",
)


def _paths(app_dir: Path) -> tuple[Path, Path, Path, Path]:
    root = Path(app_dir).resolve() / "tools"
    return (root / "MSIXKFXArchiver_x64_1_25218.exe",
            root / "Calibre" / "calibre-customize.exe",
            root / "Calibre" / "calibre-debug.exe",
            root / "KFX Input.zip")


def windows_tools_status(app_dir: Path, *, expected_hashes: tuple[str, str, str, str] = TOOL_HASHES) -> str:
    paths = _paths(app_dir)
    if not all(path.is_file() and not path.is_symlink() for path in paths):
        return "missing"
    if not is_zipfile(paths[3]):
        return "incompatible"
    for path, expected in zip(paths, expected_hashes):
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected.lower():
                return "incompatible"
    return "ready"


def resolve_windows_tools(app_dir: Path, *, expected_hashes: tuple[str, str, str, str] = TOOL_HASHES) -> WindowsKindleAdapter | None:
    if windows_tools_status(app_dir, expected_hashes=expected_hashes) != "ready":
        return None
    archiver, customize, debug, plugin = _paths(app_dir)
    return WindowsKindleAdapter(archiver_exe=archiver, calibre_customize_exe=customize,
                                calibre_debug_exe=debug, kfx_input_zip=plugin,
                                archiver_sha256=expected_hashes[0],
                                allow_profile_key_copy=True)
