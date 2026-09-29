"""Interface com núcleo falso: seleção, thread, progresso e cancelamento."""

import os
from pathlib import Path
import sys
import threading
import time
import tomllib

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
pytest.importorskip("PySide6")
from PySide6.QtCore import QMimeData, QThread, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QPushButton, QInputDialog

from kindle_pdf.batch import BatchReport
import kindle_pdf.gui as gui_module
from kindle_pdf.model import Detection
from kindle_pdf.pipeline import ConversionResult
from kindle_pdf.gui import KindlePdfWindow, collect_sources


@pytest.fixture(scope="module")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


def _diagnose(_path: Path) -> Detection:
    return Detection("supported", "epub", "not_detected", 5, "test-hash", "EPUB de teste")


def _wait_until(predicate, timeout_ms=3000):
    deadline = time.monotonic() + timeout_ms / 1000
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate()


def test_collect_sources_expands_local_folder_deduplicates_and_skips_output(tmp_path: Path) -> None:
    folder = tmp_path / "books"
    folder.mkdir()
    first = folder / "a.epub"
    second = folder / "nested" / "b.azw"
    second.parent.mkdir()
    for path in (first, second):
        path.write_bytes(b"book")
    (folder / "ignored.txt").write_text("ignore", encoding="utf-8")
    output = folder / "pdfs"
    output.mkdir()
    (output / "old.epub").write_bytes(b"old")

    selected = collect_sources([folder, first], output)

    assert selected == [first.resolve(), second.resolve()]


def test_main_window_has_one_book_action_and_no_tool_fields(qapp, tmp_path: Path) -> None:
    window = KindlePdfWindow(app_dir=tmp_path)
    visible_buttons = {button.text() for button in window.findChildren(QPushButton) if button.isVisibleTo(window)}
    assert "Selecionar livro" in visible_buttons
    assert "Outro arquivo" in visible_buttons
    assert "Converter" in visible_buttons
    assert not any(field in visible_buttons for field in ("Adicionar pasta ou dispositivo", "Limpar seleção"))
    assert not hasattr(window, "archiver_edit")
    assert not hasattr(window, "calibre_edit")
    assert not hasattr(window, "plugin_edit")
    window.close()


def test_kindle_book_picker_selects_discovered_book(qapp, monkeypatch, tmp_path: Path) -> None:
    book = tmp_path / "BOOK_EBOK" / "BOOK_EBOK.azw"
    book.parent.mkdir()
    book.write_bytes(b"EA DRMION data")
    monkeypatch.setattr(gui_module, "discover_kindle_books", lambda *_: [book])
    monkeypatch.setattr(gui_module, "kindle_titles", lambda *_: {"BOOK": "Livro identificado"})
    seen = []

    def choose(_parent, _title, _label, choices, *_args):
        seen.extend(choices)
        return choices[0], True

    monkeypatch.setattr(QInputDialog, "getItem", choose)
    window = KindlePdfWindow(app_dir=tmp_path)
    window._choose_kindle_book()

    assert len(seen) == 1
    assert seen == ["Livro identificado"]
    assert window._sources == [book.resolve()]
    assert window.selected_label.text() == "Livro identificado"
    window.close()


