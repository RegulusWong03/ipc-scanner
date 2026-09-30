"""导入预览对话框 — 显示导入数据 + 校验结果 + 冲突处理选项"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QGroupBox, QRadioButton, QButtonGroup,
    QTextEdit, QTabWidget, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from export.handlers import validate_import_data


class ImportDialog(QDialog):
    """导入预览对话框

    功能:
    1. 显示导入数据预览（表格形式）
    2. 校验错误行高亮显示
    3. 选择冲突处理方式（跳过/覆盖/全部新增）
    4. 返回用户选择的操作
    """

    # 冲突处理策略
    SKIP_EXISTING = "skip"      # 跳过已存在的设备
    OVERWRITE = "overwrite"     # 覆盖已存在的设备
    ADD_ALL = "add_all"         # 全部作为新设备添加（忽略 MAC 冲突）

    def __init__(self, rows: list[dict], existing_macs: set[str], parent=None):
        """
        Args:
            rows: 导入的数据行
            existing_macs: 当前已存在的设备 MAC 集合
            parent: 父窗口
        """
        super().__init__(parent)
        self.setWindowTitle("导入预览")
        self.setMinimumSize(900, 600)

        self._rows = rows
        self._existing_macs = existing_macs
        self._valid_rows: list[dict] = []
        self._error_rows: list[dict] = []
        self._strategy = self.SKIP_EXISTING
        self._accepted = False

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 统计信息
        self._valid_rows, self._error_rows = validate_import_data(self._rows)

        total = len(self._rows)
        valid = len(self._valid_rows)
        errors = len(self._error_rows)
        new_devices = sum(1 for r in self._valid_rows
                         if r.get("mac", "").lower() not in self._existing_macs)
        existing_devices = valid - new_devices

        stats_text = (
            f"总计 {total} 行 | "
            f"<font color='green'>有效 {valid} 行</font> | "
            f"<font color='red'>错误 {errors} 行</font> | "
            f"新增 {new_devices} 台 | 已存在 {existing_devices} 台"
        )
        stats_label = QLabel(stats_text)
        stats_label.setWordWrap(True)
        layout.addWidget(stats_label)

        # Tab：预览 / 错误
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 预览 Tab
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)

        self.preview_table = QTableWidget()
        columns = ["IP", "MAC", "品牌", "型号", "分组", "备注", "状态"]
        self.preview_table.setColumnCount(len(columns))
        self.preview_table.setHorizontalHeaderLabels(columns)
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_table.setAlternatingRowColors(True)

        self.preview_table.setRowCount(len(self._valid_rows))
        for i, row in enumerate(self._valid_rows):
            mac = row.get("mac", "").lower()
            is_new = mac not in self._existing_macs
            status = "新增" if is_new else "已存在"

            items = [
                row.get("ip", ""),
                row.get("mac", ""),
                row.get("brand", ""),
                row.get("model", ""),
                row.get("group", ""),
                row.get("note", ""),
                status,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                if col == 6:  # 状态列
                    item.setForeground(QColor("#4caf50" if is_new else "#ff9800"))
                self.preview_table.setItem(i, col, item)

        preview_layout.addWidget(self.preview_table)
        tabs.addTab(preview_widget, f"有效数据 ({valid})")

        # 错误 Tab
        if self._error_rows:
            error_widget = QWidget()
            error_layout = QVBoxLayout(error_widget)

            self.error_table = QTableWidget()
            error_columns = ["行号", "IP", "MAC", "错误原因"]
            self.error_table.setColumnCount(len(error_columns))
            self.error_table.setHorizontalHeaderLabels(error_columns)
            self.error_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.error_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

            self.error_table.setRowCount(len(self._error_rows))
            for i, row in enumerate(self._error_rows):
                items = [
                    str(row.get("_row_num", "")),
                    row.get("ip", ""),
                    row.get("mac", ""),
                    row.get("_errors", ""),
                ]
                for col, text in enumerate(items):
                    item = QTableWidgetItem(text)
                    if col == 3:
                        item.setForeground(QColor("#f44336"))
                    self.error_table.setItem(i, col, item)

            error_layout.addWidget(self.error_table)
            tabs.addTab(error_widget, f"错误数据 ({errors})")

        # 冲突处理选项
        conflict_group = QGroupBox("已存在设备的处理方式")
        conflict_layout = QVBoxLayout(conflict_group)
        self.conflict_group = QButtonGroup(self)

        self.radio_skip = QRadioButton("跳过已存在的设备（仅导入新设备）")
        self.radio_skip.setChecked(True)
        self.radio_overwrite = QRadioButton("覆盖已存在的设备（用导入数据更新）")
        self.radio_add_all = QRadioButton("全部作为新设备添加（忽略 MAC 冲突）")

        self.conflict_group.addButton(self.radio_skip)
        self.conflict_group.addButton(self.radio_overwrite)
        self.conflict_group.addButton(self.radio_add_all)

        conflict_layout.addWidget(self.radio_skip)
        conflict_layout.addWidget(self.radio_overwrite)
        conflict_layout.addWidget(self.radio_add_all)
        layout.addWidget(conflict_group)

        # 按钮
        btn_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        self.import_btn = QPushButton(f"导入 {valid} 台设备")
        self.import_btn.clicked.connect(self._on_import_clicked)
        self.import_btn.setEnabled(valid > 0)

        btn_layout.addStretch()
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.import_btn)
        layout.addLayout(btn_layout)

    def _on_import_clicked(self):
        """确认导入"""
        if self.radio_skip.isChecked():
            self._strategy = self.SKIP_EXISTING
        elif self.radio_overwrite.isChecked():
            self._strategy = self.OVERWRITE
        else:
            self._strategy = self.ADD_ALL

        self._accepted = True
        self.accept()

    def get_result(self) -> tuple[list[dict], str]:
        """获取导入结果

        Returns:
            (valid_rows, strategy)
            strategy: "skip" | "overwrite" | "add_all"
        """
        return self._valid_rows, self._strategy
