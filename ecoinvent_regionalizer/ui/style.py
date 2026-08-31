# Colorblind-safe qualitative palette: Okabe-Ito (the first 8, widely used
# in accessible scientific plotting) extended with additional
# well-separated hues for cases with more than 8 categories (real ecoinvent
# activities can have many distinct supplier geographies).
COLORBLIND_PALETTE = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#000000",
    "#999999", "#44AA99", "#882255", "#DDCC77",
    "#117733", "#332288", "#AA4499", "#88CCEE",
]

STYLESHEET = """
QWidget {
    font-size: 13px;
}
QMainWindow {
    background: #f4f5f7;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #d5d8dd;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
    background: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #2c3e50;
}
QTabWidget::pane {
    border: none;
    background: #f4f5f7;
}
QTabBar::tab {
    padding: 8px 18px;
    margin-right: 2px;
    background: #e4e6ea;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #ffffff;
    font-weight: 600;
}
QPushButton {
    padding: 6px 14px;
    border-radius: 5px;
    border: 1px solid #c3c7cd;
    background: #ffffff;
}
QPushButton:hover {
    background: #eef1f5;
}
QPushButton:pressed {
    background: #dfe3e8;
}
QPushButton:disabled {
    color: #9aa0a6;
    background: #f0f1f3;
}
QLineEdit, QComboBox, QSpinBox {
    padding: 4px 6px;
    border: 1px solid #c3c7cd;
    border-radius: 4px;
    background: #ffffff;
}
QTableWidget {
    border: 1px solid #d5d8dd;
    gridline-color: #e6e8eb;
    background: #ffffff;
    alternate-background-color: #f7f8fa;
}
QHeaderView::section {
    background: #eef1f5;
    padding: 5px;
    border: none;
    border-bottom: 1px solid #d5d8dd;
    font-weight: 600;
}
QListWidget {
    border: 1px solid #d5d8dd;
    border-radius: 4px;
    background: #ffffff;
}
QStatusBar {
    background: #e4e6ea;
    border-top: 1px solid #d5d8dd;
}
"""
