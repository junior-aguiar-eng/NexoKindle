"""Pula testes que dependem de ferramentas locais ausentes neste ambiente."""

import os
from pathlib import Path

import pytest


def _renderer_available() -> bool:
    configured = os.environ.get("WEASYPRINT_EXE")
    return bool(configured) and Path(configured).is_file()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _renderer_available():
        return
    skip = pytest.mark.skip(reason="WEASYPRINT_EXE não aponta para o WeasyPrint v70 local")
    for item in items:
        if item.get_closest_marker("renderer"):
            item.add_marker(skip)
