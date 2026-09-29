from pathlib import Path

from kindle_pdf.kindle_library import discover_kindle_books, kindle_content_roots, kindle_titles


def _content(local: Path, package: str) -> Path:
    root = local / "Packages" / package / "LocalState" / "Classic" / "Content"
    root.mkdir(parents=True)
    return root


def test_discovers_complete_books_in_multiple_kindle_packages(tmp_path: Path) -> None:
    first = _content(tmp_path, "AMZNKindle.AmazonKindleReadingApp_one")
    second = _content(tmp_path, "AMZNKindle.AmazonKindleReadingApp_two")
    for root, name in ((first, "BOOK1_EBOK"), (second, "BOOK2_EBOK")):
        folder = root / name
        folder.mkdir()
        (folder / f"{name}.azw").write_bytes(b"EA DRMION data")
        (folder / "amzn1.drm-voucher.v1.test.voucher").write_bytes(b"voucher")
        (folder / "fragment.azw.md").write_bytes(b"metadata")
    (first / "INCOMPLETE_EBOK").mkdir()
    (first / "INCOMPLETE_EBOK" / "INCOMPLETE_EBOK.azw").write_bytes(b"EA DRMION data")

    assert kindle_content_roots(tmp_path) == [first, second]
    assert discover_kindle_books(tmp_path) == [
        first / "BOOK1_EBOK" / "BOOK1_EBOK.azw",
        second / "BOOK2_EBOK" / "BOOK2_EBOK.azw",
    ]


def test_missing_kindle_installation_returns_empty_list(tmp_path: Path) -> None:
    assert discover_kindle_books(tmp_path) == []


def test_titles_come_from_local_kindle_metadata_and_ignore_unknown_ids(tmp_path: Path) -> None:
    root = _content(tmp_path, "AMZNKindle.AmazonKindleReadingApp_one")
    cache = root.parent / "Data" / "Cache" / "KindleSyncMetadataCache.xml"
    cache.parent.mkdir(parents=True)
    cache.write_text("<response><add_update_list>"
                     "<meta_data><ASIN>B123</ASIN><title>Direito civil</title></meta_data>"
                     "<meta_data><ASIN>B456</ASIN><title>Outro livro</title></meta_data>"
                     "</add_update_list></response>", encoding="utf-8")

    assert kindle_titles(tmp_path) == {"B123": "Direito civil", "B456": "Outro livro"}
