"""Phase 3 配置功能测试"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from device.config import DEFAULT_CREDENTIALS, change_password
from device.models import Device, DeviceStatus, DeviceType


class TestDeviceConfig:
    """设备配置模块测试"""

    def test_default_credentials_exist(self):
        """测试默认账密表已配置"""
        assert "hikvision" in DEFAULT_CREDENTIALS
        assert "dahua" in DEFAULT_CREDENTIALS
        assert "onvif" in DEFAULT_CREDENTIALS
        assert len(DEFAULT_CREDENTIALS["hikvision"]) > 0
        assert len(DEFAULT_CREDENTIALS["dahua"]) > 0

    def test_hikvision_default_password(self):
        """测试海康默认密码"""
        creds = DEFAULT_CREDENTIALS["hikvision"]
        passwords = [p for _, p in creds]
        assert "admin12345" in passwords

    def test_dahua_default_password(self):
        """测试大华默认密码"""
        creds = DEFAULT_CREDENTIALS["dahua"]
        passwords = [p for _, p in creds]
        assert "admin" in passwords

    def test_change_password_returns_dict(self):
        """测试改密函数返回字典格式"""
        # 对不存在的设备调用，应返回失败结果
        result = change_password(
            brand="unknown",
            ip="192.168.255.255",
            old_password="test",
            new_password="newtest",
            port=80,
        )
        assert "success" in result
        assert "message" in result
        assert result["success"] is False


class TestBatchOperations:
    """批量操作模块测试"""

    def test_batch_change_password_empty_list(self):
        """测试空设备列表"""
        from batch.operations import batch_change_password

        result = batch_change_password([], "newpass")
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result["details"] == []

    def test_batch_change_ip_empty_list(self):
        """测试空设备列表"""
        from batch.operations import batch_change_ip

        result = batch_change_ip([], "192.168.1.100")
        assert result["success"] == 0
        assert result["failed"] == 0
        assert result.get("skipped", 0) == 0

    def test_batch_set_dhcp_empty_list(self):
        """测试空设备列表"""
        from batch.operations import batch_set_dhcp

        result = batch_set_dhcp([], True)
        assert result["success"] == 0
        assert result["failed"] == 0

    def test_batch_change_password_with_progress(self):
        """测试批量改密的进度回调"""
        from batch.operations import batch_change_password

        devices = [
            Device(mac="aa:bb:cc:dd:ee:01", ip="192.168.1.1", brand="hikvision",
                   status=DeviceStatus.ONLINE),
            Device(mac="aa:bb:cc:dd:ee:02", ip="192.168.1.2", brand="dahua",
                   status=DeviceStatus.ONLINE),
        ]

        progress_log = []

        def on_progress(current, total, mac, success, message):
            progress_log.append((current, total, mac))

        result = batch_change_password(
            devices, "newpass123", old_password="old",
            progress_callback=on_progress,
        )

        # 2 个设备都失败了（无法连接），但进度回调应该被调用
        assert len(progress_log) == 2
        assert progress_log[0] == (1, 2, "aa:bb:cc:dd:ee:01")
        assert progress_log[1] == (2, 2, "aa:bb:cc:dd:ee:02")
        assert result["failed"] == 2  # 都失败，因为设备不在线

    def test_batch_change_ip_allocation(self):
        """测试 IP 分配计算逻辑"""
        import ipaddress

        # 验证 IP 递增逻辑
        base = ipaddress.IPv4Address("192.168.1.100")
        for i in range(5):
            ip = str(base + i)
            assert ip == f"192.168.1.{100 + i}"


class TestConfigPanelUI:
    """配置面板 UI 测试"""

    def test_config_panel_import(self):
        """测试配置面板可导入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.config_panel import ConfigPanel

        panel = ConfigPanel()
        assert panel is not None
        assert panel.ip_input is not None
        assert panel.mask_input is not None
        assert panel.gateway_input is not None

    def test_config_panel_set_device(self):
        """测试设置设备信息"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.config_panel import ConfigPanel

        panel = ConfigPanel()
        device = Device(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.100",
            subnet_mask="255.255.255.0",
            gateway="192.168.1.1",
            brand="hikvision",
            model="DS-2CD2142FWD",
            dhcp=False,
        )
        panel.set_device(device)

        assert panel.device_label.text() == "hikvision DS-2CD2142FWD"
        assert panel.mac_label.text() == "aa:bb:cc:dd:ee:ff"
        assert panel.current_ip_label.text() == "192.168.1.100"
        assert panel.ip_input.text() == "192.168.1.100"
        assert panel.mask_input.text() == "255.255.255.0"
        assert panel.gateway_input.text() == "192.168.1.1"
        assert panel.radio_static.isChecked()

    def test_config_panel_dhcp_toggle(self):
        """测试 DHCP 切换禁用输入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.config_panel import ConfigPanel

        panel = ConfigPanel()
        device = Device(mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.100", dhcp=True)
        panel.set_device(device)

        # DHCP 模式 -> 输入框禁用
        assert panel.radio_dhcp.isChecked()
        assert not panel.ip_input.isEnabled()
        assert not panel.mask_input.isEnabled()
        assert not panel.gateway_input.isEnabled()

        # 切换到静态
        panel.radio_static.setChecked(True)
        assert panel.ip_input.isEnabled()
        assert panel.mask_input.isEnabled()

    def test_password_fields_exist(self):
        """测试密码修改输入框存在"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.config_panel import ConfigPanel

        panel = ConfigPanel()
        assert panel.old_pwd_input is not None
        assert panel.new_pwd_input is not None
        assert panel.confirm_pwd_input is not None
        assert panel.change_pwd_btn is not None


class TestBatchPanelUI:
    """批量操作面板 UI 测试"""

    def test_batch_panel_import(self):
        """测试批量面板可导入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.batch_panel import BatchPanel

        panel = BatchPanel(get_devices_fn=lambda: [])
        assert panel is not None

    def test_batch_panel_fields(self):
        """测试批量面板的输入控件"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.batch_panel import BatchPanel

        panel = BatchPanel(get_devices_fn=lambda: [])

        # 批量改密
        assert panel.pwd_old_input is not None
        assert panel.pwd_new_input is not None
        assert panel.pwd_confirm_input is not None
        assert panel.pwd_start_btn is not None

        # 批量改IP
        assert panel.ip_start_input is not None
        assert panel.ip_mask_input is not None
        assert panel.ip_gw_input is not None
        assert panel.ip_check_conflict is not None
        assert panel.ip_start_btn is not None

        # 批量DHCP
        assert panel.dhcp_enable_btn is not None
        assert panel.dhcp_disable_btn is not None


class TestMainWindowPhase3:
    """主窗口 Phase 3 集成测试"""

    def test_main_window_5_tabs(self):
        """测试主窗口有 5 个 Tab（含批量操作）"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.main_window import MainWindow

        window = MainWindow()
        assert window.tabs.count() == 5
        # 验证 Tab 名称
        tab_names = [window.tabs.tabText(i) for i in range(5)]
        assert "设备列表" in tab_names
        assert "网络配置" in tab_names
        assert "批量操作" in tab_names
        assert "实时预览" in tab_names
        assert "操作日志" in tab_names

    def test_main_window_signals_connected(self):
        """测试信号连接"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.main_window import MainWindow

        window = MainWindow()
        # 批量面板信号已连接
        assert window.batch_panel is not None
        assert window.config_panel.password_changed is not None


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
