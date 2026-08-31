from __future__ import annotations

import bw2data as bd
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ecoinvent_regionalizer.core import export, regionalize


class AnalysisTab(QWidget):
    substitutions_ready = pyqtSignal(object, object, list)  # root_activity, substitutions, priority_list

    def __init__(self, priority_widget):
        super().__init__()
        self.project_name: str | None = None
        self.db_name: str | None = None
        self.signature_index: dict | None = None
        self.root_activity = None
        self.substitutions: list[regionalize.FlowSubstitution] = []
        self.priority_widget = priority_widget
        self.priority_widget.changed.connect(self._on_priority_changed)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._search)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(10, 10, 10, 10)

        search_box = QGroupBox("① Pick the root activity  (e.g. paper cup, RER)")
        search_layout = QVBoxLayout(search_box)
        search_layout.setSpacing(6)
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search activity name, e.g. 'paper cup'")
        self.search_edit.returnPressed.connect(self._search)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        search_btn = QPushButton("Search")
        search_btn.setDefault(True)
        search_btn.clicked.connect(self._search)
        search_row.addWidget(self.search_edit)
        search_row.addWidget(search_btn)
        search_layout.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.setMaximumHeight(130)
        self.results_list.itemDoubleClicked.connect(self._select_activity)
        search_layout.addWidget(self.results_list)

        self.selected_label = QLabel("No activity selected.")
        self.selected_label.setStyleSheet("color: #2a6; font-weight: 600;")
        search_layout.addWidget(self.selected_label)
        layout.addWidget(search_box, 0)

        sub_box = QGroupBox("② Input flows — resolved geography per your priority ranking")
        sub_layout = QVBoxLayout(sub_box)
        sub_layout.setSpacing(6)

        controls_row = QHBoxLayout()
        controls_row.addWidget(QLabel("Depth:"))
        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(1, 4)
        self.depth_spin.setValue(1)
        self.depth_spin.setFixedWidth(60)
        self.depth_spin.setToolTip(
            "1 = only this activity's own direct inputs (default).\n"
            "2+ = also walk each resolved input's own inputs, recursively.\n"
            "Deeper levels explore the CHOSEN geography's supply chain "
            "(e.g. digging into 'electricity, US' once that substitution "
            "is made), not the original one.\n"
            "Higher depths can produce a lot of rows on real ecoinvent "
            "data -- capped for safety."
        )
        controls_row.addWidget(self.depth_spin)
        controls_row.addStretch()
        self.resolve_btn = QPushButton("Load exchanges && resolve geography")
        self.resolve_btn.clicked.connect(self._load_and_resolve)
        controls_row.addWidget(self.resolve_btn)
        self.export_btn = QPushButton("Export to CSV")
        self.export_btn.clicked.connect(self._export_csv)
        controls_row.addWidget(self.export_btn)
        sub_layout.addLayout(controls_row)

        self.truncation_label = QLabel("")
        self.truncation_label.setStyleSheet("color: #b33; font-weight: 600;")
        self.truncation_label.setVisible(False)
        sub_layout.addWidget(self.truncation_label)

        self.table_hint_label = QLabel(
            "No flows loaded yet — select an activity above, then click "
            "\"Load exchanges & resolve geography\"."
        )
        self.table_hint_label.setStyleSheet("color: #888; font-style: italic; padding: 20px;")
        self.table_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_layout.addWidget(self.table_hint_label)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Depth", "Flow", "Reference product", "Amount", "Unit",
            "Original geography", "Resolved geography (override)",
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setVisible(False)
        sub_layout.addWidget(self.table)

        layout.addWidget(sub_box, 1)

    def set_connection(self, project_name: str, db_name: str):
        self.project_name = project_name
        self.db_name = db_name
        bd.projects.set_current(project_name)
        self.signature_index = None  # lazy build on first resolve
        self.priority_widget.set_available_locations(regionalize.get_all_locations(db_name))

    def _on_search_text_changed(self, _text: str):
        self._search_timer.start(300)  # debounce so we don't re-query on every keystroke

    def _search(self):
        if not self.db_name:
            return
        term = self.search_edit.text().strip()
        if not term:
            self.results_list.clear()
            return
        results = regionalize.search_activities(self.db_name, term)
        self.results_list.clear()
        for act in results:
            item = QListWidgetItem(f"{act.get('name')} [{act.get('location')}] — {act.get('reference product')}")
            item.setData(Qt.ItemDataRole.UserRole, act.key)
            self.results_list.addItem(item)

    def _select_activity(self, item: QListWidgetItem):
        key = item.data(Qt.ItemDataRole.UserRole)
        self.root_activity = bd.get_activity(key)
        self.selected_label.setText(
            f"Selected: {self.root_activity.get('name')} "
            f"[{self.root_activity.get('location')}] — {self.root_activity.get('reference product')}"
        )

    def _load_and_resolve(self):
        if self.root_activity is None:
            QMessageBox.warning(self, "No activity", "Search and double-click an activity first.")
            return
        if self.signature_index is None:
            self.signature_index = regionalize.build_flow_signature_index(self.db_name)

        priority = self.priority_widget.get_priority()
        max_depth = self.depth_spin.value()
        self.substitutions, truncated = regionalize.build_substitutions(
            self.root_activity, priority, self.signature_index, max_depth=max_depth,
        )
        if truncated:
            self.truncation_label.setText(
                f"Stopped early after {regionalize.MAX_SUBSTITUTION_NODES} flows — "
                f"the tree at this depth is very large. Try a lower depth if you "
                f"need the full picture."
            )
            self.truncation_label.setVisible(True)
        else:
            self.truncation_label.setVisible(False)

        self._render_table()
        self.substitutions_ready.emit(self.root_activity, self.substitutions, priority)

    def _on_priority_changed(self):
        if self.root_activity is not None and self.substitutions:
            self._load_and_resolve()

    def _ordered_rows(self) -> list[regionalize.FlowSubstitution]:
        """
        Reorders the flat (breadth-first) substitution list into depth-first
        tree order, so each flow's children appear directly beneath it in
        the table instead of grouped by level.
        """
        by_parent: dict[tuple, list[regionalize.FlowSubstitution]] = {}
        for s in self.substitutions:
            by_parent.setdefault(s.parent_key, []).append(s)

        ordered = []
        seen: set[tuple] = {self.root_activity.key}

        def visit(parent_key):
            for sub in by_parent.get(parent_key, []):
                ordered.append(sub)
                if sub.chosen_key in seen:
                    continue  # cycle in the technosphere graph -- don't re-descend
                seen.add(sub.chosen_key)
                visit(sub.chosen_key)

        visit(self.root_activity.key)
        return ordered

    def _render_table(self):
        rows = self._ordered_rows()
        self.table.setVisible(bool(rows))
        self.table_hint_label.setVisible(not rows)
        self.table.setRowCount(len(rows))
        for row, sub in enumerate(rows):
            indent = "    " * (sub.depth - 1) + ("↳ " if sub.depth > 1 else "")
            self.table.setItem(row, 0, QTableWidgetItem(str(sub.depth)))
            self.table.setItem(row, 1, QTableWidgetItem(indent + sub.flow_name))
            self.table.setItem(row, 2, QTableWidgetItem(sub.reference_product))
            self.table.setItem(row, 3, QTableWidgetItem(f"{sub.amount:g}"))
            self.table.setItem(row, 4, QTableWidgetItem(sub.unit))
            self.table.setItem(row, 5, QTableWidgetItem(sub.original_location))

            combo = QComboBox()
            options = sub.available_locations
            combo.addItems(options)
            if sub.chosen_location in options:
                combo.setCurrentText(sub.chosen_location)
            elif not options:
                combo.addItem("(no alternative found)")
            combo.currentTextChanged.connect(
                lambda text, s=sub: self._on_override(s, text)
            )
            self.table.setCellWidget(row, 6, combo)

    def _on_override(self, sub: regionalize.FlowSubstitution, text: str):
        if text in sub.candidates:
            sub.chosen_location = text
            sub.manual_override = True

    def _export_csv(self):
        if not self.substitutions:
            QMessageBox.warning(self, "Nothing to export", "Load exchanges first.")
            return
        default_name = f"{(self.root_activity.get('name') or 'flows').replace(' ', '_')}_substitutions.csv"
        path, _ = QFileDialog.getSaveFileName(self, "Export flows to CSV", default_name, "CSV files (*.csv)")
        if not path:
            return
        try:
            export.export_substitutions_csv(self._ordered_rows(), path)
            QMessageBox.information(self, "Exported", f"Saved to {path}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
