"""Organiza ferramentas locais num bundle Windows sem instalar no sistema."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from kindle_pdf.windows_tools import TOOL_HASHES, windows_tools_status

ARCHIVER_NAME = "MSIXKFXArchiver_x64_1_25218.exe"
PRIVATE_SUFFIXES = {".azw", ".azw3", ".mobi", ".epub", ".k4i", ".keyfile"}


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_tool_bundle(bundle: Path, *, expected_hashes: tuple[str, str, str, str] = TOOL_HASHES) -> bool:
    tools = Path(bundle) / "tools"
    archiver = tools / ARCHIVER_NAME
    calibre = tools / "Calibre"
    plugin = tools / "KFX Input.zip"
    return (archiver.is_file() and (calibre / "LICENSE").is_file() and plugin.is_file()
            and windows_tools_status(bundle, expected_hashes=expected_hashes) == "ready")


def stage_tool_bundle(bundle: Path, archiver: Path, calibre: Path, plugin: Path,
                      *, expected_hashes: tuple[str, str, str, str] = TOOL_HASHES) -> None:
    bundle = Path(bundle).resolve()
    archiver, calibre, plugin = (Path(path).resolve() for path in (archiver, calibre, plugin))
    if not archiver.is_file() or _hash(archiver) != expected_hashes[0].lower():
        raise ValueError("O hash do arquivador não corresponde à versão validada.")
    if not plugin.is_file() or not calibre.is_dir():
        raise ValueError("Calibre ou KFX Input ausente.")
    if not all((calibre / name).is_file() for name in
               ("calibre-customize.exe", "calibre-debug.exe", "LICENSE")):
        raise ValueError("Pasta do Calibre Portable incompleta.")
    for path, expected in zip((calibre / "calibre-customize.exe", calibre / "calibre-debug.exe", plugin),
                              expected_hashes[1:]):
        if _hash(path) != expected.lower():
            raise ValueError("O hash de uma ferramenta não corresponde à versão validada.")
    samples = calibre / "app" / "resources" / "quick_start"
    if any(path.is_symlink() or
           (path.suffix.lower() in PRIVATE_SUFFIXES and not
            (path.parent == samples and path.suffix.lower() == ".epub"))
           for path in calibre.rglob("*")):
        raise ValueError("Pasta do Calibre contém entrada não permitida.")
    target = bundle / "tools"
    if target.exists():
        raise ValueError("A pasta de ferramentas já existe no bundle.")
    bundle.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".tool-stage-", dir=bundle) as scratch:
        staged = Path(scratch) / "tools"
        staged.mkdir()
        shutil.copy2(archiver, staged / ARCHIVER_NAME)
        shutil.copy2(plugin, staged / "KFX Input.zip")
        shutil.copytree(calibre, staged / "Calibre",
                        ignore=lambda directory, names: [name for name in names
                                if Path(directory) == samples and name.lower().endswith(".epub")])
        if not verify_tool_bundle(staged.parent, expected_hashes=expected_hashes):
            raise ValueError("Pacote de ferramentas incompleto.")
        os.replace(staged, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("archiver", type=Path)
    parser.add_argument("calibre", type=Path)
    parser.add_argument("plugin", type=Path)
    args = parser.parse_args()
    stage_tool_bundle(args.bundle, args.archiver, args.calibre, args.plugin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
