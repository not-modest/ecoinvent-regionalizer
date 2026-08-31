import sys

from PyQt6.QtWidgets import QApplication

from ecoinvent_regionalizer import (
    config,  # noqa: F401  (sets BRIGHTWAY_DIR before any bw2data import)
)
from ecoinvent_regionalizer.ui.main_window import MainWindow
from ecoinvent_regionalizer.ui.style import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
