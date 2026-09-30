"""网络配置面板 — IP/子网掩码/网关/DHCP 配置 + 冲突检测 + 密码修改"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QRadioButton, QPushButton, QGroupBox,
    QButtonGroup, QFormLayout, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal, QObject, QThread

from device.models import Device
from scanner.ip_conflict import check_ip_conflict


class _Worker(QObject):
    """通用后台工作线程"""
    finished = pyqtSignal(object)

    def __init__(self, func, *args):
        super().__init__()
        self._func = func
        self._args = args

    def run(self):
        result = self._func(*self._args)
        self.finished.emit(result)


class ConfigPanel(QWidget):
    """单设备网络配置 + 密码修改面板"""

    config_applied = pyqtSignal(object, dict)        # (device, result_dict)
    password_changed = pyqtSignal(object, dict)       # (device, result_dict)

    def __init__(self):
        super().__init__()
        self._current_device: Device | None = None
        self._worker_thread: QThread | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # === 设备信息 ===
        info_group = QGroupBox("当前设备")
        info_layout = QFormLayout(info_group)
        self.device_label = QLabel("未选择设备")
        self.mac_label = QLabel("")
        self.current_ip_label = QLabel("")
        info_layout.addRow("设备:", self.device_label)
        info_layout.addRow("MAC:", self.mac_label)
        info_layout.addRow("当前 IP:", self.current_ip_label)
        layout.addWidget(info_group)

        # === 网络配置 ===
        # DHCP / 静态切换
        mode_group = QGroupBox("IP 获取方式")
        mode_layout = QVBoxLayout(mode_group)
        self.mode_group = QButtonGroup(self)
        self.radio_dhcp = QRadioButton("DHCP 自动获取")
        self.radio_static = QRadioButton("手动配置")
        self.radio_static.setChecked(True)
        self.mode_group.addButton(self.radio_dhcp)
        self.mode_group.addButton(self.radio_static)
        mode_layout.addWidget(self.radio_dhcp)
        mode_layout.addWidget(self.radio_static)
        layout.addWidget(mode_group)

        # 手动配置
        config_group = QGroupBox("网络配置")
        config_layout = QFormLayout(config_group)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.100")
        self.mask_input = QLineEdit("255.255.255.0")
        self.gateway_input = QLineEdit()
        self.gateway_input.setPlaceholderText("192.168.1.1")
        config_layout.addRow("IP 地址:", self.ip_input)
        config_layout.addRow("子网掩码:", self.mask_input)
        config_layout.addRow("网关:", self.gateway_input)
        layout.addWidget(config_group)

        self.radio_dhcp.toggled.connect(self._toggle_inputs)

        # 按钮
        btn_layout = QHBoxLayout()
        self.check_btn = QPushButton("检测 IP 冲突")
        self.check_btn.clicked.connect(self._check_conflict)
        self.apply_btn = QPushButton("应用配置")
        self.apply_btn.clicked.connect(self._apply_config)
        btn_layout.addWidget(self.check_btn)
        btn_layout.addWidget(self.apply_btn)
        layout.addLayout(btn_layout)

        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

        # === 密码修改 ===
        pwd_group = QGroupBox("修改密码")
        pwd_layout = QFormLayout(pwd_group)
        self.old_pwd_input = QLineEdit()
        self.old_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_pwd_input.setPlaceholderText("当前密码")
        self.new_pwd_input = QLineEdit()
        self.new_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pwd_input.setPlaceholderText("新密码")
        self.confirm_pwd_input = QLineEdit()
        self.confirm_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_pwd_input.setPlaceholderText("确认新密码")
        pwd_layout.addRow("旧密码:", self.old_pwd_input)
        pwd_layout.addRow("新密码:", self.new_pwd_input)
        pwd_layout.addRow("确认密码:", self.confirm_pwd_input)
        layout.addWidget(pwd_group)

        pwd_btn_layout = QHBoxLayout()
        self.change_pwd_btn = QPushButton("修改密码")
        self.change_pwd_btn.clicked.connect(self._change_password)
        pwd_btn_layout.addWidget(self.change_pwd_btn)
        layout.addLayout(pwd_btn_layout)

        self.pwd_result_label = QLabel("")
        layout.addWidget(self.pwd_result_label)

        layout.addStretch()

    def set_device(self, device: Device):
        """设置当前要配置的设备"""
        self._current_device = device
        brand_model = f"{device.brand} {device.model}".strip() or "未知设备"
        self.device_label.setText(brand_model)
        self.mac_label.setText(device.mac)
        self.current_ip_label.setText(device.ip)
        self.ip_input.setText(device.ip)
        self.mask_input.setText(device.subnet_mask or "255.255.255.0")
        self.gateway_input.setText(device.gateway or "")

        if device.dhcp:
            self.radio_dhcp.setChecked(True)
        else:
            self.radio_static.setChecked(True)

        self.result_label.setText("")
        self.pwd_result_label.setText("")
        # 清空密码输入
        self.old_pwd_input.clear()
        self.new_pwd_input.clear()
        self.confirm_pwd_input.clear()

    def _toggle_inputs(self, dhcp_on: bool):
        self.ip_input.setEnabled(not dhcp_on)
        self.mask_input.setEnabled(not dhcp_on)
        self.gateway_input.setEnabled(not dhcp_on)

    # === IP 冲突检测 ===

    def _run_async(self, func, *args, on_done=None, disable_widgets=None):
        """通用异步执行器"""
        self._worker_thread = QThread()
        worker = _Worker(func, *args)
        worker.moveToThread(self._worker_thread)

        for w in (disable_widgets or []):
            w.setEnabled(False)

        self._worker_thread.started.connect(worker.run)
        worker.finished.connect(lambda r: self._on_async_done(r, on_done, disable_widgets or []))
        worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)
        self._worker_thread.start()

    def _on_async_done(self, result, callback, widgets):
        for w in widgets:
            w.setEnabled(True)
        if callback:
            callback(result)

    def _check_conflict(self):
        ip = self.ip_input.text().strip()
        if not ip:
            QMessageBox.warning(self, "提示", "请输入 IP 地址")
            return

        self.result_label.setText("检测中...")
        self._run_async(
            check_ip_conflict, ip,
            on_done=self._on_conflict_result,
            disable_widgets=[self.check_btn],
        )

    def _on_conflict_result(self, result: dict):
        if result["conflict"]:
            mac = result.get("mac", "未知")
            self.result_label.setText(f"IP 冲突! 该 IP 已被 {mac} 占用")
            self.result_label.setStyleSheet("color: red;")
            QMessageBox.warning(
                self, "IP 冲突",
                f"IP {self.ip_input.text()} 已被设备 {mac} 占用，请更换 IP。"
            )
        else:
            self.result_label.setText("IP 可用，无冲突")
            self.result_label.setStyleSheet("color: green;")

    # === 应用配置 ===

    def _apply_config(self):
        if not self._current_device:
            QMessageBox.warning(self, "提示", "请先在设备列表中选择一个设备")
            return

        dhcp = self.radio_dhcp.isChecked()
        ip = self.ip_input.text().strip()
        mask = self.mask_input.text().strip()
        gateway = self.gateway_input.text().strip()
        device = self._current_device

        if not dhcp and not ip:
            QMessageBox.warning(self, "提示", "请输入 IP 地址")
            return

        # 非 DHCP 且 IP 变更 -> 先检测冲突
        if not dhcp and ip != device.ip:
            self.result_label.setText("检测冲突中...")

            def on_check_done(result):
                if result["conflict"]:
                    mac = result.get("mac", "未知")
                    QMessageBox.warning(
                        self, "IP 冲突",
                        f"IP {ip} 已被 {mac} 占用，无法应用。"
                    )
                    self.result_label.setText(f"IP 冲突: {mac}")
                    self.result_label.setStyleSheet("color: red;")
                else:
                    self._do_apply(device, ip, mask, gateway, dhcp)

            self._run_async(
                check_ip_conflict, ip,
                on_done=on_check_done,
                disable_widgets=[self.check_btn],
            )
        else:
            self._do_apply(device, ip, mask, gateway, dhcp)

    def _do_apply(self, device: Device, ip: str, mask: str, gateway: str, dhcp: bool):
        from device.config import modify_network_config

        self.result_label.setText("正在修改配置...")
        self._run_async(
            modify_network_config,
            device.brand, device.ip, device.mac,
            ip, mask, gateway, dhcp,
            on_done=lambda ok: self._on_apply_done(device, ip, mask, gateway, dhcp, ok),
            disable_widgets=[self.apply_btn],
        )

    def _on_apply_done(self, device, ip, mask, gateway, dhcp, ok):
        result = {"success": ok, "message": "成功" if ok else "修改失败（请检查设备连接）"}
        if ok:
            self.result_label.setText(f"配置修改成功: {ip}")
            self.result_label.setStyleSheet("color: green;")
        else:
            self.result_label.setText(f"修改失败: {result['message']}")
            self.result_label.setStyleSheet("color: red;")
        self.config_applied.emit(device, result)

    # === 修改密码 ===

    def _change_password(self):
        if not self._current_device:
            QMessageBox.warning(self, "提示", "请先在设备列表中选择一个设备")
            return

        old_pwd = self.old_pwd_input.text()
        new_pwd = self.new_pwd_input.text()
        confirm_pwd = self.confirm_pwd_input.text()

        if not old_pwd:
            QMessageBox.warning(self, "提示", "请输入旧密码")
            return
        if not new_pwd:
            QMessageBox.warning(self, "提示", "请输入新密码")
            return
        if new_pwd != confirm_pwd:
            QMessageBox.warning(self, "提示", "两次输入的新密码不一致")
            return

        self.pwd_result_label.setText("正在修改密码...")
        device = self._current_device

        from device.config import change_password
        self._run_async(
            change_password,
            device.brand, device.ip, old_pwd, new_pwd, device.port,
            on_done=self._on_password_done,
            disable_widgets=[self.change_pwd_btn],
        )

    def _on_password_done(self, result: dict):
        if result.get("success"):
            self.pwd_result_label.setText("密码修改成功")
            self.pwd_result_label.setStyleSheet("color: green;")
            # 清空输入
            self.old_pwd_input.clear()
            self.new_pwd_input.clear()
            self.confirm_pwd_input.clear()
        else:
            self.pwd_result_label.setText(f"修改失败: {result.get('message', '')}")
            self.pwd_result_label.setStyleSheet("color: red;")

        if self._current_device:
            self.password_changed.emit(self._current_device, result)
