"""主窗口 — 应用入口界面，协调各子面板与后端引擎"""

import logging

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QToolBar, QTabWidget, QFileDialog, QMessageBox,
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from ui.scan_panel import ScanPanel
from ui.device_table import DeviceTable
from ui.config_panel import ConfigPanel
from ui.batch_panel import BatchPanel
from ui.preview_panel import PreviewPanel
from ui.log_panel import LogPanel
from ui.import_dialog import ImportDialog
from scanner.discovery import DeviceDiscoveryThread
from device.storage import init_db, save_device, load_devices
from device.models import Device, DeviceStatus
from logger.op_log import init_log_db, log_operation
from export.handlers import (
    export_excel, export_csv, import_excel, import_csv, generate_template
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IPC/NVR 扫描管理工具")
        self.setMinimumSize(1200, 800)

        # 后端状态
        self._devices: list[Device] = []
        self._discovery_thread: DeviceDiscoveryThread | None = None

        # 初始化数据库
        init_db()
        init_log_db()

        # 从 SQLite 加载历史设备
        self._devices = load_devices()

        self._init_ui()

        # 用历史数据刷新界面
        self.device_table.update_devices(self._devices)
        self._rebuild_group_tree()

        log_operation("启动", detail="应用程序启动")

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)

        # 工具栏
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.scan_action = QAction("扫描设备", self)
        toolbar.addAction(self.scan_action)
        toolbar.addSeparator()

        # 导入/导出相关
        self.import_action = QAction("导入", self)
        self.import_action.triggered.connect(self._import_devices)
        toolbar.addAction(self.import_action)

        self.export_action = QAction("导出全部", self)
        self.export_action.triggered.connect(self._export_devices)
        toolbar.addAction(self.export_action)

        self.export_selected_action = QAction("导出选中", self)
        self.export_selected_action.triggered.connect(self._export_selected_devices)
        toolbar.addAction(self.export_selected_action)

        self.template_action = QAction("下载模板", self)
        self.template_action.triggered.connect(self._download_template)
        toolbar.addAction(self.template_action)

        # 主体布局：扫描面板在上，Tab 在下
        self.scan_panel = ScanPanel()
        layout.addWidget(self.scan_panel)

        # Tab 布局
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        # 设备列表页
        self.device_table = DeviceTable()
        self.tabs.addTab(self.device_table, "设备列表")

        # 网络配置页（单设备）
        self.config_panel = ConfigPanel()
        self.tabs.addTab(self.config_panel, "网络配置")

        # 批量操作页
        self.batch_panel = BatchPanel(get_devices_fn=lambda: self._devices)
        self.tabs.addTab(self.batch_panel, "批量操作")

        # 实时预览页
        self.preview_panel = PreviewPanel()
        self.tabs.addTab(self.preview_panel, "实时预览")

        # 操作日志页
        self.log_panel = LogPanel()
        self.tabs.addTab(self.log_panel, "操作日志")

        # 状态栏
        self.statusBar().showMessage(f"已加载 {len(self._devices)} 台历史设备")

        # === 信号连接 ===

        # 扫描
        self.scan_panel.scan_requested.connect(self._on_scan_requested)
        self.scan_action.triggered.connect(self.scan_panel.start_scan)
        self.scan_panel.stop_requested.connect(self._on_stop_scan)

        # 设备选中 -> 配置面板 + 预览面板
        self.device_table.device_selected.connect(self._on_device_selected)

        # 设备列表变更（备注/分组编辑）
        self.device_table.devices_changed.connect(self._on_devices_changed)

        # 配置面板
        self.config_panel.config_applied.connect(self._on_config_applied)
        self.config_panel.password_changed.connect(self._on_password_changed)

        # 批量操作完成
        self.batch_panel.batch_completed.connect(self._on_batch_completed)

        # Tab 切换时刷新日志
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # === 扫描流程 ===

    def _on_scan_requested(self, ip_list: list[str], iface_ip: str | None):
        """启动扫描线程"""
        if self._discovery_thread and self._discovery_thread.isRunning():
            return

        self.statusBar().showMessage(f"正在扫描 {len(ip_list)} 个地址...")

        for d in self._devices:
            d.status = DeviceStatus.OFFLINE

        self._discovery_thread = DeviceDiscoveryThread(
            ip_list=ip_list,
            iface_ip=iface_ip,
            enable_onvif_detail=False,
        )
        self._discovery_thread.device_found.connect(self._on_device_found)
        self._discovery_thread.scan_finished.connect(self._on_scan_finished)
        self._discovery_thread.scan_progress.connect(self._on_scan_progress)
        self._discovery_thread.scan_error.connect(self._on_scan_error)
        self._discovery_thread.start()

    def _on_stop_scan(self):
        if self._discovery_thread and self._discovery_thread.isRunning():
            self._discovery_thread.stop()
            self.statusBar().showMessage("扫描已停止")

    def _on_device_found(self, info: dict):
        mac = info.get("mac", "")
        if not mac:
            return

        existing = next((d for d in self._devices if d.mac == mac), None)

        if existing:
            if existing.ip != info.get("ip", ""):
                old_ip = existing.ip
                existing.ip = info.get("ip", existing.ip)
                existing.subnet_mask = info.get("subnet", existing.subnet_mask)
                existing.gateway = info.get("gateway", existing.gateway)
                log_operation("IP变更", device_mac=mac, device_ip=existing.ip,
                              detail=f"{old_ip} -> {existing.ip}")
            existing.status = DeviceStatus.ONLINE
            existing.firmware_version = info.get("firmware", existing.firmware_version)
            existing.model = info.get("model", existing.model)
            existing.brand = info.get("brand", existing.brand)
        else:
            device = self._build_device_from_info(info)
            device.status = DeviceStatus.NEW
            self._devices.append(device)
            log_operation("扫描", device_mac=mac, device_ip=device.ip,
                          detail=f"发现新设备 {device.brand} {device.model}")

        self._save_and_refresh()

    def _on_scan_finished(self, result: list):
        self.scan_panel.scan_done()
        self._save_and_refresh()
        self._rebuild_group_tree()

        online_count = sum(1 for d in self._devices if d.status == DeviceStatus.ONLINE)
        new_count = sum(1 for d in self._devices if d.status == DeviceStatus.NEW)
        self.statusBar().showMessage(
            f"扫描完成：{len(self._devices)} 台设备，{online_count} 台在线，{new_count} 台新上线"
        )
        log_operation("扫描", detail=f"扫描完成，发现 {online_count} 台在线设备")

    def _on_scan_progress(self, current: int, total: int):
        self.scan_panel.update_progress(current, total)
        self.statusBar().showMessage(f"端口扫描中... {current}/{total}")

    def _on_scan_error(self, error: str):
        logger.error("扫描出错: %s", error)
        self.statusBar().showMessage(f"扫描出错: {error}")

    def _build_device_from_info(self, info: dict) -> Device:
        from datetime import datetime
        from device.models import DeviceType

        device_type_str = info.get("device_type", "UNKNOWN")
        try:
            device_type = DeviceType(device_type_str)
        except ValueError:
            device_type = DeviceType.UNKNOWN

        channels = info.get("digital_channels", 0) or info.get("channels", 0)

        return Device(
            mac=info.get("mac", ""),
            ip=info.get("ip", ""),
            subnet_mask=info.get("subnet", ""),
            gateway=info.get("gateway", ""),
            port=info.get("http_port", 80),
            device_type=device_type,
            brand=info.get("brand", ""),
            model=info.get("model", ""),
            firmware_version=info.get("firmware", ""),
            serial_number=info.get("serial", ""),
            channels=channels,
            status=DeviceStatus.ONLINE,
            dhcp=info.get("dhcp", False),
            first_seen=datetime.now(),
            last_seen=datetime.now(),
        )

    # === 设备操作 ===

    def _on_device_selected(self, device: Device):
        self.config_panel.set_device(device)
        self.preview_panel.set_device(device)

    def _on_devices_changed(self):
        self._save_and_refresh()
        self._rebuild_group_tree()

    def _on_config_applied(self, device: Device, result: dict):
        if result.get("success"):
            device.ip = self.config_panel.ip_input.text().strip()
            device.subnet_mask = self.config_panel.mask_input.text().strip()
            device.gateway = self.config_panel.gateway_input.text().strip()
            device.dhcp = self.config_panel.radio_dhcp.isChecked()
            self._save_and_refresh()
            log_operation("修改配置", device_mac=device.mac, device_ip=device.ip,
                          detail=f"IP={device.ip} DHCP={'是' if device.dhcp else '否'}",
                          result="success")
        else:
            log_operation("修改配置", device_mac=device.mac, device_ip=device.ip,
                          detail=result.get("message", ""), result="failed")

    def _on_password_changed(self, device: Device, result: dict):
        if result.get("success"):
            log_operation("修改密码", device_mac=device.mac, device_ip=device.ip,
                          result="success")
        else:
            log_operation("修改密码", device_mac=device.mac, device_ip=device.ip,
                          detail=result.get("message", ""), result="failed")

    def _on_batch_completed(self, result: dict):
        """批量操作完成回调"""
        s = result.get("success", 0)
        f = result.get("failed", 0)
        skip = result.get("skipped", 0)
        self._save_and_refresh()
        self.statusBar().showMessage(f"批量操作完成: 成功 {s}, 跳过 {skip}, 失败 {f}")
        log_operation("批量操作", detail=f"成功 {s}, 跳过 {skip}, 失败 {f}")

    # === 导入/导出 ===

    def _export_devices(self):
        """导出全部设备"""
        if not self._devices:
            QMessageBox.information(self, "提示", "设备列表为空，无数据可导出")
            return

        self._do_export(self._devices, "导出全部设备")

    def _export_selected_devices(self):
        """导出选中的设备"""
        selected = self.device_table.get_selected_devices()
        if not selected:
            QMessageBox.information(self, "提示", "请先在设备列表中选择要导出的设备")
            return

        self._do_export(selected, f"导出选中的 {len(selected)} 台设备")

    def _do_export(self, devices: list[Device], title: str):
        """执行导出操作"""
        path, _ = QFileDialog.getSaveFileName(
            self, title, "",
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
        )
        if not path:
            return

        try:
            if path.endswith(".xlsx"):
                export_excel(devices, path, styled=True)
            else:
                export_csv(devices, path)
            self.statusBar().showMessage(f"导出成功: {path}")
            log_operation("导出", detail=f"导出 {len(devices)} 台设备到 {path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    def _import_devices(self):
        """导入设备清单（带预览和校验）"""
        path, _ = QFileDialog.getOpenFileName(
            self, "导入设备清单", "",
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
        )
        if not path:
            return

        try:
            # 读取文件
            if path.endswith(".xlsx"):
                rows = import_excel(path)
            else:
                rows = import_csv(path)

            if not rows:
                QMessageBox.information(self, "提示", "文件中没有可导入的数据")
                return

            # 显示导入预览对话框
            existing_macs = {d.mac.lower() for d in self._devices}
            dialog = ImportDialog(rows, existing_macs, parent=self)

            if dialog.exec() != ImportDialog.DialogCode.Accepted:
                return

            # 获取用户选择
            valid_rows, strategy = dialog.get_result()

            # 执行导入
            count = self._process_import(valid_rows, strategy)

            self._save_and_refresh()
            self._rebuild_group_tree()
            self.statusBar().showMessage(f"导入成功: {count} 台设备")
            log_operation("导入", detail=f"从 {path} 导入 {count} 台设备 (策略: {strategy})")

        except Exception as e:
            QMessageBox.critical(self, "导入失败", str(e))

    def _process_import(self, valid_rows: list[dict], strategy: str) -> int:
        """处理导入数据

        Args:
            valid_rows: 校验通过的数据行
            strategy: 冲突处理策略 (skip/overwrite/add_all)

        Returns:
            实际导入的设备数量
        """
        count = 0
        existing_macs = {d.mac.lower(): d for d in self._devices}

        for row in valid_rows:
            mac = row.get("mac", "").lower()
            if not mac:
                continue

            existing = existing_macs.get(mac)

            if existing:
                if strategy == ImportDialog.SKIP_EXISTING:
                    # 跳过已存在的设备
                    continue
                elif strategy == ImportDialog.OVERWRITE:
                    # 覆盖更新
                    existing.ip = row.get("ip", "") or existing.ip
                    existing.brand = row.get("brand", "") or existing.brand
                    existing.model = row.get("model", "") or existing.model
                    existing.group = row.get("group", "") or existing.group
                    existing.note = row.get("note", "") or existing.note
                    existing.subnet_mask = row.get("subnet_mask", "") or existing.subnet_mask
                    existing.gateway = row.get("gateway", "") or existing.gateway
                    count += 1
                elif strategy == ImportDialog.ADD_ALL:
                    # 全部作为新设备（不应该发生，MAC 重复会覆盖）
                    existing.ip = row.get("ip", "") or existing.ip
                    count += 1
            else:
                # 新设备
                device = Device(
                    mac=mac,
                    ip=row.get("ip", ""),
                    brand=row.get("brand", ""),
                    model=row.get("model", ""),
                    group=row.get("group", ""),
                    note=row.get("note", ""),
                    subnet_mask=row.get("subnet_mask", ""),
                    gateway=row.get("gateway", ""),
                )
                self._devices.append(device)
                existing_macs[mac] = device
                count += 1

        return count

    def _download_template(self):
        """下载导入模板"""
        path, _ = QFileDialog.getSaveFileName(
            self, "下载导入模板", "设备清单模板.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not path:
            return

        try:
            generate_template(path)
            self.statusBar().showMessage(f"模板已保存: {path}")
            QMessageBox.information(
                self, "模板下载成功",
                f"模板已保存到:\n{path}\n\n请按照模板格式填写设备信息后导入。"
            )
        except Exception as e:
            QMessageBox.critical(self, "模板下载失败", str(e))

    # === 持久化与刷新 ===

    def _save_and_refresh(self):
        for d in self._devices:
            save_device(d)
        self.device_table.update_devices(self._devices)

    def _rebuild_group_tree(self):
        self.device_table.rebuild_group_tree(self._devices)

    # === Tab 切换 ===

    def _on_tab_changed(self, index: int):
        if index == 4:  # 日志页
            self.log_panel.refresh_logs()
