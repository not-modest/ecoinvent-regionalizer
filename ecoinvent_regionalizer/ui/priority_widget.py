from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PriorityListWidget(QWidget):
    """
    Drag-to-reorder ranked list of geography codes, e.g.
    USA -> RNA -> GLO -> RoW -> RER.
    Only offers codes that actually exist in the connected database.
    """
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.available_locations: list[str] = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Geography priority (drag to reorder, highest priority first):"))

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list_widget.model().rowsMoved.connect(lambda *_: self.changed.emit())
        layout.addWidget(self.list_widget)

        add_row = QHBoxLayout()
        self.add_combo = QComboBox()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_selected)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        add_row.addWidget(self.add_combo)
        add_row.addWidget(add_btn)
        add_row.addWidget(remove_btn)
        layout.addLayout(add_row)

    def set_available_locations(self, locations: list[str]):
        self.available_locations = locations
        self.add_combo.clear()
        self.add_combo.addItems(locations)

    def set_priority(self, locations: list[str]):
        self.list_widget.clear()
        for loc in locations:
            self.list_widget.addItem(loc)
        self.changed.emit()

    def get_priority(self) -> list[str]:
        return [self.list_widget.item(i).text() for i in range(self.list_widget.count())]

    def _add_selected(self):
        loc = self.add_combo.currentText()
        if not loc:
            return
        existing = self.get_priority()
        if loc in existing:
            return
        self.list_widget.addItem(loc)
        self.changed.emit()

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))
        self.changed.emit()