def test_basic_book_does_not_resolve_protected_tools(qapp, monkeypatch, tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("A rota básica chamou ferramentas protegidas")
    monkeypatch.setattr(gui_module, "resolve_windows_tools", forbidden)
    window = KindlePdfWindow(app_dir=tmp_path, detect_fn=_diagnose)
    window.add_paths([book])
    options = window._options_for_detections([_diagnose(book)])
    assert options.decrypt_adapter is None
    window.close()


def test_unknown_protected_format_does_not_use_kindle_tools(qapp, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gui_module, "resolve_windows_tools", lambda *_: pytest.fail("Kindle tools called"))
    window = KindlePdfWindow(app_dir=tmp_path)
    detection = Detection("protected_or_unreadable", "epub", "protected", 20,
                          "test-hash", "EPUB protegido")
    with pytest.raises(ValueError, match="não é compatível"):
        window._options_for_detections([detection])
    window.close()


@pytest.mark.parametrize("status,expected", [
    ("failed", "Falha"), ("unsupported", "não é compatível"),
    ("review_required", "Revisão necessária"),
])
def test_nonfinal_result_is_visible_and_review_pdf_cannot_open(qapp, tmp_path: Path,
                                                                 status: str, expected: str) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    review = tmp_path / "review.pdf"
    review.write_bytes(b"pdf")
    window = KindlePdfWindow()
    window.add_paths([book])
    result = ConversionResult(book.resolve(), "test-hash", status, None,
                              review if status == "review_required" else None, ())
    window._on_progress(1, 1, result)
    window._on_done(BatchReport((result,), 0, tmp_path / "batch.json"))
    assert expected in window.status_label.text()
    assert not window.open_button.isEnabled()
    window.close()


def test_protected_book_refuses_onedrive_destination(qapp, monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "BOOK_EBOK" / "BOOK_EBOK.azw"
    source.parent.mkdir()
    source.write_bytes(b"EA DRMION data")
    synced = tmp_path / "OneDrive"
    monkeypatch.setenv("OneDrive", str(synced))
    protected = Detection("protected_or_unreadable", "kindle_drmion", "protected", 20,
                          "test-hash", "Livro Kindle protegido")

    def forbidden_batch(*_args, **_kwargs):
        raise AssertionError("Destino sincronizado não pode iniciar a conversão")

    window = KindlePdfWindow(batch_fn=forbidden_batch, detect_fn=lambda _: protected,
                             app_dir=tmp_path)
    window.add_paths([source])
    window.output_edit.setText(str(synced / "PDFs"))
    window.start_conversion()
    _wait_until(lambda: window.worker is not None and not window.worker.isRunning())
    qapp.processEvents()

    assert "sincroniza" in window.status_label.text().lower()
    window.close()


def test_window_runs_selected_batch_off_ui_thread_and_shows_result(qapp, tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    output = tmp_path / "pdfs"
    output.mkdir()
    pdf = output / "book.pdf"
    pdf.write_bytes(b"pdf")
    calls = []

    def fake_batch(paths, destination, options, *, on_result, should_cancel):
        calls.append((paths, destination, QThread.currentThread() is not qapp.thread()))
        result = ConversionResult(paths[0], "test-hash", "converted", pdf, None, ())
        on_result(1, 1, result)
        return BatchReport((result,), 0, destination / ".kindle-pdf-batch.json")

    window = KindlePdfWindow(batch_fn=fake_batch, detect_fn=_diagnose)
    window.add_paths([book])
    window.output_edit.setText(str(output))
    window.start_conversion()
    _wait_until(lambda: not window.worker.isRunning() and window.table.item(0, 2).text() == "converted")

    assert calls == [([book.resolve()], output.resolve(), True)]
    assert window.table.item(0, 1).text() == "epub"
    assert window.table.item(0, 3).text() == str(pdf)
    assert window.start_button.isEnabled()
    window.close()


def test_cancel_stops_before_next_book_and_keeps_first_result(qapp, tmp_path: Path) -> None:
    books = [tmp_path / "a.epub", tmp_path / "b.epub"]
    for book in books:
        book.write_bytes(b"book")
    processed = []

    def fake_batch(paths, destination, options, *, on_result, should_cancel):
        results = []
        for index, path in enumerate(paths, 1):
            if should_cancel():
                break
            processed.append(path)
            result = ConversionResult(path, "test-hash", "unsupported", None, None, ())
            results.append(result)
            on_result(index, len(paths), result)
            if index == 1:
                deadline = time.monotonic() + 2
                while not should_cancel() and time.monotonic() < deadline:
                    time.sleep(0.01)
        return BatchReport(tuple(results), 0, destination / ".kindle-pdf-batch.json",
                           cancelled=len(results) < len(paths))

    window = KindlePdfWindow(batch_fn=fake_batch, detect_fn=_diagnose)
    window.add_paths(books)
    window.output_edit.setText(str(tmp_path / "pdfs"))
    window.start_conversion()
    window.worker.progress.connect(lambda *_: window.cancel_conversion())
    _wait_until(lambda: not window.worker.isRunning() and window.table.item(0, 2).text() == "unsupported"
                and "Cancelado" in window.status_label.text())

    assert processed == [books[0].resolve()]
    assert window.table.item(1, 2).text() == "supported"
    assert "Cancelado" in window.status_label.text()
    window.close()


def test_open_result_uses_local_file_url(qapp, monkeypatch, tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"pdf")
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
    window = KindlePdfWindow(detect_fn=_diagnose)
    window.add_paths([book])
    result = ConversionResult(book.resolve(), "test-hash", "converted", pdf, None, ())
    window._on_progress(1, 1, result)
    window.table.selectRow(0)

    window.open_selected_pdf()

    assert len(opened) == 1
    assert Path(opened[0].toLocalFile()) == pdf
    window.close()


def test_other_file_chooser_and_drop_accept_local_paths(qapp, monkeypatch, tmp_path: Path) -> None:
    folder = tmp_path / "books"
    folder.mkdir()
    first = folder / "a.epub"
    second = folder / "b.azw"
    first.write_bytes(b"book")
    second.write_bytes(b"book")
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(first)], ""))
    window = KindlePdfWindow(detect_fn=_diagnose)
    buttons = {button.text(): button for button in window.findChildren(QPushButton)}

    QTest.mouseClick(buttons["Outro arquivo"], Qt.MouseButton.LeftButton)
    assert window.table.rowCount() == 1

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(first))])

    class DropEvent:
        accepted = False
        def mimeData(self):
            return mime
        def acceptProposedAction(self):
            self.accepted = True
        def ignore(self):
            self.accepted = False

    event = DropEvent()
    window.dragEnterEvent(event)
    assert event.accepted
    window.dropEvent(event)
    assert window.table.rowCount() == 1
    window.clear_sources()
    assert window.table.rowCount() == 0
    window.close()


