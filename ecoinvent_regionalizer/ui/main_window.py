from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QSplitter, QTabWidget, QVBoxLayout, QWidget

from ecoinvent_regionalizer.ui.about_tab import AboutTab
from ecoinvent_regionalizer.ui.analysis_tab import AnalysisTab
from ecoinvent_regionalizer.ui.import_tab import ImportTab
from ecoinvent_regionalizer.ui.priority_widget import PriorityListWidget
from ecoinvent_regionalizer.ui.results_tab import ResultsTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ecoinvent Geography Regionalizer")
        self.resize(1400, 900)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        self.setCentralWidget(tabs)

        self.about_tab = AboutTab()
        self.import_tab = ImportTab()
        self.priority_widget = PriorityListWidget()
        self.analysis_tab = AnalysisTab(self.priority_widget)
        self.results_tab = ResultsTab()

        analysis_container = QWidget()
        layout = QVBoxLayout(analysis_container)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.analysis_tab)
        splitter.addWidget(self.priority_widget)
        splitter.setSizes([950, 350])
        layout.addWidget(splitter)

        tabs.addTab(self.about_tab, "0. About")
        tabs.addTab(self.import_tab, "1. Setup / Import")
        tabs.addTab(analysis_container, "2. Analysis")
        tabs.addTab(self.results_tab, "3. Results")

        self.connection_label = QLabel("Not connected — set up or connect to a project in the Setup / Import tab.")
        self.connection_label.setStyleSheet("padding: 2px 8px; color: #555;")
        self.statusBar().addWidget(self.connection_label)

        self.import_tab.db_ready.connect(self._on_db_ready)
        self.analysis_tab.substitutions_ready.connect(self.results_tab.set_scenario)

    def _on_db_ready(self, project_name: str, db_name: str):
        self.analysis_tab.set_connection(project_name, db_name)
        self.results_tab.set_project(project_name)
        self.connection_label.setText(f"Connected — project: '{project_name}'   database: '{db_name}'")
