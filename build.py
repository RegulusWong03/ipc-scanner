#!/usr/bin/env python3
"""打包构建脚本 — 跨平台支持 Windows/Linux/macOS

使用方法:
    python build.py              # 使用 spec 文件打包（推荐）
    python build.py --onefile    # 单文件模式打包
    python build.py --clean      # 清理后重新打包
    python build.py --test       # 打包前先运行测试
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
SPEC_FILE = BASE_DIR / "ipc_scanner.spec"


def get_platform_info():
    """获取当前平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "windows", "amd64" if machine == "amd64" else machine
    elif system == "linux":
        return "linux", machine
    elif system == "darwin":
        return "macos", machine
    else:
        return system, machine


def run_tests():
    """运行测试"""
    print("=" * 60)
    print("Running tests...")
    print("=" * 60)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=BASE_DIR,
    )
    if result.returncode != 0:
        print("\n[X] Tests failed! Aborting build.")
        sys.exit(1)

    print("\n[OK] All tests passed!")


def clean():
    """清理构建目录"""
    print("Cleaning build artifacts...")

    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed: {d}")

    # 清理 __pycache__
    for pycache in BASE_DIR.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)

    # 清理 .pyc 文件
    for pyc in BASE_DIR.rglob("*.pyc"):
        pyc.unlink()

    print("  Clean complete!")


def build(use_spec=True, onefile=False):
    """执行打包"""
    system, arch = get_platform_info()

    print("=" * 60)
    print(f"Building for {system} ({arch})")
    print("=" * 60)

    # 确保 PyInstaller 已安装
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    if use_spec and SPEC_FILE.exists() and not onefile:
        # 使用 spec 文件（目录模式）
        cmd = [sys.executable, "-m", "PyInstaller", str(SPEC_FILE)]
    elif onefile:
        # 单文件模式
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onefile",
            "--windowed",
            "--name", "IPCScanner",
            "--add-data", f"{BASE_DIR / '_version.py'}{os.pathsep}.",
            "--hidden-import", "PyQt6.QtSvg",
            "--hidden-import", "PyQt6.QtNetwork",
            "--hidden-import", "PyQt6.QtWidgets",
            "--hidden-import", "PyQt6.QtCore",
            "--hidden-import", "PyQt6.QtGui",
        ]
        # Windows 额外参数
        if system == "windows":
            cmd.extend([
                "--icon", str(BASE_DIR / "assets" / "icon.ico"),
                "--version-file", str(BASE_DIR / "version_info.txt"),
            ])
    else:
        # 目录模式（默认）
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--onedir",
            "--windowed",
            "--name", "IPCScanner",
            "--add-data", f"{BASE_DIR / '_version.py'}{os.pathsep}.",
        ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)

    if result.returncode != 0:
        print("\n[X] Build failed!")
        sys.exit(1)

    print("\n[OK] Build successful!")

    # 显示输出
    if onefile:
        # 单文件模式
        if system == "windows":
            exe_path = DIST_DIR / "IPCScanner.exe"
        else:
            exe_path = DIST_DIR / "IPCScanner"
        
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"  Output: {exe_path}")
            print(f"  Size: {size_mb:.1f} MB")
    else:
        # 目录模式
        if system == "windows":
            exe_path = DIST_DIR / "IPCScanner" / "IPCScanner.exe"
        else:
            exe_path = DIST_DIR / "IPCScanner" / "IPCScanner"

        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"  Output: {exe_path}")
            print(f"  Size: {size_mb:.1f} MB")
        else:
            app_dir = DIST_DIR / "IPCScanner"
            if app_dir.exists():
                total_size = sum(f.stat().st_size for f in app_dir.rglob("*") if f.is_file())
                print(f"  Output directory: {app_dir}")
                print(f"  Total size: {total_size / (1024 * 1024):.1f} MB")


def package(onefile=False):
    """创建发布包"""
    system, arch = get_platform_info()

    print("\n" + "=" * 60)
    print("Creating release package...")
    print("=" * 60)

    # 读取版本号
    version = {}
    with open(BASE_DIR / "_version.py", encoding="utf-8") as f:
        exec(f.read(), version)
    ver = version.get("__version__", "1.0.0")

    release_dir = BASE_DIR / "release"
    release_dir.mkdir(exist_ok=True)

    if onefile:
        # 单文件模式：直接复制 exe/可执行文件
        if system == "windows":
            exe_src = DIST_DIR / "IPCScanner.exe"
            exe_dst = release_dir / f"IPCScanner-{ver}-win-{arch}.exe"
        else:
            exe_src = DIST_DIR / "IPCScanner"
            exe_dst = release_dir / f"IPCScanner-{ver}-linux-{arch}"

        if exe_src.exists():
            shutil.copy2(exe_src, exe_dst)
            # Linux 添加执行权限
            if system == "linux":
                exe_dst.chmod(0o755)
            print(f"  Package: {exe_dst}")
            print(f"  Size: {exe_dst.stat().st_size / (1024 * 1024):.1f} MB")
        else:
            print(f"  [X] Executable not found: {exe_src}")
            sys.exit(1)

    elif system == "windows":
        # Windows 目录模式: 创建 zip
        import zipfile
        zip_name = f"IPCScanner-{ver}-win-{arch}.zip"
        zip_path = release_dir / zip_name

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            app_dir = DIST_DIR / "IPCScanner"
            for file in app_dir.rglob("*"):
                if file.is_file():
                    arcname = f"IPCScanner/{file.relative_to(app_dir)}"
                    zf.write(file, arcname)

        print(f"  Package: {zip_path}")
        print(f"  Size: {zip_path.stat().st_size / (1024 * 1024):.1f} MB")

    elif system == "linux":
        # Linux 目录模式: 创建 tar.gz
        import tarfile
        tar_name = f"IPCScanner-{ver}-linux-{arch}.tar.gz"
        tar_path = release_dir / tar_name

        with tarfile.open(tar_path, "w:gz") as tf:
            app_dir = DIST_DIR / "IPCScanner"
            tf.add(app_dir, arcname="IPCScanner")

        print(f"  Package: {tar_path}")
        print(f"  Size: {tar_path.stat().st_size / (1024 * 1024):.1f} MB")

    else:
        # macOS: 创建 dmg (需要额外工具)
        print("  macOS packaging requires create-dmg tool")
        print("  Output available in dist/IPCScanner/")


def main():
    parser = argparse.ArgumentParser(description="IPC Scanner Build Script")
    parser.add_argument("--onefile", action="store_true", help="Build as single executable")
    parser.add_argument("--clean", action="store_true", help="Clean build directories first")
    parser.add_argument("--test", action="store_true", help="Run tests before building")
    parser.add_argument("--package", action="store_true", help="Create release package after build")
    parser.add_argument("--skip-build", action="store_true", help="Skip build, only package")

    args = parser.parse_args()

    if args.clean:
        clean()

    if args.test:
        run_tests()

    if not args.skip_build:
        build(use_spec=SPEC_FILE.exists(), onefile=args.onefile)

    if args.package:
        package(onefile=args.onefile)

    print("\nDone!")


if __name__ == "__main__":
    main()
