"""全局样式表 — 现代深色主题"""

APP_STYLESHEET = """
/* ===== 全局 ===== */
QMainWindow {
    background-color: #1e1e2e;
    color: #cdd6f4;
}

QWidget {
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ===== 工具栏 ===== */
QToolBar {
    background-color: #181825;
    border: none;
    border-bottom: 2px solid #313244;
    padding: 8px 12px;
    spacing: 8px;
}

QToolBar QToolButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: bold;
}

QToolBar QToolButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QToolBar QToolButton:pressed {
    background-color: #585b70;
}

/* ===== Tab 页签 ===== */
QTabWidget::pane {
    border: 1px solid #313244;
    background-color: #1e1e2e;
    border-radius: 0 0 8px 8px;
}

QTabBar {
    background-color: transparent;
}

QTabBar::tab {
    background-color: #181825;
    color: #6c7086;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 24px;
    margin-right: 2px;
    font-size: 13px;
    font-weight: bold;
}

QTabBar::tab:hover {
    color: #cdd6f4;
    background-color: #1e1e2e;
}

QTabBar::tab:selected {
    color: #89b4fa;
    background-color: #1e1e2e;
    border-bottom: 3px solid #89b4fa;
}

/* ===== 表格 ===== */
QTableWidget {
    gridline-color: #313244;
    border: 1px solid #313244;
    background-color: #1e1e2e;
    alternate-background-color: #181825;
    color: #cdd6f4;
    font-size: 13px;
    selection-background-color: #313244;
    border-radius: 8px;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #252537;
}

QTableWidget::item:selected {
    background-color: #313244;
    color: #cdd6f4;
    border-radius: 4px;
}

QTableWidget::item:hover {
    background-color: #252537;
}

QHeaderView {
    background-color: transparent;
}

QHeaderView::section {
    background-color: #181825;
    color: #89b4fa;
    border: none;
    border-bottom: 2px solid #313244;
    border-right: 1px solid #313244;
    padding: 8px 12px;
    font-weight: bold;
    font-size: 12px;
}

QHeaderView::section:hover {
    background-color: #1e1e2e;
}

/* ===== 按钮 ===== */
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #74c7ec;
}

QPushButton:pressed {
    background-color: #89dceb;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

/* 次要按钮 */
QPushButton[class="secondary"] {
    background-color: #45475a;
    color: #cdd6f4;
}

QPushButton[class="secondary"]:hover {
    background-color: #585b70;
}

/* 危险按钮 */
QPushButton[class="danger"] {
    background-color: #f38ba8;
    color: #1e1e2e;
}

QPushButton[class="danger"]:hover {
    background-color: #eba0ac;
}

/* 成功按钮 */
QPushButton[class="success"] {
    background-color: #a6e3a1;
    color: #1e1e2e;
}

QPushButton[class="success"]:hover {
    background-color: #94e2d5;
}

/* ===== 输入框 ===== */
QLineEdit {
    border: 2px solid #313244;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    background-color: #181825;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
    selection-color: #1e1e2e;
}

QLineEdit:focus {
    border-color: #89b4fa;
}

QLineEdit:hover {
    border-color: #45475a;
}

QLineEdit:disabled {
    background-color: #11111b;
    color: #6c7086;
}

/* ===== 下拉框 ===== */
QComboBox {
    border: 2px solid #313244;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 13px;
    background-color: #181825;
    color: #cdd6f4;
    min-width: 120px;
}

QComboBox:hover {
    border-color: #45475a;
}

QComboBox:focus {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6c7086;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    border: 2px solid #313244;
    border-radius: 6px;
    color: #cdd6f4;
    selection-background-color: #313244;
    selection-color: #89b4fa;
    padding: 4px;
    outline: none;
}

QComboBox QAbstractItemView::item {
    padding: 6px 12px;
    border-radius: 4px;
}

QComboBox QAbstractItemView::item:hover {
    background-color: #313244;
}

/* ===== 分组框 ===== */
QGroupBox {
    font-weight: bold;
    border: 2px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding: 20px 16px 16px 16px;
    background-color: #181825;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 12px;
    color: #89b4fa;
    font-size: 13px;
}

/* ===== 树形控件 ===== */
QTreeWidget {
    border: 1px solid #313244;
    background-color: #181825;
    color: #cdd6f4;
    font-size: 13px;
    border-radius: 8px;
    padding: 4px;
}

QTreeWidget::item {
    padding: 6px 8px;
    border-radius: 4px;
}

QTreeWidget::item:selected {
    background-color: #313244;
    color: #89b4fa;
}

QTreeWidget::item:hover {
    background-color: #252537;
}

QTreeWidget::branch {
    background-color: transparent;
}

/* ===== 进度条 ===== */
QProgressBar {
    border: none;
    border-radius: 6px;
    text-align: center;
    background-color: #313244;
    color: #cdd6f4;
    font-weight: bold;
    font-size: 12px;
    height: 20px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #89b4fa, stop:1 #74c7ec);
    border-radius: 6px;
}

/* ===== 状态栏 ===== */
QStatusBar {
    background-color: #181825;
    border-top: 1px solid #313244;
    color: #6c7086;
    font-size: 12px;
    padding: 4px 8px;
}

QStatusBar::item {
    border: none;
}

/* ===== 单选按钮 ===== */
QRadioButton {
    font-size: 13px;
    spacing: 8px;
    color: #cdd6f4;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid #45475a;
    background-color: #181825;
}

QRadioButton::indicator:checked {
    border-color: #89b4fa;
    background-color: #89b4fa;
}

QRadioButton::indicator:hover {
    border-color: #89b4fa;
}

/* ===== 复选框 ===== */
QCheckBox {
    font-size: 13px;
    spacing: 8px;
    color: #cdd6f4;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #45475a;
    background-color: #181825;
}

QCheckBox::indicator:checked {
    border-color: #89b4fa;
    background-color: #89b4fa;
}

/* ===== 标签 ===== */
QLabel {
    color: #cdd6f4;
    background-color: transparent;
}

QLabel[class="title"] {
    font-size: 16px;
    font-weight: bold;
    color: #89b4fa;
}

QLabel[class="subtitle"] {
    font-size: 12px;
    color: #6c7086;
}

/* ===== 文本编辑区 ===== */
QTextEdit {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #11111b;
    color: #a6adc8;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    padding: 8px;
}

/* ===== 分割条 ===== */
QSplitter::handle {
    background-color: #313244;
    width: 2px;
}

QSplitter::handle:hover {
    background-color: #89b4fa;
}

/* ===== 滚动条 ===== */
QScrollBar:vertical {
    background-color: #181825;
    width: 10px;
    border: none;
    border-radius: 5px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #181825;
    height: 10px;
    border: none;
    border-radius: 5px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ===== 对话框 ===== */
QMessageBox {
    background-color: #1e1e2e;
    font-size: 13px;
}

QMessageBox QLabel {
    color: #cdd6f4;
    min-width: 280px;
}

/* ===== 菜单 ===== */
QMenu {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
    color: #cdd6f4;
}

QMenu::item:selected {
    background-color: #313244;
    color: #89b4fa;
}

QMenu::separator {
    height: 1px;
    background-color: #313244;
    margin: 4px 12px;
}

/* ===== 提示框 ===== */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
}
"""
