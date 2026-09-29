"""Shared entry point for separate Windows GUI and console executables."""

from __future__ import annotations

import sys

from kindle_pdf import cli, gui
from kindle_pdf._vendor.KindleUnpack.lib import kindleunpack


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--internal-kindleunpack":
        if len(args) != 3:
            return 2
        return kindleunpack.main(["kindleunpack", args[1], args[2]])
    if not args:
        return gui.launch_gui()
    return cli.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
