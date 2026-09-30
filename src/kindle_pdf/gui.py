"""Interface gráfica local para seleção, diagnóstico e conversão em lote."""

from __future__ import annotations

from pathlib import Path
import os
import sys
import threading
from typing import Callable, Iterable

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QFileDialog, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from .batch import BatchReport, convert_batch
from .detect import detect_book
from .drm import SecretInput
from .kindle_library import discover_kindle_books, kindle_titles
from .model import Detection
from .pipeline import ConvertOptions, ConversionResult
from .windows_tools import resolve_windows_tools, windows_tools_status

BOOK_EXTENSIONS = {".epub", ".azw", ".azw3", ".mobi", ".kfx", ".kfx-zip", ".zip"}
BatchCallable = Callable[..., BatchReport]
DetectCallable = Callable[[Path], Detection]


def default_output_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA") if sys.platform == "win32" else None
    return (Path(local) if local else Path.home() / "Documents") / "KindlePDF" / "PDFs"


def is_known_synced_dir(path: Path) -> bool:
    destination = Path(path).resolve()
    roots = [Path(value).resolve() for key in ("OneDrive", "OneDriveCommercial",
                                               "OneDriveConsumer", "Dropbox")
             if (value := os.environ.get(key))]
    roots.append((Path.home() / "Dropbox").resolve())
    return any(destination.is_relative_to(root) for root in roots)


def collect_sources(selections: Iterable[Path], output_dir: Path,
                    should_cancel: Callable[[], bool] | None = None) -> list[Path]:
    """Expande somente os caminhos escolhidos, sem procurar dispositivos."""
    output = Path(output_dir).resolve()
    found: set[Path] = set()
    for selected in selections:
        if should_cancel is not None and should_cancel():
            break
        path = Path(selected).resolve()
        candidates = path.rglob("*") if path.is_dir() else (path,)
        for candidate in candidates:
            if should_cancel is not None and should_cancel():
                break
            try:
                resolved = candidate.resolve()
                if (resolved.is_file() and not resolved.is_relative_to(output)
                        and resolved.suffix.lower() in BOOK_EXTENSIONS):
                    found.add(resolved)
            except OSError:
                continue
    return sorted(found, key=lambda item: str(item).casefold())


class SourceScanWorker(QThread):
    paths_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, selections: list[Path], output_dir: Path,
                 scan_fn: Callable[..., list[Path]]) -> None:
        super().__init__()
        self.selections = selections
        self.output_dir = output_dir
        self.scan_fn = scan_fn
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            self.paths_ready.emit(self.scan_fn(self.selections, self.output_dir,
                                               should_cancel=self._cancel.is_set))
        except Exception:
            self.failed.emit("Não foi possível ler a pasta selecionada.")


class ConversionWorker(QThread):
    diagnosed = Signal(str, object)
    progress = Signal(int, int, object)
    batch_done = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[Path], output_dir: Path, options: ConvertOptions,
                 batch_fn: BatchCallable = convert_batch,
                 detect_fn: DetectCallable = detect_book,
                 options_factory: Callable[[list[Detection]], ConvertOptions] | None = None) -> None:
        super().__init__()
        self.paths = paths
        self.output_dir = output_dir
        self.options = options
        self.batch_fn = batch_fn
        self.detect_fn = detect_fn
        self.options_factory = options_factory
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            scanned: list[Path] = []
            detections: list[Detection] = []
            for path in self.paths:
                if self._cancel.is_set():
                    break
                detection = self.detect_fn(path)
                self.diagnosed.emit(str(path), detection)
                detections.append(detection)
                scanned.append(path)
            if self._cancel.is_set():
                self.batch_done.emit(BatchReport((), 0, self.output_dir / ".kindle-pdf-batch.json", True))
                return
            if (any(item.status == "protected_or_unreadable" for item in detections)
                    and is_known_synced_dir(self.output_dir)):
                raise ValueError("Escolha em Configurações uma pasta local fora de sincronização para este livro.")
            options = self.options_factory(detections) if self.options_factory else self.options
            report = self.batch_fn(
                scanned, self.output_dir, options,
                on_result=lambda index, total, result: self.progress.emit(index, total, result),
                should_cancel=self._cancel.is_set,
            )
            self.batch_done.emit(report)
        except ValueError as exc:
            self.failed.emit(str(exc))
        except Exception:
            # Erros de ferramentas externas podem conter material sensível.
            self.failed.emit("Falha no diagnóstico ou na conversão. Verifique os caminhos e tente novamente.")


