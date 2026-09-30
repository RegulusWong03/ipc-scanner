#!/usr/bin/env python3
"""IPC/NVR 扫描管理工具 — 入口文件"""

import sys
import logging

from _version import __version__, __app_name_cn__
from PyQt6.QtWidgets import QApplication

from device.storage import init_db
from logger.op_log import init_log_db
from ui.main_window import MainWindow
from ui.styles import APP_STYLESHEET


def setup_logging():
    """配置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("%s v%s 启动", __app_name_cn__, __version__)


def main():
    setup_logging()
    init_db()
    init_log_db()

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name_cn__)
    app.setApplicationVersion(__version__)
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.setWindowTitle(f"{__app_name_cn__} v{__version__}")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
