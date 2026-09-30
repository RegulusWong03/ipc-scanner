"""扫描控制面板 — 网卡选择、IP段输入、扫描控制"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton,
    QComboBox, QLineEdit, QLabel, QProgressBar,
)
from PyQt6.QtCore import pyqtSignal

from scanner.network import get_network_interfaces, get_scan_range, parse_ip_range


class ScanPanel(QWidget):
    """扫描控制面板（扁平布局，嵌入主窗口顶部）"""

    scan_requested = pyqtSignal(list, object)  # (ip_list, iface_ip)
    stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._interfaces = get_network_interfaces()
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 网卡选择
        layout.addWidget(QLabel("网卡:"))
        self.nic_combo = QComboBox()
        self.nic_combo.setMinimumWidth(180)
        for iface in self._interfaces:
            self.nic_combo.addItem(f"{iface['name']} ({iface['ip']})", iface)
        layout.addWidget(self.nic_combo)

        # IP 段输入
        layout.addWidget(QLabel("IP 段:"))
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("留空自动检测，或输入 192.168.1.0/24")
        self.ip_input.setMaximumWidth(250)
        layout.addWidget(self.ip_input)

        # 扫描按钮
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_btn)

        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan)
        layout.addWidget(self.stop_btn)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setMaximumWidth(200)
        layout.addWidget(self.progress)

        layout.addStretch()

    def start_scan(self):
        """触发扫描"""
        ip_text = self.ip_input.text().strip()
        iface = self.nic_combo.currentData()
        iface_ip = iface["ip"] if iface else None

        if ip_text:
            ip_list = parse_ip_range(ip_text)
        elif iface:
            ip_list = get_scan_range(iface["ip"], iface["netmask"])
        else:
            ip_list = []

        if not ip_list:
            return

        self.scan_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setMaximum(len(ip_list))
        self.progress.setValue(0)

        self.scan_requested.emit(ip_list, iface_ip)

    def stop_scan(self):
        """停止扫描"""
        self.stop_requested.emit()
        self.scan_done()

    def update_progress(self, current: int, total: int):
        """更新扫描进度"""
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def scan_done(self):
        """扫描完成/停止后恢复 UI"""
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
