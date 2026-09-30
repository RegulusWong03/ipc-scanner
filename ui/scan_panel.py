"""扫描控制面板 — 卡片容器，网卡选择、IP段输入、扫描控制"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QComboBox, QLineEdit, QLabel, QProgressBar, QFrame,
)
from PyQt6.QtCore import pyqtSignal

from scanner.network import get_network_interfaces, get_scan_range, parse_ip_range


class ScanPanel(QWidget):
    """扫描控制面板（卡片式布局）"""

    scan_requested = pyqtSignal(list, object)  # (ip_list, iface_ip)
    stop_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._interfaces = get_network_interfaces()
        self._init_ui()

    def _init_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        # 卡片容器
        card = QFrame()
        card.setStyleSheet("""
            QFrame#scanCard {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 10px;
                padding: 12px 16px;
            }
        """)
        card.setObjectName("scanCard")

        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # 网卡选择
        nic_label = QLabel("网卡")
        nic_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        layout.addWidget(nic_label)

        self.nic_combo = QComboBox()
        self.nic_combo.setMinimumWidth(200)
        for iface in self._interfaces:
            self.nic_combo.addItem(f"{iface['name']}  {iface['ip']}", iface)
        layout.addWidget(self.nic_combo)

        # 分隔
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #313244;")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

        # IP 段输入
        ip_label = QLabel("IP 段")
        ip_label.setStyleSheet("color: #6c7086; font-size: 12px;")
        layout.addWidget(ip_label)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("留空自动检测，或输入 192.168.1.0/24")
        self.ip_input.setMinimumWidth(240)
        layout.addWidget(self.ip_input)

        layout.addStretch()

        # 扫描按钮
        self.scan_btn = QPushButton("开始扫描")
        self.scan_btn.setFixedWidth(100)
        self.scan_btn.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_btn)

        # 停止按钮
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.setFixedWidth(70)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan)
        layout.addWidget(self.stop_btn)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setFixedWidth(160)
        self.progress.setFixedHeight(24)
        layout.addWidget(self.progress)

        outer_layout.addWidget(card)

    def start_scan(self):
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
        self.stop_requested.emit()
        self.scan_done()

    def update_progress(self, current: int, total: int):
        self.progress.setMaximum(total)
        self.progress.setValue(current)

    def scan_done(self):
        self.scan_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