class KindlePdfWindow(QMainWindow):
    def __init__(self, *, batch_fn: BatchCallable = convert_batch,
                 detect_fn: DetectCallable = detect_book,
                 app_dir: Path | None = None) -> None:
        super().__init__()
        self.batch_fn = batch_fn
        self.detect_fn = detect_fn
        self.app_dir = Path(app_dir) if app_dir is not None else Path(sys.executable).parent
        self.worker: ConversionWorker | None = None
        self.scan_worker: SourceScanWorker | None = None
        self._sources: list[Path] = []
        self._rows: dict[Path, int] = {}
        self._pdfs: dict[Path, Path] = {}
        self._close_pending = False
        self._working = False
        self._scanning = False
        self._clear_after_scan = False
        self.setWindowTitle("Kindle PDF")
        self.resize(760, 420)
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Converter livros para PDF")
        title.setObjectName("title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Escolha um livro já baixado no Kindle ou outro arquivo local."))

        sources_bar = QHBoxLayout()
        self.add_files_button = QPushButton("Outro arquivo")
        self.add_files_button.clicked.connect(self._choose_files)
        sources_bar.addWidget(self.add_files_button)
        self.kindle_button = QPushButton("Selecionar livro")
        self.kindle_button.clicked.connect(self._choose_kindle_book)
        sources_bar.insertWidget(0, self.kindle_button)
        self.add_folder_button = QPushButton("Adicionar pasta ou dispositivo")
        self.add_folder_button.clicked.connect(self._choose_folder)
        self.clear_button = QPushButton("Limpar seleção")
        self.clear_button.clicked.connect(self.clear_sources)
        sources_bar.addStretch()
        layout.addLayout(sources_bar)

        self.selected_label = QLabel("Nenhum livro selecionado")
        layout.addWidget(self.selected_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Arquivo", "Formato", "Status", "PDF"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAcceptDrops(False)
        self.table.viewport().setAcceptDrops(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._update_open_button)
        layout.addWidget(self.table)
        self.table.hide()

        self.output_edit = QLineEdit(str(default_output_dir()))
        self.settings_button = QPushButton("Configurações")
        self.settings_button.clicked.connect(self._choose_output)
        sources_bar.addWidget(self.settings_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Selecione ao menos um livro.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        actions = QHBoxLayout()
        self.open_button = QPushButton("Abrir PDF")
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_selected_pdf)
        actions.addWidget(self.open_button)
        actions.addStretch()
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        actions.addWidget(self.cancel_button)
        self.start_button = QPushButton("Converter")
        self.start_button.clicked.connect(self.start_conversion)
        actions.addWidget(self.start_button)
        layout.addLayout(actions)
        self.setStyleSheet("""
            QMainWindow { background: #f7f8fa; color: #17212d; }
            QLabel#title { font-size: 21px; font-weight: 700; }
            QPushButton { padding: 7px 12px; }
            QTableWidget { background: white; gridline-color: #e3e7ec; }
            QGroupBox { border: 1px solid #d8dee6; border-radius: 6px; margin-top: 8px; padding-top: 10px; }
        """)

    def add_paths(self, paths: Iterable[Path]) -> None:
        if self._working or self._scanning:
            return
        incoming = [Path(path) for path in paths]
        output = Path(self.output_edit.text().strip() or "outputs")
        if any(path.is_dir() for path in incoming):
            self._scanning = True
            self._clear_after_scan = False
            self.scan_worker = SourceScanWorker([*self._sources, *incoming], output, collect_sources)
            self.scan_worker.paths_ready.connect(self._apply_sources)
            self.scan_worker.failed.connect(self._on_scan_failed)
            self.scan_worker.finished.connect(self._on_scan_thread_finished)
            self.add_files_button.setEnabled(False)
            self.add_folder_button.setEnabled(False)
            self.kindle_button.setEnabled(False)
            self.settings_button.setEnabled(False)
            self.start_button.setEnabled(False)
            self.clear_button.setText("Cancelar seleção")
            self.status_label.setText("Lendo a pasta selecionada...")
            self.scan_worker.start()
            return
        self._apply_sources(collect_sources([*self._sources, *incoming], output))

    def _apply_sources(self, paths: list[Path]) -> None:
        self._sources = [] if self._clear_after_scan else paths
        self._rows = {path: index for index, path in enumerate(self._sources)}
        self._pdfs.clear()
        self.table.setRowCount(len(self._sources))
        self.table.setVisible(len(self._sources) > 1)
        for row, path in enumerate(self._sources):
            for column, value in enumerate((str(path), "—", "Aguardando", "")):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.progress_bar.setRange(0, max(1, len(self._sources)))
        self.progress_bar.setValue(0)
        self.status_label.setText(f"{len(self._sources)} livro(s) selecionado(s)." if self._sources else "Selecione ao menos um livro.")
        self.selected_label.setText(self._sources[0].stem if len(self._sources) == 1 else
                                    f"{len(self._sources)} livros selecionados" if self._sources else
                                    "Nenhum livro selecionado")
        if self._sources:
            self.table.selectRow(0)
        self._update_open_button()

    def clear_sources(self) -> None:
        if self._working:
            return
        if self._scanning:
            self._clear_after_scan = True
            if self.scan_worker is not None:
                self.scan_worker.request_cancel()
            self.status_label.setText("Cancelando a leitura da pasta...")
            return
        self._sources.clear()
        self._rows.clear()
        self._pdfs.clear()
        self.table.setRowCount(0)
        self.table.hide()
        self._update_open_button()
        self.selected_label.setText("Nenhum livro selecionado")
        self.status_label.setText("Selecione ao menos um livro.")

    def _choose_files(self) -> None:
        if self._working or self._scanning:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar livros", "", "Livros (*.epub *.azw *.azw3 *.mobi *.kfx *.kfx-zip *.zip);;Todos (*.*)")
        if files:
            self.clear_sources()
            self.add_paths([Path(file) for file in files])

    def _choose_kindle_book(self) -> None:
        if self._working or self._scanning:
            return
        local = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
        books = discover_kindle_books(local)
        if not books:
            self.status_label.setText("Nenhum livro baixado foi encontrado no Kindle para Windows.")
            return
        titles = kindle_titles(local)
        labels = [titles.get(book.parent.name.removesuffix("_EBOK"),
                             book.parent.name.removesuffix("_EBOK")) for book in books]
        if len(set(labels)) != len(labels):
            labels = [f"{label} ({book.parent.name.removesuffix('_EBOK')})"
                      for label, book in zip(labels, books)]
        selected, accepted = QInputDialog.getItem(self, "Livros baixados", "Escolha um livro:", labels, 0, False)
        if accepted:
            self.clear_sources()
            self.add_paths([books[labels.index(selected)]])
            self.selected_label.setText(selected)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta ou dispositivo")
        if folder:
            self.add_paths([Path(folder)])

    def _choose_output(self) -> None:
        if self._working or self._scanning:
            return
        folder = QFileDialog.getExistingDirectory(self, "Selecionar destino dos PDFs")
        if folder:
            self.output_edit.setText(folder)

    def _options_for_detections(self, detections: list[Detection]) -> ConvertOptions:
        protected = [item for item in detections if item.status == "protected_or_unreadable"]
        if not protected:
            return ConvertOptions()
        if any(item.format != "kindle_drmion" for item in protected):
            raise ValueError("A proteção deste formato não é compatível com a conversão automática.")
        if sys.platform != "win32":
            raise ValueError("Este livro exige a integração Kindle para Windows.")
        adapter = resolve_windows_tools(self.app_dir)
        if adapter is None:
            state = windows_tools_status(self.app_dir)
            if state == "incompatible":
                raise ValueError("As ferramentas incluídas não são compatíveis com esta versão do KindlePDF.")
            raise ValueError("Esta instalação não contém as ferramentas necessárias para livros protegidos.")
        return ConvertOptions(decrypt_adapter=adapter,
                              credential=SecretInput("kindle-windows-local-session"))

    def start_conversion(self) -> None:
        if self._working or self._scanning:
            return
        output_text = self.output_edit.text().strip()
        if not output_text:
            self.status_label.setText("Escolha a pasta de destino.")
            return
        destination = Path(output_text).resolve()
        paths = collect_sources(self._sources, destination)
        if not paths:
            self.status_label.setText("Selecione ao menos um livro fora da pasta de destino.")
            return
        self.worker = ConversionWorker(paths, destination, ConvertOptions(), self.batch_fn,
                                       self.detect_fn, self._options_for_detections)
        self.worker.diagnosed.connect(self._on_diagnosed)
        self.worker.progress.connect(self._on_progress)
        self.worker.batch_done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_thread_finished)
        self.progress_bar.setRange(0, len(paths))
        self.progress_bar.setValue(0)
        self.status_label.setText("Diagnosticando os livros selecionados...")
        self._working = True
        self._pdfs.clear()
        self._update_open_button()
        for row in range(self.table.rowCount()):
            self._cell(row, 2).setText("Aguardando")
            self._cell(row, 2).setToolTip("")
            self._cell(row, 3).setText("")
        for button in (self.add_files_button, self.add_folder_button, self.clear_button,
                       self.kindle_button, self.settings_button):
            button.setEnabled(False)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.worker.start()

    def cancel_conversion(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_cancel()
            self.status_label.setText("Cancelamento solicitado; aguardando o livro atual.")

    def _cell(self, row: int, column: int) -> QTableWidgetItem:
        item = self.table.item(row, column)
        if item is None:
            item = QTableWidgetItem()
            self.table.setItem(row, column, item)
        return item

    def _on_diagnosed(self, path: str, detection: Detection) -> None:
        row = self._rows.get(Path(path))
        if row is None:
            return
        self._cell(row, 1).setText(detection.format)
        self._cell(row, 2).setText(detection.status)
        self._cell(row, 2).setToolTip(detection.reason)

    def _on_progress(self, index: int, total: int, result: ConversionResult) -> None:
        row = self._rows.get(result.input_path)
        if row is not None:
            self._pdfs.pop(result.input_path, None)
            self._cell(row, 3).setText("")
            self._cell(row, 2).setText(result.status)
            self._cell(row, 2).setToolTip("; ".join(result.diagnostics))
            pdf = result.pdf_path if result.status == "converted" else None
            if pdf is not None:
                self._pdfs[result.input_path] = pdf
                self._cell(row, 3).setText(str(pdf))
            elif result.review_path is not None:
                self._cell(row, 3).setText(str(result.review_path))
        self.progress_bar.setValue(index)
        self.status_label.setText(f"Processados {index} de {total} livro(s).")
        self._update_open_button()

    def _on_done(self, report: BatchReport) -> None:
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if report.cancelled:
            self.status_label.setText(f"Cancelado após {len(report.results)} de {len(self._sources)} livro(s).")
        elif len(report.results) == 1:
            result = report.results[0]
            if "Adaptador: external_key_cache." in result.diagnostics:
                self.status_label.setText(
                    "Conversão interrompida para proteger o cache de chaves deste Windows. "
                    "Nenhum PDF foi criado.")
                return
            messages = {
                "converted": "PDF pronto. Clique em Abrir PDF.",
                "review_required": "Revisão necessária: o PDF gerado não foi aprovado na validação.",
                "unsupported": "Este livro não é compatível com a conversão atual.",
                "protected_or_unreadable": "Não foi possível converter este livro nesta instalação.",
                "failed": "Falha ao converter este livro. Confira se está baixado por completo.",
            }
            details = "; ".join(dict.fromkeys(result.diagnostics))
            artifact = result.pdf_path or result.review_path
            self.status_label.setText("\n".join(part for part in (
                messages[result.status], details, f"Arquivo: {artifact}" if artifact else "") if part))
        else:
            converted = sum(result.status == "converted" for result in report.results)
            self.status_label.setText(f"{converted} PDF(s) pronto(s) de {len(report.results)} livro(s).")

    def _on_failed(self, message: str) -> None:
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText(message)

    def _on_thread_finished(self) -> None:
        self._working = False
        for button in (self.add_files_button, self.add_folder_button, self.clear_button,
                       self.kindle_button, self.settings_button):
            button.setEnabled(True)
        if self._close_pending:
            self.close()

    def _on_scan_failed(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_scan_thread_finished(self) -> None:
        self._scanning = False
        self.add_files_button.setEnabled(True)
        self.add_folder_button.setEnabled(True)
        self.kindle_button.setEnabled(True)
        self.settings_button.setEnabled(True)
        self.start_button.setEnabled(True)
        self.clear_button.setText("Limpar seleção")
        if self._close_pending:
            self.close()

    def _update_open_button(self) -> None:
        row = self.table.currentRow()
        path = self._sources[row] if 0 <= row < len(self._sources) else None
        self.open_button.setEnabled(path in self._pdfs if path is not None else False)

    def open_selected_pdf(self) -> None:
        row = self.table.currentRow()
        if not 0 <= row < len(self._sources):
            return
        pdf = self._pdfs.get(self._sources[row])
        if pdf is None or not pdf.is_file():
            self.status_label.setText("O PDF selecionado não está disponível.")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(pdf))):
            self.status_label.setText("Não foi possível solicitar a abertura do PDF.")

    def dragEnterEvent(self, event) -> None:
        if self._working or self._scanning:
            event.ignore()
            return
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        if self._working or self._scanning:
            event.ignore()
            return
        self.add_paths(Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        if self._scanning:
            self._close_pending = True
            if self.scan_worker is not None:
                self.scan_worker.request_cancel()
            event.ignore()
            return
        if self._working:
            self._close_pending = True
            self.cancel_conversion()
            event.ignore()
            return
        super().closeEvent(event)


def apply_light_theme(app: QApplication) -> None:
    """Fixa o tema claro: a folha de estilo pinta fundos claros e não cobre o modo escuro."""
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    app.setStyle("Fusion")
    app.setPalette(app.style().standardPalette())


def launch_gui() -> int:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    apply_light_theme(app)
    window = KindlePdfWindow()
    window.show()
    return app.exec()
