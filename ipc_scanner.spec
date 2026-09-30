# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec 文件 — IPC/NVR 扫描管理工具打包配置

使用方法:
    pyinstaller ipc_scanner.spec

或在 Windows 上:
    pyinstaller ipc_scanner.spec --clean
"""

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# 项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(SPEC))

# 版本信息
VERSION = {}
with open(os.path.join(BASE_DIR, '_version.py')) as f:
    exec(f.read(), VERSION)

block_cipher = None

# === 数据文件 ===
datas = []

# 收集 openpyxl 模板（Excel 样式需要）
datas += collect_data_files('openpyxl')

# === 隐藏导入 ===
hiddenimports = [
    # PyQt6 子模块
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    # 网络相关
    'scapy',
    'scapy.all',
    'httpx',
    'httpx._transports',
    'httpx._transports.default',
    # OpenCV
    'cv2',
    'numpy',
    # XML
    'xml.etree.ElementTree',
    # 数据库
    'sqlite3',
]

# 收集 scapy 子模块（ARP 等功能）
hiddenimports += collect_submodules('scapy')

# 收集 httpx 子模块
hiddenimports += collect_submodules('httpx')

a = Analysis(
    [os.path.join(BASE_DIR, 'main.py')],
    pathex=[BASE_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大模块，减小打包体积
        'matplotlib',
        'scipy',
        'pandas',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        'tkinter',
        'unittest',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# === Windows exe 配置 ===
exe_options = {
    'name': 'IPCScanner',
    'console': False,  # GUI 模式，不显示控制台
    'disable_windowed_traceback': False,
}

# 图标（如果有）
icon_path = os.path.join(BASE_DIR, 'assets', 'icon.ico')
if os.path.exists(icon_path):
    exe_options['icon'] = icon_path

# Windows 版本信息（.exe 属性面板显示）
if sys.platform == 'win32':
    from PyInstaller.utils.hooks import copy_metadata
    datas += copy_metadata('PyQt6')

    exe_options['version'] = os.path.join(BASE_DIR, 'version_info.txt')
    # 如果 version_info.txt 不存在则跳过
    if not os.path.exists(exe_options['version']):
        del exe_options['version']

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 使用 onefile=False（目录模式，启动更快）
    **exe_options,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='IPCScanner',
)
