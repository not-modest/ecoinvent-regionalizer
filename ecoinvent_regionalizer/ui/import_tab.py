from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ecoinvent_regionalizer import config
from ecoinvent_regionalizer.core import bw_setup


class ImportWorker(QThread):
    log_line = pyqtSignal(str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, source_dir: Path, db_name: str, project_name: str):
        super().__init__()
        self.source_dir = source_dir
        self.db_name = db_name
        self.project_name = project_name

    def run(self):
        try:
            bw_setup.import_ecoinvent(
                self.source_dir, self.db_name, self.project_name,
                log=lambda msg: self.log_line.emit(msg),
            )
            self.finished_ok.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class ImportTab(QWidget):
    db_ready = pyqtSignal(str, str)  # project_name, db_name

    def __init__(self):
        super().__init__()
        self.worker: ImportWorker | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        source_box = QGroupBox("① Source")
        source_layout = QVBoxLayout(source_box)
        source_layout.addWidget(QLabel(
            "Download the ecospold2 dataset export from the ecoinvent website, extract it, "
            "and select the folder here (it should contain a 'datasets' folder full of .spold files)."
        ))
        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(config.ECOINVENT_RAW_DIR))
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit)
        path_row.addWidget(browse_btn)
        source_layout.addLayout(path_row)
        layout.addWidget(source_box, 0)

        project_box = QGroupBox("② Brightway project")
        project_layout = QVBoxLayout(project_box)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Project name:"))
        self.project_edit = QLineEdit(config.DEFAULT_BW_PROJECT)
        name_row.addWidget(self.project_edit)
        name_row.addWidget(QLabel("Database name:"))
        self.db_edit = QLineEdit(config.DEFAULT_ECOINVENT_DB)
        name_row.addWidget(self.db_edit)
        project_layout.addLayout(name_row)

        action_row = QHBoxLayout()
        self.import_btn = QPushButton("Import into Brightway")
        self.import_btn.setStyleSheet("font-weight: 600;")
        self.import_btn.clicked.connect(self._start_import)
        action_row.addWidget(self.import_btn)
        self.use_existing_btn = QPushButton("Already imported — just connect")
        self.use_existing_btn.clicked.connect(self._connect_existing)
        action_row.addWidget(self.use_existing_btn)
        project_layout.addLayout(action_row)

        self.clear_btn = QPushButton("Clear project & start fresh")
        self.clear_btn.setStyleSheet("color: #a00; margin-top: 4px;")
        self.clear_btn.clicked.connect(self._clear_project)
        project_layout.addWidget(self.clear_btn)
        layout.addWidget(project_box, 0)

        progress_box = QGroupBox("③ Progress")
        progress_layout = QVBoxLayout(progress_box)
        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.stage_label.setVisible(False)
        progress_layout.addWidget(self.stage_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # indeterminate/busy animation -- we don't
        # get reliable step counts out of bw2io's internal tqdm bars, so this just
        # signals "still working" rather than a percentage.
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        progress_layout.addWidget(self.log)
        layout.addWidget(progress_box, 1)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select ecoinvent export folder", self.path_edit.text())
        if path:
            self.path_edit.setText(path)

    def _append_log(self, msg: str):
        self.log.appendPlainText(msg)
        self.stage_label.setText(msg if len(msg) < 120 else msg[:117] + "...")

    def _set_busy(self, busy: bool):
        self.import_btn.setEnabled(not busy)
        self.use_existing_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        self.stage_label.setVisible(busy)

    def _start_import(self):
        self._set_busy(True)
        self.log.clear()
        self.stage_label.setText("Starting...")
        source = Path(self.path_edit.text())
        self.worker = ImportWorker(source, self.db_edit.text(), self.project_edit.text())
        self.worker.log_line.connect(self._append_log)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _on_finished(self):
        self._append_log("Import complete.")
        self._set_busy(False)
        self.db_ready.emit(self.project_edit.text(), self.db_edit.text())

    def _on_failed(self, msg: str):
        self._append_log(f"ERROR: {msg}")
        self._set_busy(False)

    def _clear_project(self):
        project_name = self.project_edit.text().strip()
        if not project_name:
            return
        reply = QMessageBox.question(
            self,
            "Clear project & start fresh",
            f"This will permanently delete the brightway project '{project_name}' "
            f"and everything in it (biosphere data, LCIA methods, and any imported "
            f"ecoinvent database under this project name) so you can redo Import from "
            f"scratch.\n\nThis cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            existed = bw_setup.delete_project(project_name)
            self.log.clear()
            if existed:
                self._append_log(f"Project '{project_name}' deleted. Ready for a fresh Import.")
            else:
                self._append_log(f"Project '{project_name}' didn't exist — nothing to clear.")
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"ERROR clearing project: {exc}")

    def _connect_existing(self):
        try:
            bw_setup.ensure_project(self.project_edit.text())
            dbs = bw_setup.list_databases(self.project_edit.text())
            if self.db_edit.text() not in dbs:
                self._append_log(f"Database '{self.db_edit.text()}' not found. Available: {dbs}")
                return
            self._append_log(f"Connected to project '{self.project_edit.text()}', database '{self.db_edit.text()}'.")
            self.db_ready.emit(self.project_edit.text(), self.db_edit.text())
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"ERROR: {exc}")
