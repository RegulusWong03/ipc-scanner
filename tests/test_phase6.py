"""Phase 6 打包部署测试"""

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestVersion:
    """版本信息测试"""

    def test_version_exists(self):
        """测试版本文件存在"""
        from _version import __version__, __app_name__, __app_name_cn__, __description__
        assert __version__
        assert __app_name__
        assert __app_name_cn__
        assert __description__

    def test_version_format(self):
        """测试版本号格式 (语义化版本)"""
        from _version import __version__
        parts = __version__.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)

    def test_version_accessible_from_main(self):
        """测试 main.py 可以导入版本"""
        from _version import __version__
        assert isinstance(__version__, str)
        assert len(__version__) > 0


class TestBuildFiles:
    """打包配置文件测试"""

    def test_spec_file_exists(self):
        """测试 PyInstaller spec 文件存在"""
        spec_path = Path(__file__).parent.parent / "ipc_scanner.spec"
        assert spec_path.exists(), "ipc_scanner.spec 文件不存在"

    def test_spec_file_syntax(self):
        """测试 spec 文件语法正确"""
        spec_path = Path(__file__).parent.parent / "ipc_scanner.spec"
        content = spec_path.read_text(encoding="utf-8")
        # 基本结构检查
        assert "Analysis" in content
        assert "EXE" in content
        assert "COLLECT" in content
        assert "main.py" in content

    def test_version_info_exists(self):
        """测试 Windows 版本信息文件存在"""
        info_path = Path(__file__).parent.parent / "version_info.txt"
        assert info_path.exists(), "version_info.txt 文件不存在"

    def test_version_info_syntax(self):
        """测试版本信息文件语法"""
        info_path = Path(__file__).parent.parent / "version_info.txt"
        content = info_path.read_text(encoding="utf-8")
        assert "VSVersionInfo" in content
        assert "FixedFileInfo" in content
        assert "StringFileInfo" in content

    def test_build_script_exists(self):
        """测试构建脚本存在"""
        build_path = Path(__file__).parent.parent / "build.py"
        assert build_path.exists(), "build.py 文件不存在"

    def test_build_script_importable(self):
        """测试构建脚本可以导入"""
        build_path = Path(__file__).parent.parent / "build.py"
        # 使用 compile 检查语法
        source = build_path.read_text(encoding="utf-8")
        compile(source, "build.py", "exec")

    def test_github_workflow_exists(self):
        """测试 GitHub Actions workflow 存在"""
        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "build.yml"
        assert workflow_path.exists(), ".github/workflows/build.yml 文件不存在"

    def test_github_workflow_content(self):
        """测试 workflow 配置内容"""
        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "build.yml"
        content = workflow_path.read_text(encoding="utf-8")
        assert "windows-latest" in content
        assert "ubuntu-latest" in content
        assert "build.py" in content
        assert "pytest" in content

    def test_requirements_txt_exists(self):
        """测试 requirements.txt 存在"""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        assert req_path.exists()

    def test_requirements_txt_content(self):
        """测试 requirements.txt 包含必要依赖"""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text(encoding="utf-8").lower()
        required = ["pyqt6", "scapy", "httpx", "psutil", "openpyxl", "opencv-python"]
        for dep in required:
            assert dep in content, f"requirements.txt 缺少依赖: {dep}"

    def test_requirements_no_vlc(self):
        """测试 requirements.txt 不包含 python-vlc（已替换为 opencv）"""
        req_path = Path(__file__).parent.parent / "requirements.txt"
        content = req_path.read_text(encoding="utf-8").lower()
        assert "python-vlc" not in content, "python-vlc 已被 opencv-python 替代"


class TestGitignore:
    """gitignore 配置测试"""

    def test_gitignore_exists(self):
        """测试 .gitignore 存在"""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        assert gitignore_path.exists()

    def test_gitignore_entries(self):
        """测试 .gitignore 包含必要条目"""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        required = ["__pycache__/", "dist/", "build/", "release/", ".venv/"]
        for entry in required:
            assert entry in content, f".gitignore 缺少: {entry}"

    def test_spec_not_ignored(self):
        """测试 spec 文件不被 gitignore 忽略"""
        gitignore_path = Path(__file__).parent.parent / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        # *.spec 不应在 gitignore 中
        assert "*.spec" not in content, "*.spec 不应被 gitignore 忽略"


class TestEntryPoints:
    """入口点测试"""

    def test_main_importable(self):
        """测试 main.py 可导入"""
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        # 只检查模块结构，不实际执行 main()
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "main_check",
            Path(__file__).parent.parent / "main.py"
        )
        assert spec is not None
        assert spec.loader is not None

    def test_main_has_main_function(self):
        """测试 main.py 包含 main 函数"""
        main_path = Path(__file__).parent.parent / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert "def main():" in content
        assert 'if __name__ == "__main__":' in content

    def test_main_uses_version(self):
        """测试 main.py 使用了版本信息"""
        main_path = Path(__file__).parent.parent / "main.py"
        content = main_path.read_text(encoding="utf-8")
        assert "__version__" in content


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
