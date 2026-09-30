import json
from pathlib import Path

import pytest

from kindle_pdf.batch import convert_batch
from kindle_pdf.pipeline import ConvertOptions
from kindle_pdf.render import PrintStyle
from tests.book_fixtures import CHAPTER, make_text_epub


@pytest.mark.renderer
def test_pipeline_upgrade_reconverts_without_overwriting_previous_pdf(tmp_path, monkeypatch):
    import kindle_pdf.pipeline as pipeline
    import kindle_pdf.batch as batch
    source = make_text_epub(tmp_path / "book.epub")
    output = tmp_path / "pdfs"
    monkeypatch.setattr(pipeline, "PIPELINE_VERSION", "old-validation")
    monkeypatch.setattr(batch, "PIPELINE_VERSION", "old-validation")
    first = convert_batch([source], output, ConvertOptions())
    old_pdf = first.results[0].pdf_path
    before = old_pdf.read_bytes()
    monkeypatch.setattr(pipeline, "PIPELINE_VERSION", "new-validation")
    monkeypatch.setattr(batch, "PIPELINE_VERSION", "new-validation")
    second = convert_batch([source], output, ConvertOptions())
    assert second.resumed_count == 0
    assert second.results[0].status == "converted"
    assert second.results[0].pdf_path != old_pdf
    assert old_pdf.read_bytes() == before


@pytest.mark.renderer
def test_batch_continues_past_invalid_file_and_records_results(tmp_path: Path) -> None:
    first = make_text_epub(tmp_path / "a.epub")
    invalid = tmp_path / "b.epub"
    invalid.write_bytes(b"not an epub")
    last = make_text_epub(tmp_path / "c.epub", {
        "OEBPS/Text/a-capitulo.xhtml": CHAPTER.replace(b"Corpo do capitulo.", b"Outro texto."),
    })
    output = tmp_path / "pdfs"

    batch = convert_batch([first, invalid, last], output, ConvertOptions())

    assert [item.status for item in batch.results] == ["converted", "unsupported", "converted"]
    assert batch.resumed_count == 0
    assert len(list(output.glob("*.pdf"))) == 2
    manifest = json.loads((output / ".kindle-pdf-batch.json").read_text(encoding="utf-8"))
    assert len(manifest["records"]) == 3
    assert "Corpo do capitulo." not in json.dumps(manifest, ensure_ascii=False)
    assert all("input_sha256" in item and "options" in item and "pipeline_version" in item for item in manifest["records"].values())


@pytest.mark.renderer
def test_batch_resumes_only_identical_input_and_options(tmp_path: Path) -> None:
    source = make_text_epub(tmp_path / "livro.epub")
    output = tmp_path / "pdfs"
    first = convert_batch([source], output, ConvertOptions())
    assert first.results[0].status == "converted"
    pdf = first.results[0].pdf_path
    before = pdf.stat().st_mtime_ns

    resumed = convert_batch([source], output, ConvertOptions())
    assert resumed.resumed_count == 1
    assert resumed.results[0].pdf_path == pdf
    assert pdf.stat().st_mtime_ns == before

    changed_style = convert_batch([source], output, ConvertOptions(style=PrintStyle(margin_mm=22)))
    assert changed_style.resumed_count == 0
    assert changed_style.results[0].pdf_path != pdf

    make_text_epub(source, {"OEBPS/Text/a-capitulo.xhtml": CHAPTER.replace(b"Corpo do capitulo.", b"Texto alterado.")})
    changed_input = convert_batch([source], output, ConvertOptions())
    assert changed_input.resumed_count == 0
    assert changed_input.results[0].pdf_path != pdf


@pytest.mark.renderer
def test_batch_does_not_resume_modified_pdf(tmp_path: Path) -> None:
    source = make_text_epub(tmp_path / "livro.epub")
    output = tmp_path / "pdfs"
    first = convert_batch([source], output, ConvertOptions())
    pdf = first.results[0].pdf_path
    pdf.write_bytes(b"modified")

    second = convert_batch([source], output, ConvertOptions())

    assert second.resumed_count == 0
    assert second.results[0].status == "failed"
    assert pdf.read_bytes() == b"modified"


@pytest.mark.renderer
def test_batch_resumes_original_after_options_change(tmp_path: Path) -> None:
    source = make_text_epub(tmp_path / "livro.epub")
    output = tmp_path / "pdfs"
    original = convert_batch([source], output, ConvertOptions())
    alternative = convert_batch([source], output, ConvertOptions(style=PrintStyle(margin_mm=22)))
    again = convert_batch([source], output, ConvertOptions())

    assert alternative.results[0].status == "converted"
    assert again.resumed_count == 1
    assert again.results[0].pdf_path == original.results[0].pdf_path
    assert len(json.loads(again.manifest_path.read_text(encoding="utf-8"))["records"]) == 2


def test_empty_batch_creates_manifest(tmp_path: Path) -> None:
    report = convert_batch([], tmp_path / "pdfs", ConvertOptions())
    assert report.results == ()
    assert report.manifest_path.is_file()
    assert json.loads(report.manifest_path.read_text(encoding="utf-8"))["records"] == {}


def test_batch_emits_progress_after_each_result(tmp_path: Path) -> None:
    first = tmp_path / "a.epub"
    second = tmp_path / "b.epub"
    first.write_bytes(b"invalid")
    second.write_bytes(b"invalid")
    events = []

    def progress(index, total, result):
        events.append((index, total, result.status, len(list((tmp_path / "pdfs").glob(".kindle-pdf-batch.json")))))

    convert_batch([first, second], tmp_path / "pdfs", ConvertOptions(), on_result=progress)
    assert events == [(1, 2, "unsupported", 1), (2, 2, "unsupported", 1)]


def test_batch_cancels_before_next_book_and_keeps_completed_result(tmp_path: Path) -> None:
    books = [tmp_path / "a.epub", tmp_path / "b.epub"]
    for book in books:
        book.write_bytes(b"invalid")
    stop = False

    def on_result(index, total, result):
        nonlocal stop
        stop = True

    report = convert_batch(books, tmp_path / "pdfs", ConvertOptions(),
                           on_result=on_result, should_cancel=lambda: stop)

    assert report.cancelled is True
    assert len(report.results) == 1
    assert report.results[0].input_path == books[0].resolve()
    manifest = json.loads(report.manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["records"]) == 1


def test_batch_cancels_if_requested_during_next_diagnosis(tmp_path: Path, monkeypatch) -> None:
    import kindle_pdf.batch as batch_module

    books = [tmp_path / "a.epub", tmp_path / "b.epub"]
    for book in books:
        book.write_bytes(b"invalid")
    actual_detect = batch_module.detect_book
    stop = False

    def detect_and_cancel(path):
        nonlocal stop
        result = actual_detect(path)
        if Path(path).name == "b.epub":
            stop = True
        return result

    monkeypatch.setattr(batch_module, "detect_book", detect_and_cancel)
    report = convert_batch(books, tmp_path / "pdfs", ConvertOptions(), should_cancel=lambda: stop)

    assert report.cancelled is True
    assert [item.input_path for item in report.results] == [books[0].resolve()]
    assert len(json.loads(report.manifest_path.read_text(encoding="utf-8"))["records"]) == 1
