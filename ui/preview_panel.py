"""实时预览面板 — RTSP 视频流播放（OpenCV 方案）

功能:
- 根据品牌自动生成 RTSP URL（多密码尝试）
- 后台线程捕获视频帧，信号安全更新 UI
- 弹出独立预览窗口（多窗口预览）
- 截图保存
"""

import logging
import threading
import time
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QFrame, QFileDialog,
    QMessageBox, QGroupBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from protocols.rtsp_helper import generate_rtsp_url

logger = logging.getLogger(__name__)


class PreviewPanel(QWidget):
    """RTSP 实时预览面板（嵌入 Tab 页）"""

    # 类级别信号定义（必须在类体中声明）
    _frame_ready = pyqtSignal(object)       # numpy frame
    _status_ready = pyqtSignal(str)         # 状态文本
    _buttons_ready = pyqtSignal(bool, bool) # (is_playing, has_frame)

    def __init__(self):
        super().__init__()
        self._capture = None
        self._running = False
        self._thread = None
        self._current_frame = None
        self._popout_windows: list[PreviewWindow] = []
        self._init_ui()

        # 连接跨线程信号
        self._frame_ready.connect(self._on_frame_update)
        self._status_ready.connect(self._on_status_update)
        self._buttons_ready.connect(self._on_buttons_update)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # === 控制面板 ===
        ctrl_group = QGroupBox("预览控制")
        ctrl_layout = QVBoxLayout(ctrl_group)

        # RTSP 地址输入
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("RTSP 地址:"))
        self.url_combo = QComboBox()
        self.url_combo.setEditable(True)
        self.url_combo.setMinimumWidth(500)
        url_layout.addWidget(self.url_combo)
        ctrl_layout.addLayout(url_layout)

        # 按钮栏
        btn_layout = QHBoxLayout()
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(self._toggle_play)
        btn_layout.addWidget(self.play_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.popout_btn = QPushButton("弹出窗口")
        self.popout_btn.clicked.connect(self._popout)
        btn_layout.addWidget(self.popout_btn)

        self.screenshot_btn = QPushButton("截图")
        self.screenshot_btn.clicked.connect(self._screenshot)
        self.screenshot_btn.setEnabled(False)
        btn_layout.addWidget(self.screenshot_btn)

        btn_layout.addStretch()
        ctrl_layout.addLayout(btn_layout)

        # 状态栏
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: gray;")
        ctrl_layout.addWidget(self.status_label)

        layout.addWidget(ctrl_group)

        # === 视频渲染区域 ===
        self.video_frame = QFrame()
        self.video_frame.setMinimumSize(640, 480)
        self.video_frame.setStyleSheet("background-color: #1a1a1a;")

        frame_layout = QVBoxLayout(self.video_frame)
        self.video_label = QLabel("选择一个设备开始预览")
        self.video_label.setStyleSheet("color: #888; font-size: 14px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame_layout.addWidget(self.video_label)

        layout.addWidget(self.video_frame, stretch=1)

    def set_device(self, device):
        """设置当前设备，自动生成可能的 RTSP URL"""
        if not device or not device.ip:
            return

        self.url_combo.clear()

        # 如果设备已有 RTSP URL，优先使用
        if device.rtsp_url:
            self.url_combo.addItem(device.rtsp_url)

        # 根据品牌生成常见 URL（多种密码尝试）
        brand = device.brand.lower() if device.brand else ""
        common_passwords = ["admin", "12345", "admin123", ""]

        existing_urls = set()
        for i in range(self.url_combo.count()):
            existing_urls.add(self.url_combo.itemText(i))

        for pwd in common_passwords:
            url = generate_rtsp_url(brand, device.ip, channel=1,
                                    stream="main", username="admin", password=pwd)
            if url not in existing_urls:
                self.url_combo.addItem(url)
                existing_urls.add(url)

        self.status_label.setText(f"设备: {device.brand} {device.model} @ {device.ip}")

    def set_rtsp_url(self, url: str):
        """兼容旧接口：直接设置 RTSP 地址"""
        if url and url != self.url_combo.currentText():
            self.url_combo.clear()
            self.url_combo.addItem(url)

    def _toggle_play(self):
        """播放/暂停"""
        if self._running:
            self._stop()
        else:
            self._start()

    def _start(self):
        """开始播放"""
        url = self.url_combo.currentText().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入 RTSP 地址")
            return

        try:
            import cv2  # noqa: F401
        except ImportError:
            QMessageBox.critical(self, "缺少依赖",
                                 "需要安装 OpenCV:\npip install opencv-python")
            return

        self._status("正在连接...")
        self.play_btn.setEnabled(False)

        self._thread = threading.Thread(
            target=self._capture_thread, args=(url,), daemon=True
        )
        self._thread.start()

    def _capture_thread(self, url: str):
        """后台视频捕获线程"""
        import cv2

        try:
            self._capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            if not self._capture.isOpened():
                self._status_ready.emit("连接失败，请检查 RTSP 地址和密码")
                self._buttons_ready.emit(False, False)
                return

            self._running = True
            self._status_ready.emit("已连接，正在播放")
            self._buttons_ready.emit(True, True)

            while self._running:
                ret, frame = self._capture.read()
                if not ret:
                    self._status_ready.emit("视频流断开")
                    break

                self._current_frame = frame.copy()
                self._frame_ready.emit(frame)
                time.sleep(0.04)  # ~25fps

        except Exception as e:
            logger.error("视频捕获错误: %s", e)
            self._status_ready.emit(f"错误: {e}")
        finally:
            self._running = False
            if self._capture:
                self._capture.release()
                self._capture = None
            self._buttons_ready.emit(False, False)

    def _stop(self):
        """停止播放"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        self.video_label.setText("已停止")
        self.video_label.setPixmap(QPixmap())
        self._status("已停止")
        self.play_btn.setText("播放")
        self.play_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.screenshot_btn.setEnabled(False)

    def _popout(self):
        """弹出独立预览窗口"""
        url = self.url_combo.currentText().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请先输入 RTSP 地址")
            return

        window = PreviewWindow(url, parent=None)
        window.closed.connect(lambda w=window: self._on_popout_closed(w))
        self._popout_windows.append(window)
        window.show()

    def _on_popout_closed(self, window):
        """弹出窗口关闭回调"""
        if window in self._popout_windows:
            self._popout_windows.remove(window)

    def _screenshot(self):
        """截图保存"""
        if self._current_frame is None:
            QMessageBox.warning(self, "提示", "没有可截图的画面")
            return

        self._save_frame(self._current_frame)

    def _save_frame(self, frame):
        """保存帧为图片"""
        import cv2

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"screenshot_{timestamp}.jpg"

        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存截图", default_name,
            "JPEG 图片 (*.jpg);;PNG 图片 (*.png)"
        )
        if not filepath:
            return

        try:
            cv2.imwrite(filepath, frame)
            self._status(f"截图已保存: {filepath}")
            logger.info("截图保存: %s", filepath)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存截图失败: {e}")

    def _status(self, text: str):
        """更新状态栏（主线程调用）"""
        self.status_label.setText(text)

    # === 跨线程信号槽 ===

    def _on_frame_update(self, frame):
        """更新视频帧显示（主线程）"""
        import cv2

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line,
                          QImage.Format.Format_RGB888)

        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(self.video_frame.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)

        self.video_label.setPixmap(scaled)

    def _on_status_update(self, text: str):
        """更新状态（主线程）"""
        self._status(text)

    def _on_buttons_update(self, is_playing: bool, has_frame: bool):
        """更新按钮状态（主线程）"""
        self.play_btn.setEnabled(True)
        self.play_btn.setText("暂停" if is_playing else "播放")
        self.stop_btn.setEnabled(is_playing)
        self.screenshot_btn.setEnabled(has_frame)


class PreviewWindow(QWidget):
    """独立预览窗口"""

    closed = pyqtSignal(object)  # 发送自身引用
    _frame_ready = pyqtSignal(object)
    _status_ready = pyqtSignal(str)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {url}")
        self.resize(800, 600)

        self._url = url
        self._capture = None
        self._running = False
        self._thread = None
        self._current_frame = None

        self._init_ui()

        # 连接信号
        self._frame_ready.connect(self._on_frame_update)
        self._status_ready.connect(self._on_status_update)

        # 开始播放
        self._start()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 视频显示
        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.video_label)

        # 控制栏
        ctrl_layout = QHBoxLayout()

        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(self._stop)
        ctrl_layout.addWidget(self.stop_btn)

        self.screenshot_btn = QPushButton("截图")
        self.screenshot_btn.clicked.connect(self._screenshot)
        ctrl_layout.addWidget(self.screenshot_btn)

        ctrl_layout.addStretch()

        self.status_label = QLabel("正在连接...")
        ctrl_layout.addWidget(self.status_label)

        layout.addLayout(ctrl_layout)

    def _start(self):
        """开始播放"""
        self._thread = threading.Thread(
            target=self._capture_thread, args=(self._url,), daemon=True
        )
        self._thread.start()

    def _capture_thread(self, url: str):
        """后台捕获线程"""
        import cv2

        try:
            self._capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            if not self._capture.isOpened():
                self._status_ready.emit("连接失败")
                return

            self._running = True
            self._status_ready.emit("已连接")

            while self._running:
                ret, frame = self._capture.read()
                if not ret:
                    break

                self._current_frame = frame.copy()
                self._frame_ready.emit(frame)
                time.sleep(0.04)

        except Exception as e:
            logger.error("预览窗口错误: %s", e)
        finally:
            self._running = False
            if self._capture:
                self._capture.release()

    def _stop(self):
        """停止播放"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.video_label.setText("已停止")

    def _screenshot(self):
        """截图"""
        if self._current_frame is None:
            return

        import cv2
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath, _ = QFileDialog.getSaveFileName(
            self, "保存截图", f"screenshot_{timestamp}.jpg",
            "JPEG (*.jpg);;PNG (*.png)"
        )
        if filepath:
            cv2.imwrite(filepath, self._current_frame)

    def closeEvent(self, event):
        """关闭窗口时停止播放"""
        self._stop()
        self.closed.emit(self)
        super().closeEvent(event)

    def _on_frame_update(self, frame):
        """更新帧（主线程）"""
        import cv2

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line,
                          QImage.Format.Format_RGB888)

        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(self.video_label.size(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.video_label.setPixmap(scaled)

    def _on_status_update(self, text: str):
        """更新状态（主线程）"""
        self.status_label.setText(text)
