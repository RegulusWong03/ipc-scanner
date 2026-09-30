"""批量操作面板 — 批量改密 + 批量改IP + 批量DHCP切换"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QProgressBar, QTextEdit, QCheckBox, QMessageBox,
    QTabWidget,
)
from PyQt6.QtCore import pyqtSignal, QObject, QThread

from device.models import Device


class _BatchWorker(QObject):
    """批量操作后台工作线程"""
    progress = pyqtSignal(int, int, str, str)   # current, total, mac, message
    finished = pyqtSignal(dict)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self):
        def progress_cb(*args):
            if len(args) >= 4:
                # batch_change_password: (current, total, mac, success, message)
                current, total, mac = args[0], args[1], args[2]
                msg = args[4] if len(args) > 4 else ("成功" if args[3] else "失败")
            elif len(args) >= 3:
                current, total, mac = args[0], args[1], args[2]
                msg = str(args[-1])
            else:
                current, total, mac, msg = args[0], args[1], "", ""
            self.progress.emit(current, total, mac, msg)

        self._kwargs["progress_callback"] = progress_cb
        result = self._func(*self._args, **self._kwargs)
        self.finished.emit(result)


class BatchPanel(QWidget):
    """批量操作面板"""

    batch_completed = pyqtSignal(dict)  # 批量操作完成

    def __init__(self, get_devices_fn):
        """
        Args:
            get_devices_fn: 获取当前设备列表的回调函数
        """
        super().__init__()
        self._get_devices = get_devices_fn
        self._worker_thread: QThread | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        inner_tabs = QTabWidget()
        layout.addWidget(inner_tabs)

        # === 批量改密 ===
        pwd_widget = QWidget()
        pwd_layout = QVBoxLayout(pwd_widget)

        pwd_group = QGroupBox("批量修改密码")
        pwd_form = QFormLayout(pwd_group)
        self.pwd_old_input = QLineEdit()
        self.pwd_old_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_old_input.setPlaceholderText("留空则尝试常见默认密码")
        self.pwd_new_input = QLineEdit()
        self.pwd_new_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_new_input.setPlaceholderText("新密码")
        self.pwd_confirm_input = QLineEdit()
        self.pwd_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.pwd_confirm_input.setPlaceholderText("确认新密码")
        pwd_form.addRow("旧密码:", self.pwd_old_input)
        pwd_form.addRow("新密码:", self.pwd_new_input)
        pwd_form.addRow("确认密码:", self.pwd_confirm_input)
        pwd_layout.addWidget(pwd_group)

        pwd_btn_layout = QHBoxLayout()
        self.pwd_start_btn = QPushButton("开始批量改密")
        self.pwd_start_btn.clicked.connect(self._start_batch_password)
        pwd_btn_layout.addWidget(self.pwd_start_btn)
        pwd_layout.addLayout(pwd_btn_layout)

        self.pwd_progress = QProgressBar()
        self.pwd_progress.setVisible(False)
        pwd_layout.addWidget(self.pwd_progress)

        self.pwd_log = QTextEdit()
        self.pwd_log.setReadOnly(True)
        self.pwd_log.setMaximumHeight(200)
        pwd_layout.addWidget(self.pwd_log)

        inner_tabs.addTab(pwd_widget, "批量改密")

        # === 批量改IP ===
        ip_widget = QWidget()
        ip_layout = QVBoxLayout(ip_widget)

        ip_group = QGroupBox("批量修改 IP")
        ip_form = QFormLayout(ip_group)
        self.ip_start_input = QLineEdit()
        self.ip_start_input.setPlaceholderText("192.168.1.100")
        self.ip_mask_input = QLineEdit("255.255.255.0")
        self.ip_gw_input = QLineEdit()
        self.ip_gw_input.setPlaceholderText("192.168.1.1")
        self.ip_pwd_input = QLineEdit()
        self.ip_pwd_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ip_pwd_input.setPlaceholderText("设备密码（留空使用默认）")
        self.ip_check_conflict = QCheckBox("修改前检测 IP 冲突（冲突则跳过）")
        self.ip_check_conflict.setChecked(True)
        ip_form.addRow("起始 IP:", self.ip_start_input)
        ip_form.addRow("子网掩码:", self.ip_mask_input)
        ip_form.addRow("网关:", self.ip_gw_input)
        ip_form.addRow("密码:", self.ip_pwd_input)
        ip_form.addRow("", self.ip_check_conflict)
        ip_layout.addWidget(ip_group)

        # 预览分配方案
        self.ip_preview_btn = QPushButton("预览分配方案")
        self.ip_preview_btn.clicked.connect(self._preview_ip_plan)
        ip_layout.addWidget(self.ip_preview_btn)

        self.ip_preview_text = QTextEdit()
        self.ip_preview_text.setReadOnly(True)
        self.ip_preview_text.setMaximumHeight(150)
        ip_layout.addWidget(self.ip_preview_text)

        ip_btn_layout = QHBoxLayout()
        self.ip_start_btn = QPushButton("开始批量改 IP")
        self.ip_start_btn.clicked.connect(self._start_batch_ip)
        ip_btn_layout.addWidget(self.ip_start_btn)
        ip_layout.addLayout(ip_btn_layout)

        self.ip_progress = QProgressBar()
        self.ip_progress.setVisible(False)
        ip_layout.addWidget(self.ip_progress)

        self.ip_log = QTextEdit()
        self.ip_log.setReadOnly(True)
        self.ip_log.setMaximumHeight(200)
        ip_layout.addWidget(self.ip_log)

        inner_tabs.addTab(ip_widget, "批量改 IP")

        # === 批量 DHCP ===
        dhcp_widget = QWidget()
        dhcp_layout = QVBoxLayout(dhcp_widget)

        dhcp_group = QGroupBox("批量切换 DHCP")
        dhcp_inner = QVBoxLayout(dhcp_group)
        self.dhcp_enable_btn = QPushButton("全部开启 DHCP")
        self.dhcp_enable_btn.clicked.connect(lambda: self._start_batch_dhcp(True))
        self.dhcp_disable_btn = QPushButton("全部关闭 DHCP")
        self.dhcp_disable_btn.clicked.connect(lambda: self._start_batch_dhcp(False))
        dhcp_inner.addWidget(self.dhcp_enable_btn)
        dhcp_inner.addWidget(self.dhcp_disable_btn)
        dhcp_layout.addWidget(dhcp_group)

        self.dhcp_progress = QProgressBar()
        self.dhcp_progress.setVisible(False)
        dhcp_layout.addWidget(self.dhcp_progress)

        self.dhcp_log = QTextEdit()
        self.dhcp_log.setReadOnly(True)
        self.dhcp_log.setMaximumHeight(200)
        dhcp_layout.addWidget(self.dhcp_log)

        inner_tabs.addTab(dhcp_widget, "批量 DHCP")

    # === 批量改密 ===

    def _start_batch_password(self):
        new_pwd = self.pwd_new_input.text()
        confirm_pwd = self.pwd_confirm_input.text()
        old_pwd = self.pwd_old_input.text()

        if not new_pwd:
            QMessageBox.warning(self, "提示", "请输入新密码")
            return
        if new_pwd != confirm_pwd:
            QMessageBox.warning(self, "提示", "两次输入的新密码不一致")
            return

        devices = self._get_devices()
        online_devices = [d for d in devices if d.status.value == "在线" or d.status.value == "新上线"]

        if not online_devices:
            QMessageBox.warning(self, "提示", "没有在线设备可操作")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"将批量修改 {len(online_devices)} 台设备的密码，确定继续？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.pwd_log.clear()
        self.pwd_progress.setVisible(True)
        self.pwd_progress.setMaximum(len(online_devices))
        self.pwd_progress.setValue(0)
        self.pwd_start_btn.setEnabled(False)

        from batch.operations import batch_change_password
        self._worker_thread = QThread()
        worker = _BatchWorker(batch_change_password, online_devices, new_pwd, old_password=old_pwd)
        worker.moveToThread(self._worker_thread)

        worker.progress.connect(self._on_pwd_progress)
        worker.finished.connect(self._on_pwd_finished)
        worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.started.connect(worker.run)
        self._worker_thread.start()

    def _on_pwd_progress(self, current, total, mac, message):
        self.pwd_progress.setValue(current)
        self.pwd_log.append(f"[{current}/{total}] {mac}: {message}")

    def _on_pwd_finished(self, result: dict):
        self.pwd_start_btn.setEnabled(True)
        s, f = result["success"], result["failed"]
        self.pwd_log.append(f"\n完成: 成功 {s} 台, 失败 {f} 台")
        self.pwd_progress.setVisible(False)
        self.batch_completed.emit(result)

    # === 批量改 IP ===

    def _preview_ip_plan(self):
        """预览 IP 分配方案"""
        start_ip = self.ip_start_input.text().strip()
        if not start_ip:
            QMessageBox.warning(self, "提示", "请输入起始 IP")
            return

        import ipaddress
        devices = self._get_devices()
        online_devices = [d for d in devices if d.status.value in ("在线", "新上线")]

        if not online_devices:
            self.ip_preview_text.setText("没有在线设备")
            return

        try:
            base = ipaddress.IPv4Address(start_ip)
        except ValueError:
            self.ip_preview_text.setText("起始 IP 格式错误")
            return

        lines = []
        for i, d in enumerate(online_devices):
            new_ip = str(base + i)
            lines.append(f"{d.mac}  {d.ip:>15}  ->  {new_ip:>15}  {d.brand} {d.model}")

        self.ip_preview_text.setText("\n".join(lines))

    def _start_batch_ip(self):
        start_ip = self.ip_start_input.text().strip()
        mask = self.ip_mask_input.text().strip()
        gateway = self.ip_gw_input.text().strip()
        password = self.ip_pwd_input.text()
        check_conflict = self.ip_check_conflict.isChecked()

        if not start_ip:
            QMessageBox.warning(self, "提示", "请输入起始 IP")
            return

        devices = self._get_devices()
        online_devices = [d for d in devices if d.status.value in ("在线", "新上线")]

        if not online_devices:
            QMessageBox.warning(self, "提示", "没有在线设备可操作")
            return

        reply = QMessageBox.question(
            self, "确认",
            f"将从 {start_ip} 开始批量分配 IP 给 {len(online_devices)} 台设备，确定继续？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.ip_log.clear()
        self.ip_progress.setVisible(True)
        self.ip_progress.setMaximum(len(online_devices))
        self.ip_progress.setValue(0)
        self.ip_start_btn.setEnabled(False)

        from batch.operations import batch_change_ip
        self._worker_thread = QThread()
        worker = _BatchWorker(
            batch_change_ip, online_devices, start_ip,
            subnet_mask=mask, gateway=gateway, password=password,
            check_conflict=check_conflict,
        )
        worker.moveToThread(self._worker_thread)

        worker.progress.connect(self._on_ip_progress)
        worker.finished.connect(self._on_ip_finished)
        worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.started.connect(worker.run)
        self._worker_thread.start()

    def _on_ip_progress(self, current, total, mac, message):
        self.ip_progress.setValue(current)
        self.ip_log.append(f"[{current}/{total}] {mac}: {message}")

    def _on_ip_finished(self, result: dict):
        self.ip_start_btn.setEnabled(True)
        s, f, skip = result["success"], result["failed"], result.get("skipped", 0)
        self.ip_log.append(f"\n完成: 成功 {s} 台, 跳过 {skip} 台 (冲突), 失败 {f} 台")
        self.ip_progress.setVisible(False)
        self.batch_completed.emit(result)

    # === 批量 DHCP ===

    def _start_batch_dhcp(self, enable: bool):
        devices = self._get_devices()
        online_devices = [d for d in devices if d.status.value in ("在线", "新上线")]

        if not online_devices:
            QMessageBox.warning(self, "提示", "没有在线设备可操作")
            return

        mode = "开启" if enable else "关闭"
        reply = QMessageBox.question(
            self, "确认",
            f"将{mode} {len(online_devices)} 台设备的 DHCP，确定继续？"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.dhcp_log.clear()
        self.dhcp_progress.setVisible(True)
        self.dhcp_progress.setMaximum(len(online_devices))
        self.dhcp_progress.setValue(0)
        self.dhcp_enable_btn.setEnabled(False)
        self.dhcp_disable_btn.setEnabled(False)

        from batch.operations import batch_set_dhcp
        self._worker_thread = QThread()
        worker = _BatchWorker(batch_set_dhcp, online_devices, enable)
        worker.moveToThread(self._worker_thread)

        worker.progress.connect(self._on_dhcp_progress)
        worker.finished.connect(self._on_dhcp_finished)
        worker.finished.connect(self._worker_thread.quit)
        self._worker_thread.started.connect(worker.run)
        self._worker_thread.start()

    def _on_dhcp_progress(self, current, total, mac, message):
        self.dhcp_progress.setValue(current)
        self.dhcp_log.append(f"[{current}/{total}] {mac}: {message}")

    def _on_dhcp_finished(self, result: dict):
        self.dhcp_enable_btn.setEnabled(True)
        self.dhcp_disable_btn.setEnabled(True)
        s, f = result["success"], result["failed"]
        self.dhcp_log.append(f"\n完成: 成功 {s} 台, 失败 {f} 台")
        self.dhcp_progress.setVisible(False)
        self.batch_completed.emit(result)