def test_project_exposes_optional_gui_command() -> None:
    project = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["gui-scripts"]["kindle-pdf-gui"] == "kindle_pdf.gui:launch_gui"
    assert any("PySide6" in dependency for dependency in project["project"]["optional-dependencies"]["gui"])


def test_close_requests_cancel_and_closes_after_worker_stops(qapp, tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    entered = threading.Event()

    def fake_batch(paths, destination, options, *, on_result, should_cancel):
        entered.set()
        deadline = time.monotonic() + 2
        while not should_cancel() and time.monotonic() < deadline:
            time.sleep(0.01)
        return BatchReport((), 0, destination / ".kindle-pdf-batch.json", cancelled=True)

    window = KindlePdfWindow(batch_fn=fake_batch, detect_fn=_diagnose)
    window.add_paths([book])
    window.output_edit.setText(str(tmp_path / "pdfs"))
    window.show()
    window.start_conversion()
    _wait_until(entered.is_set)
    window.close()

    _wait_until(lambda: not window.worker.isRunning())
    _wait_until(lambda: not window.isVisible())
    assert not window.worker.isRunning()


@pytest.mark.skipif(sys.platform != "win32", reason="Integração específica do Windows")
def test_protected_book_chooses_included_tools_automatically(qapp, monkeypatch, tmp_path: Path) -> None:
    adapter = object()
    monkeypatch.setattr(gui_module, "resolve_windows_tools", lambda *_: adapter)
    window = KindlePdfWindow(app_dir=tmp_path)
    protected = Detection("protected_or_unreadable", "kindle_drmion", "protected", 20,
                          "test-hash", "Livro Kindle protegido")

    options = window._options_for_detections([protected])

    assert options.decrypt_adapter is adapter
    assert options.credential is not None
    window.close()


def test_clear_selection_is_disabled_while_worker_runs(qapp, tmp_path: Path) -> None:
    book = tmp_path / "book.epub"
    book.write_bytes(b"book")
    entered = threading.Event()
    release = threading.Event()

    def fake_batch(paths, destination, options, *, on_result, should_cancel):
        entered.set()
        release.wait(2)
        return BatchReport((), 0, destination / ".kindle-pdf-batch.json", cancelled=True)

    window = KindlePdfWindow(batch_fn=fake_batch, detect_fn=_diagnose)
    window.add_paths([book])
    window.output_edit.setText(str(tmp_path / "pdfs"))
    window.start_conversion()
    _wait_until(entered.is_set)

    assert not window.clear_button.isEnabled()
    window.clear_sources()
    assert window.table.rowCount() == 1

    release.set()
    _wait_until(lambda: not window.worker.isRunning())
    _wait_until(window.clear_button.isEnabled)
    window.close()


def test_folder_enumeration_runs_off_the_ui_thread(qapp, monkeypatch, tmp_path: Path) -> None:
    folder = tmp_path / "books"
    folder.mkdir()
    (folder / "book.epub").write_bytes(b"book")
    entered = threading.Event()
    release = threading.Event()
    original_collect = gui_module.collect_sources

    def slow_collect(selections, output_dir, should_cancel=None):
        entered.set()
        release.wait(2)
        return original_collect(selections, output_dir)

    monkeypatch.setattr(gui_module, "collect_sources", slow_collect)
    window = KindlePdfWindow()
    began = time.monotonic()
    window.add_paths([folder])

    assert time.monotonic() - began < 0.4
    _wait_until(entered.is_set)
    assert window.table.rowCount() == 0
    release.set()
    _wait_until(lambda: window.table.rowCount() == 1 and not window._scanning)
    window.close()


def test_folder_scan_can_be_cancelled_without_adding_partial_selection(qapp, monkeypatch, tmp_path: Path) -> None:
    folder = tmp_path / "books"
    folder.mkdir()
    (folder / "book.epub").write_bytes(b"book")
    entered = threading.Event()
    release = threading.Event()
    original_collect = gui_module.collect_sources

    def slow_collect(selections, output_dir, should_cancel=None):
        entered.set()
        release.wait(2)
        return original_collect(selections, output_dir, should_cancel=should_cancel)

    monkeypatch.setattr(gui_module, "collect_sources", slow_collect)
    window = KindlePdfWindow()
    window.add_paths([folder])
    _wait_until(entered.is_set)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(folder / "book.epub"))])

    class DropEvent:
        accepted = None
        def mimeData(self):
            return mime
        def acceptProposedAction(self):
            self.accepted = True
        def ignore(self):
            self.accepted = False

    drop = DropEvent()
    window.dragEnterEvent(drop)
    assert drop.accepted is False
    window.clear_sources()
    release.set()
    _wait_until(lambda: not window._scanning)

    assert window.table.rowCount() == 0
    assert window.start_button.isEnabled()
    window.close()


def test_light_theme_keeps_text_dark_over_light_background(qapp) -> None:
    from PySide6.QtGui import QColor, QPalette

    dark = QPalette()
    dark.setColor(QPalette.ColorRole.WindowText, QColor("white"))
    dark.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
    dark.setColor(QPalette.ColorRole.Window, QColor("#202020"))
    qapp.setPalette(dark)
    gui_module.apply_light_theme(qapp)
    window = KindlePdfWindow()
    palette = window.palette()

    assert palette.color(QPalette.ColorRole.WindowText).lightness() < 100
    assert palette.color(QPalette.ColorRole.Window).lightness() > 200
    assert palette.color(QPalette.ColorRole.ButtonText).lightness() < 100
    window.close()
