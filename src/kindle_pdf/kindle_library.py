"""Descoberta limitada à biblioteca local do aplicativo Kindle para Windows."""

from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET


def kindle_content_roots(local_app_data: Path) -> list[Path]:
    packages = Path(local_app_data) / "Packages"
    roots = [package / "LocalState" / "Classic" / "Content"
             for package in packages.glob("AMZNKindle.AmazonKindleReadingApp*")
             if package.is_dir() and not package.is_symlink()]
    return sorted((root for root in roots if root.is_dir() and not root.is_symlink()),
                  key=lambda path: str(path).casefold())


def discover_kindle_books(local_app_data: Path) -> list[Path]:
    """Retorna apenas o arquivo principal de cada pasta de livro completa."""
    books: set[Path] = set()
    for root in kindle_content_roots(local_app_data):
        for folder in root.glob("*_EBOK"):
            if not folder.is_dir() or folder.is_symlink():
                continue
            main = folder / f"{folder.name}.azw"
            if not main.is_file() or main.is_symlink() or main.stat().st_size == 0:
                continue
            with main.open("rb") as stream:
                header = stream.read(16)
            if b"DRMION" in header and not any(folder.glob("*.voucher")):
                continue
            books.add(main.resolve())
    return sorted(books, key=lambda path: str(path).casefold())


def kindle_titles(local_app_data: Path) -> dict[str, str]:
    """Lê somente ASIN e título do cache local mantido pelo Kindle."""
    titles: dict[str, str] = {}
    for content in kindle_content_roots(local_app_data):
        cache = content.parent / "Data" / "Cache" / "KindleSyncMetadataCache.xml"
        try:
            if cache.is_symlink() or cache.stat().st_size > 8 * 1024 * 1024:
                continue
            root = ET.parse(cache).getroot()
        except (OSError, ET.ParseError):
            continue
        for item in root.iter("meta_data"):
            asin = item.findtext("ASIN")
            title = item.findtext("title")
            if asin and title:
                titles[asin.strip()] = title.strip()
    return titles
