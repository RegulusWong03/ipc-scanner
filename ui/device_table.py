"""设备列表视图 — 表格展示 + 分组树 + 搜索过滤 + 右键菜单 + 多选导出"""

import webbrowser
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QMenu, QLabel,
    QTreeWidget, QTreeWidgetItem, QSplitter, QLineEdit,
    QApplication, QInputDialog, QMessageBox, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from device.models import Device, DeviceStatus
from device.storage import update_device_note, update_device_group


COLUMNS = [
    "序号", "IP", "MAC", "品牌", "型号", "序列号", "设备类型",
    "固件版本", "通道数", "运行时间", "HTTP端口", "RTSP端口",
    "设备端口", "子网掩码", "网关", "DHCP", "激活状态",
    "状态", "分组", "备注",
]

# 列索引常量
COL_SEQ = 0
COL_IP = 1
COL_MAC = 2
COL_BRAND = 3
COL_MODEL = 4
COL_SERIAL = 5
COL_DEVICE_TYPE = 6
COL_FIRMWARE = 7
COL_CHANNELS = 8
COL_UPTIME = 9
COL_HTTP_PORT = 10
COL_RTSP_PORT = 11
COL_DEVICE_PORT = 12
COL_SUBNET = 13
COL_GATEWAY = 14
COL_DHCP = 15
COL_ACTIVATED = 16
COL_STATUS = 17
COL_GROUP = 18
COL_NOTE = 19

# 状态颜色映射
STATUS_COLORS = {
    DeviceStatus.ONLINE: QColor("#4caf50"),
    DeviceStatus.OFFLINE: QColor("#9e9e9e"),
    DeviceStatus.NEW: QColor("#2196f3"),
}

# 品牌彩色指示器（用彩色文字前缀代替图标）
BRAND_INDICATORS = {
    "hikvision": ("●", "#e53935"),   # 红色
    "dahua": ("●", "#1e88e5"),       # 蓝色
    "uniview": ("●", "#43a047"),     # 绿色
}
BRAND_DEFAULT_INDICATOR = ("●", "#9e9e9e")  # 灰色


