"""Reject a Windows bundle whose GUI is tied to a terminal window."""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def subsystem(path: Path) -> int:
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError(f"Arquivo PE inválido: {path.name}")
        stream.seek(0x3C)
        pe_offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(pe_offset)
        if stream.read(4) != b"PE\0\0":
            raise ValueError(f"Assinatura PE inválida: {path.name}")
        stream.seek(pe_offset + 24 + 68)
        return struct.unpack("<H", stream.read(2))[0]


def main(bundle: Path) -> int:
    expected = {"KindlePDF.exe": 2, "KindlePDF-CLI.exe": 3}
    for name, wanted in expected.items():
        path = bundle / name
        actual = subsystem(path)
        if actual != wanted:
            raise ValueError(f"{name}: subsistema PE {actual}; esperado {wanted}")
        print(f"{name}: subsistema PE {actual}")
    if not (bundle / "_internal").is_dir():
        raise ValueError("Dependências compartilhadas ausentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
