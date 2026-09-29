import json
from pathlib import Path

from kindle_pdf.cli import main
from tests.book_fixtures import CHAPTER, make_text_epub


def test_cli_emits_one_json_object_for_protected_book(
    tmp_path: Path, capsys
) -> None:
    sample = tmp_path / "book.azw"
    sample.write_bytes(b"DRMION" + b"ProtectedData")

    code = main(["diagnosticar", str(sample)])
    output = capsys.readouterr()
    report = json.loads(output.out)

    assert code == 4
    assert report["status"] == "protected_or_unreadable"
    assert report["format"] == "kindle_drmion"
    assert report["size_bytes"] == sample.stat().st_size
    assert output.err == ""


def test_cli_exit_codes_separate_unsupported_and_invalid(
    tmp_path: Path, capsys
) -> None:
    unknown = tmp_path / "unknown.azw3"
    unknown.write_bytes(b"not a kindle file")
    assert main(["diagnosticar", str(unknown)]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "unsupported_format"

    assert main(["diagnosticar", str(tmp_path / "missing")]) == 3
    assert json.loads(capsys.readouterr().out)["status"] == "invalid_file"


def test_cli_converter_emits_optional_json_summary(tmp_path: Path, capsys) -> None:
    source = make_text_epub(tmp_path / "livro.epub")
    output = tmp_path / "pdfs"

    code = main(["converter", str(source), "--saida", str(output), "--json"])
    printed = capsys.readouterr()
    report = json.loads(printed.out)

    assert code == 0
    assert report["status"] == "converted"
    assert Path(report["pdf_path"]).is_file()
    assert printed.err == ""


def test_cli_converter_pasta_reports_each_item_and_resume(tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "books"
    source_dir.mkdir()
    make_text_epub(source_dir / "a.epub")
    (source_dir / "b.epub").write_bytes(b"invalid")
    make_text_epub(source_dir / "c.epub", {
        "OEBPS/Text/a-capitulo.xhtml": CHAPTER.replace(b"Corpo do capitulo.", b"Texto C."),
    })
    output = tmp_path / "pdfs"

    code = main(["converter-pasta", str(source_dir), "--saida", str(output), "--json"])
    first = json.loads(capsys.readouterr().out)
    assert code == 1
    assert [item["status"] for item in first["results"]] == ["converted", "unsupported", "converted"]

    code_again = main(["converter-pasta", str(source_dir), "--saida", str(output), "--json"])
    second = json.loads(capsys.readouterr().out)
    assert code_again == 1
    assert second["resumed_count"] == 2


def test_cli_windows_adapter_requires_explicit_local_tools(tmp_path: Path, capsys) -> None:
    source = tmp_path / "protected.azw"
    source.write_bytes(b"\xeaDRMION\xeeProtectedData")
    calibre_dir = tmp_path / "calibre"
    output = tmp_path / "pdfs"

    code = main(["converter", str(source), "--saida", str(output), "--json",
                 "--kindle-windows", "--archiver-exe", str(tmp_path / "missing.exe"),
                 "--calibre-dir", str(calibre_dir),
                 "--kfx-input-zip", str(tmp_path / "missing.zip")])
    report = json.loads(capsys.readouterr().out)
    assert code == 4
    assert report["status"] == "protected_or_unreadable"
    assert not list(output.glob("*.pdf"))
