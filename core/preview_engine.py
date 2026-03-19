# group-site-manager/core/preview_engine.py
"""
Hugo 本地预览引擎 (preview_engine)

职责：
    查找系统中的 hugo 可执行文件，启动/停止本地预览服务器。
    使用 subprocess.Popen 在后台运行 `hugo server -D`，并记录进程 PID。
    提供停止预览的方法，并在程序退出时自动清理。

技术栈：
    - subprocess：启动和管理子进程
    - shutil：查找可执行文件
    - webbrowser：自动打开浏览器
    - logging：记录操作日志
"""

import logging
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class HugoPreview:
    """Hugo 本地预览管理器"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.hugo_path: Optional[str] = None

    def is_available(self) -> bool:
        """检查系统中是否存在 hugo 命令"""
        self.hugo_path = shutil.which("hugo")
        return self.hugo_path is not None

    def start(self, repo_path: Path) -> bool:
        """
        启动 Hugo 预览服务器。

        Args:
            repo_path: 本地仓库路径（即网站根目录）

        Returns:
            bool: 启动成功返回 True，否则 False
        """
        if not self.is_available():
            logger.error("未找到 hugo 命令，请确保已安装 Hugo")
            return False

        if self.is_running():
            logger.warning("预览服务器已在运行，先停止当前进程")
            self.stop()

        try:
            # 在仓库根目录下执行 hugo server -D
            self.process = subprocess.Popen(
                [self.hugo_path, "server", "-D"],
                cwd=str(repo_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info(f"Hugo 预览服务器已启动，PID: {self.process.pid}")
            # 等待一小段时间确保服务器启动成功
            import time
            time.sleep(2)
            # 自动打开浏览器
            webbrowser.open("http://localhost:1313")
            return True
        except Exception as e:
            logger.exception(f"启动 Hugo 预览失败: {e}")
            return False

    def stop(self) -> None:
        """停止 Hugo 预览服务器（终止进程）"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info(f"Hugo 预览服务器已停止，PID: {self.process.pid}")
            self.process = None
        else:
            logger.debug("没有正在运行的预览服务器")

    def is_running(self) -> bool:
        """检查预览服务器是否正在运行"""
        return self.process is not None and self.process.poll() is None

    def __del__(self):
        """析构时自动停止预览"""
        self.stop()