class DeviceTable(QWidget):
    """设备列表，包含分组树 + 设备表格"""

    device_selected = pyqtSignal(object)  # 选中设备
    devices_changed = pyqtSignal()        # 设备数据有修改

    def __init__(self):
        super().__init__()
        self._devices: list[Device] = []
        self._filtered: list[Device] = []
        self._active_group: str | None = None  # 当前选中的分组过滤
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # 左侧：分组树
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderLabel("分组")
        self.group_tree.setMaximumWidth(200)
        self.group_tree.itemClicked.connect(self._on_group_clicked)
        splitter.addWidget(self.group_tree)

        # 右侧：搜索 + 表格
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("搜索:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入 IP / MAC / 品牌 / 型号...")
        self.search_input.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_input)

        # 设备计数
        self.count_label = QLabel("0 台设备")
        search_layout.addWidget(self.count_label)
        right_layout.addLayout(search_layout)

        # 设备表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # IP 和 MAC 列自适应内容宽度
        self.table.horizontalHeader().setSectionResizeMode(COL_IP, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(COL_MAC, QHeaderView.ResizeMode.ResizeToContents)
        # 最后一列（备注）填充剩余空间
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # 支持多选
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.setAlternatingRowColors(True)
        right_layout.addWidget(self.table)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)

    def update_devices(self, devices: list[Device]):
        """设置设备数据源并刷新"""
        self._devices = devices
        self._apply_filter()

    def rebuild_group_tree(self, devices: list[Device]):
        """重建左侧分组树"""
        self.group_tree.clear()

        # "全部" 根节点
        all_item = QTreeWidgetItem(self.group_tree, ["全部"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, None)

        # 按分组聚合
        groups: dict[str, int] = {}
        for d in devices:
            g = d.group or "未分组"
            groups[g] = groups.get(g, 0) + 1

        for name, count in sorted(groups.items()):
            item = QTreeWidgetItem(self.group_tree, [f"{name} ({count})"])
            item.setData(0, Qt.ItemDataRole.UserRole, name if name != "未分组" else "")

        self.group_tree.expandAll()

    def get_selected_devices(self) -> list[Device]:
        """获取当前选中的所有设备（支持多选）"""
        selected = []
        for idx in self.table.selectionModel().selectedRows():
            row = idx.row()
            if 0 <= row < len(self._filtered):
                selected.append(self._filtered[row])
        return selected

    def get_filtered_devices(self) -> list[Device]:
        """获取当前过滤后的设备列表"""
        return self._filtered

    def _apply_filter(self):
        """根据搜索关键字和分组过滤设备，刷新表格"""
        keyword = self.search_input.text().strip().lower()
        result = self._devices

        # 分组过滤
        if self._active_group is not None:
            result = [d for d in result if (d.group or "") == self._active_group]

        # 关键字过滤
        if keyword:
            result = [d for d in result if self._match_keyword(d, keyword)]

        self._filtered = result
        self._refresh_table()

    def _match_keyword(self, d: Device, keyword: str) -> bool:
        """判断设备是否匹配搜索关键字"""
        searchable = " ".join([
            d.ip, d.mac, d.brand, d.model,
            d.firmware_version, d.serial_number,
            d.device_name, d.mac_vendor,
            d.group, d.note,
        ]).lower()
        return keyword in searchable

    def _refresh_table(self):
        """刷新表格显示"""
        devices = self._filtered
        self.table.setRowCount(len(devices))

        for i, d in enumerate(devices):
            self._update_device_row(i, d)

        self.count_label.setText(f"{len(devices)} 台设备")

    def _add_device_row(self, row: int, d: Device):
        """为新增设备添加一行（与 _update_device_row 等价，方便调用方区分语义）"""
        self._update_device_row(row, d)

    def _update_device_row(self, row: int, d: Device):
        """填充或更新指定行的所有列"""
        # 品牌指示器
        brand_key = (d.brand or "").lower()
        indicator, indicator_color = BRAND_INDICATORS.get(brand_key, BRAND_DEFAULT_INDICATOR)
        brand_text = f"{indicator} {d.brand}" if d.brand else indicator

        items = [
            str(row + 1),                             # 序号
            d.ip,
            d.mac,
            brand_text,                                # 品牌（含彩色指示器）
            d.model,
            d.serial_number,
            d.device_type.value,
            d.firmware_version,
            str(d.channels),
            d.uptime,
            str(d.http_port) if d.http_port else "",
            str(d.rtsp_port) if d.rtsp_port else "",
            str(d.device_port) if d.device_port else "",
            d.subnet_mask,
            d.gateway,
            "是" if d.dhcp else "否",
            "已激活" if d.activated else "未激活",
            d.status.value,
            d.group,
            d.note,
        ]

        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            # 品牌列：设置指示器颜色
            if col == COL_BRAND:
                item.setForeground(QColor(indicator_color))
            # 状态列着色
            elif col == COL_STATUS:
                color = STATUS_COLORS.get(d.status)
                if color:
                    item.setForeground(color)
            # DHCP 列着色
            elif col == COL_DHCP:
                item.setForeground(QColor("#4caf50") if d.dhcp else QColor("#9e9e9e"))
            # 激活状态列着色
            elif col == COL_ACTIVATED:
                item.setForeground(QColor("#4caf50") if d.activated else QColor("#ff9800"))
            self.table.setItem(row, col, item)

    def _on_search_changed(self, _text: str):
        self._apply_filter()

    def _on_group_clicked(self, item: QTreeWidgetItem, _column: int):
        """分组树节点点击"""
        group = item.data(0, Qt.ItemDataRole.UserRole)
        self._active_group = group
        self._apply_filter()

    # === 右键菜单 ===

    def _show_context_menu(self, pos):
        device = self._get_selected_device()
        if not device:
            return

        menu = QMenu(self)
        menu.addAction("打开 Web 管理页", self._open_web)
        menu.addAction("实时预览", lambda: self.device_selected.emit(device))
        menu.addSeparator()
        menu.addAction("修改备注", self._edit_note)
        menu.addAction("修改分组", self._edit_group)
        menu.addSeparator()
        menu.addAction("复制 IP", lambda: QApplication.clipboard().setText(device.ip))
        menu.addAction("复制 MAC", lambda: QApplication.clipboard().setText(device.mac))
        menu.addAction("复制 RTSP 地址", lambda: QApplication.clipboard().setText(device.rtsp_url or ""))
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _open_web(self):
        """打开 Web 管理页"""
        device = self._get_selected_device()
        if device and device.ip:
            webbrowser.open(f"http://{device.ip}:{device.port}")

    def _edit_note(self):
        """编辑设备备注"""
        device = self._get_selected_device()
        if not device:
            return

        text, ok = QInputDialog.getText(
            self, "修改备注",
            f"设备: {device.ip} ({device.mac})\n备注:",
            text=device.note,
        )
        if ok:
            device.note = text
            update_device_note(device.mac, text)
            self.devices_changed.emit()

    def _edit_group(self):
        """编辑设备分组"""
        device = self._get_selected_device()
        if not device:
            return

        text, ok = QInputDialog.getText(
            self, "修改分组",
            f"设备: {device.ip} ({device.mac})\n分组 (如 1F-大厅):",
            text=device.group,
        )
        if ok:
            device.group = text
            update_device_group(device.mac, text)
            self.devices_changed.emit()

    # === 选择 ===

    def _get_selected_device(self) -> Device | None:
        """获取当前选中行对应的设备（单选模式）"""
        row = self.table.currentRow()
        if 0 <= row < len(self._filtered):
            return self._filtered[row]
        return None

    def _on_selection_changed(self):
        device = self._get_selected_device()
        if device:
            self.device_selected.emit(device)
