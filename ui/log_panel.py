"""操作日志面板 — 查看历史操作记录"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLineEdit, QPushButton, QDateTimeEdit,
)
from PyQt6.QtCore import QDateTime
from logger.op_log import query_logs


LOG_COLUMNS = ["时间", "操作", "设备 MAC", "设备 IP", "详情", "结果"]


class LogPanel(QWidget):
    """操作日志查看面板"""

    def __init__(self):
        super().__init__()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 筛选栏
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("操作类型:"))
        self.op_combo = QComboBox()
        self.op_combo.addItems(["全部", "扫描", "修改IP", "修改密码", "修改配置", "导入", "导出", "启动"])
        filter_layout.addWidget(self.op_combo)

        filter_layout.addWidget(QLabel("设备 MAC:"))
        self.mac_input = QLineEdit()
        self.mac_input.setPlaceholderText("可选")
        self.mac_input.setMaximumWidth(200)
        filter_layout.addWidget(self.mac_input)

        filter_layout.addWidget(QLabel("起始:"))
        self.start_time = QDateTimeEdit()
        self.start_time.setDateTime(QDateTime.currentDateTime().addDays(-7))
        self.start_time.setDisplayFormat("yyyy-MM-dd HH:mm")
        filter_layout.addWidget(self.start_time)

        filter_layout.addWidget(QLabel("结束:"))
        self.end_time = QDateTimeEdit()
        self.end_time.setDateTime(QDateTime.currentDateTime())
        self.end_time.setDisplayFormat("yyyy-MM-dd HH:mm")
        filter_layout.addWidget(self.end_time)

        self.query_btn = QPushButton("查询")
        self.query_btn.clicked.connect(self._query_logs)
        filter_layout.addWidget(self.query_btn)

        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_logs)
        filter_layout.addWidget(self.refresh_btn)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 日志表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(LOG_COLUMNS))
        self.table.setHorizontalHeaderLabels(LOG_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # 日志计数
        self.count_label = QLabel("")
        layout.addWidget(self.count_label)

    def _query_logs(self):
        """查询并显示日志"""
        op = self.op_combo.currentText()
        if op == "全部":
            op = ""
        mac = self.mac_input.text().strip()
        start = self.start_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss")
        end = self.end_time.dateTime().toString("yyyy-MM-ddTHH:mm:ss")

        logs = query_logs(operation=op, device_mac=mac, start_time=start, end_time=end)
        self.table.setRowCount(len(logs))
        for i, log in enumerate(logs):
            ts = log["timestamp"][:19].replace("T", " ")
            self.table.setItem(i, 0, QTableWidgetItem(ts))
            self.table.setItem(i, 1, QTableWidgetItem(log["operation"]))
            self.table.setItem(i, 2, QTableWidgetItem(log["device_mac"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(log["device_ip"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(log["detail"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(log["result"]))

        self.count_label.setText(f"共 {len(logs)} 条记录")

    def refresh_logs(self):
        """刷新日志列表"""
        self.end_time.setDateTime(QDateTime.currentDateTime())
        self._query_logs()
