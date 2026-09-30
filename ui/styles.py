"""全局样式表"""

APP_STYLESHEET = """
QMainWindow {
    background-color: #f5f5f5;
}

QToolBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e0e0e0;
    padding: 4px;
    spacing: 8px;
}

QToolBar QToolButton {
    background-color: #ffffff;
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 13px;
}

QToolBar QToolButton:hover {
    background-color: #e3f2fd;
    border-color: #2196f3;
}

QTabWidget::pane {
    border: 1px solid #e0e0e0;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    font-size: 13px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    border-bottom-color: #ffffff;
    color: #1976d2;
    font-weight: bold;
}

QTableWidget {
    gridline-color: #e0e0e0;
    border: 1px solid #e0e0e0;
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    font-size: 13px;
}

QTableWidget::item:selected {
    background-color: #e3f2fd;
    color: #000000;
}

QHeaderView::section {
    background-color: #f5f5f5;
    border: 1px solid #e0e0e0;
    padding: 6px;
    font-weight: bold;
    font-size: 12px;
}

QPushButton {
    background-color: #1976d2;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #1565c0;
}

QPushButton:pressed {
    background-color: #0d47a1;
}

QPushButton:disabled {
    background-color: #bdbdbd;
    color: #ffffff;
}

QLineEdit {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 13px;
    background-color: #ffffff;
}

QLineEdit:focus {
    border-color: #2196f3;
}

QComboBox {
    border: 1px solid #d0d0d0;
    border-radius: 4px;
    padding: 6px 8px;
    font-size: 13px;
    background-color: #ffffff;
}

QComboBox:hover {
    border-color: #2196f3;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #1976d2;
}

QTreeWidget {
    border: 1px solid #e0e0e0;
    background-color: #ffffff;
    font-size: 13px;
}

QProgressBar {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    text-align: center;
    background-color: #f5f5f5;
}

QProgressBar::chunk {
    background-color: #4caf50;
    border-radius: 3px;
}

QStatusBar {
    background-color: #f5f5f5;
    border-top: 1px solid #e0e0e0;
    font-size: 12px;
    color: #616161;
}

QMessageBox {
    font-size: 13px;
}

QRadioButton {
    font-size: 13px;
    spacing: 8px;
}
"""
