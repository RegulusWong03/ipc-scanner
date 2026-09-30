"""Phase 5 实时预览测试"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from protocols.rtsp_helper import (
    generate_rtsp_url, parse_rtsp_url, generate_multiple_urls,
)


class TestRtspHelper:
    """RTSP URL 生成测试"""

    def test_hikvision_main_stream(self):
        """测试海康主码流 URL"""
        url = generate_rtsp_url("hikvision", "192.168.1.64", channel=1,
                                stream="main", username="admin", password="admin123")
        assert url == "rtsp://admin:admin123@192.168.1.64:554/Streaming/Channels/101"

    def test_hikvision_sub_stream(self):
        """测试海康子码流 URL"""
        url = generate_rtsp_url("hikvision", "192.168.1.64", channel=1,
                                stream="sub", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.64:554/Streaming/Channels/102"

    def test_hikvision_channel2(self):
        """测试海康 NVR 第 2 通道"""
        url = generate_rtsp_url("hikvision", "192.168.1.64", channel=2,
                                stream="main", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.64:554/Streaming/Channels/201"

    def test_dahua_main_stream(self):
        """测试大华主码流 URL"""
        url = generate_rtsp_url("dahua", "192.168.1.108", channel=1,
                                stream="main", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.108:554/cam/realmonitor?channel=1&subtype=0"

    def test_dahua_sub_stream(self):
        """测试大华子码流 URL"""
        url = generate_rtsp_url("dahua", "192.168.1.108", channel=1,
                                stream="sub", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.108:554/cam/realmonitor?channel=1&subtype=1"

    def test_dahua_channel3(self):
        """测试大华 NVR 第 3 通道"""
        url = generate_rtsp_url("dahua", "192.168.1.108", channel=3,
                                stream="main", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.108:554/cam/realmonitor?channel=3&subtype=0"

    def test_uniview_main_stream(self):
        """测试宇视主码流 URL"""
        url = generate_rtsp_url("uniview", "192.168.1.200", channel=1,
                                stream="main", username="admin", password="123456")
        assert url == "rtsp://admin:123456@192.168.1.200:554/unicast/c1/s0"

    def test_uniview_sub_stream(self):
        """测试宇视子码流 URL"""
        url = generate_rtsp_url("uniview", "192.168.1.200", channel=1,
                                stream="sub", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.200:554/unicast/c1/s1"

    def test_tplink_main_stream(self):
        """测试 TP-LINK URL"""
        url = generate_rtsp_url("tp-link", "192.168.1.50", channel=1,
                                stream="main", username="admin", password="admin")
        assert url == "rtsp://admin:admin@192.168.1.50:554/stream1"

    def test_generic_unknown_brand(self):
        """测试未知品牌的通用 URL"""
        url = generate_rtsp_url("unknown", "10.0.0.1", channel=1,
                                username="admin", password="admin")
        assert url == "rtsp://admin:admin@10.0.0.1:554/onvif1"

    def test_empty_brand(self):
        """测试空品牌"""
        url = generate_rtsp_url("", "10.0.0.1", channel=1,
                                username="admin", password="pass")
        assert url == "rtsp://admin:pass@10.0.0.1:554/onvif1"

    def test_case_insensitive(self):
        """测试品牌名不区分大小写"""
        url1 = generate_rtsp_url("Hikvision", "1.1.1.1")
        url2 = generate_rtsp_url("HIKVISION", "1.1.1.1")
        url3 = generate_rtsp_url("hikvision", "1.1.1.1")
        assert url1 == url2 == url3


class TestParseRtspUrl:
    """RTSP URL 解析测试"""

    def test_parse_standard_url(self):
        """测试解析标准 RTSP URL"""
        result = parse_rtsp_url("rtsp://admin:admin@192.168.1.100:554/Streaming/Channels/101")
        assert result["username"] == "admin"
        assert result["password"] == "admin"
        assert result["ip"] == "192.168.1.100"
        assert result["port"] == 554
        assert result["path"] == "/Streaming/Channels/101"

    def test_parse_dahua_url(self):
        """测试解析大华 RTSP URL"""
        result = parse_rtsp_url("rtsp://admin:123456@10.0.0.1:554/cam/realmonitor?channel=1&subtype=0")
        assert result["username"] == "admin"
        assert result["password"] == "123456"
        assert result["ip"] == "10.0.0.1"
        assert result["port"] == 554

    def test_parse_invalid_url(self):
        """测试解析无效 URL"""
        result = parse_rtsp_url("not_a_url")
        assert result == {}

    def test_parse_empty_url(self):
        """测试解析空 URL"""
        result = parse_rtsp_url("")
        assert result == {}

    def test_roundtrip_hikvision(self):
        """测试生成后解析的一致性"""
        url = generate_rtsp_url("hikvision", "192.168.1.64", channel=1,
                                username="admin", password="secret")
        parsed = parse_rtsp_url(url)
        assert parsed["ip"] == "192.168.1.64"
        assert parsed["username"] == "admin"
        assert parsed["password"] == "secret"
        assert parsed["port"] == 554


class TestGenerateMultipleUrls:
    """多 URL 生成测试"""

    def test_generate_multiple_default_passwords(self):
        """测试默认密码列表"""
        urls = generate_multiple_urls("hikvision", "192.168.1.64")
        assert len(urls) == 4  # admin, 12345, admin123, ""
        assert all("192.168.1.64" in url for url in urls)
        assert all("hikvision" not in url.lower() for url in urls)  # 品牌不出现在 URL

    def test_generate_multiple_custom_passwords(self):
        """测试自定义密码列表"""
        urls = generate_multiple_urls("dahua", "10.0.0.1",
                                       passwords=["pass1", "pass2"])
        assert len(urls) == 2
        assert "pass1" in urls[0]
        assert "pass2" in urls[1]

    def test_generate_multiple_different_brands(self):
        """测试不同品牌生成不同格式"""
        urls_hik = generate_multiple_urls("hikvision", "1.1.1.1", passwords=["admin"])
        urls_dahua = generate_multiple_urls("dahua", "1.1.1.1", passwords=["admin"])
        assert urls_hik[0] != urls_dahua[0]
        assert "Streaming/Channels" in urls_hik[0]
        assert "realmonitor" in urls_dahua[0]


class TestPreviewPanelUI:
    """预览面板 UI 测试"""

    def test_preview_panel_import(self):
        """测试预览面板可导入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        assert panel is not None
        assert panel.url_combo is not None
        assert panel.play_btn is not None
        assert panel.stop_btn is not None
        assert panel.popout_btn is not None
        assert panel.screenshot_btn is not None

    def test_preview_panel_set_device(self):
        """测试设置设备后自动生成 URL"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel
        from device.models import Device

        panel = PreviewPanel()
        device = Device(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.64",
            brand="hikvision",
            model="DS-2CD2142FWD",
        )
        panel.set_device(device)

        # 应该有多个 URL（不同密码）
        assert panel.url_combo.count() >= 4
        # 第一个应该包含海康格式
        first_url = panel.url_combo.itemText(0)
        assert "192.168.1.64" in first_url
        assert "Streaming/Channels" in first_url

    def test_preview_panel_set_device_dahua(self):
        """测试大华设备 URL 生成"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel
        from device.models import Device

        panel = PreviewPanel()
        device = Device(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.108",
            brand="dahua",
            model="IPC-HDW4431C",
        )
        panel.set_device(device)

        first_url = panel.url_combo.itemText(0)
        assert "192.168.1.108" in first_url
        assert "realmonitor" in first_url

    def test_preview_panel_set_device_with_rtsp_url(self):
        """测试设备已有 RTSP URL 时优先使用"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel
        from device.models import Device

        panel = PreviewPanel()
        device = Device(
            mac="aa:bb:cc:dd:ee:ff",
            ip="192.168.1.64",
            brand="hikvision",
            rtsp_url="rtsp://custom:pass@192.168.1.64:554/custom_path",
        )
        panel.set_device(device)

        # 第一个应该是设备自带的 URL
        assert panel.url_combo.itemText(0) == "rtsp://custom:pass@192.168.1.64:554/custom_path"

    def test_preview_panel_set_rtsp_url_compat(self):
        """测试兼容接口 set_rtsp_url"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        panel.set_rtsp_url("rtsp://test:test@1.1.1.1:554/test")
        assert panel.url_combo.currentText() == "rtsp://test:test@1.1.1.1:554/test"

    def test_preview_panel_set_none_device(self):
        """测试设置 None 设备不崩溃"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        panel.set_device(None)  # 不应崩溃
        assert panel.url_combo.count() == 0

    def test_preview_panel_initial_state(self):
        """测试初始状态"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewPanel

        panel = PreviewPanel()
        assert panel.stop_btn.isEnabled() is False
        assert panel.screenshot_btn.isEnabled() is False
        assert panel.status_label.text() == "就绪"

    def test_preview_window_import(self):
        """测试预览窗口可导入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.preview_panel import PreviewWindow

        # 不启动播放，只验证类定义
        assert PreviewWindow is not None
        assert hasattr(PreviewWindow, 'closed')
        assert hasattr(PreviewWindow, '_frame_ready')


class TestMainWindowPhase5:
    """主窗口 Phase 5 集成测试"""

    def test_main_window_preview_panel(self):
        """测试主窗口包含预览面板"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from ui.main_window import MainWindow

        window = MainWindow()
        assert window.preview_panel is not None
        # 预览 Tab 存在
        tab_names = [window.tabs.tabText(i) for i in range(window.tabs.count())]
        assert "实时预览" in tab_names


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
