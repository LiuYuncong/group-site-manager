# group-site-manager/main.py
"""
程序主入口
负责初始化配置检查、启动主窗口
"""

import sys
from pathlib import Path

# 确保可以导入 core 和 ui 模块
sys.path.insert(0, str(Path(__file__).parent))

import tkinter.messagebox as messagebox
import customtkinter as ctk

from core.config_manager import AppConfig
from ui.main_window import MainWindow


def check_environment():
    """检查运行环境，主要是仓库路径是否存在"""
    config = AppConfig()
    config.load_or_create()  # 确保配置加载

    repo_path = config.repo_path
    if not repo_path.exists():
        # 弹窗警告（需要先创建 tkinter 根窗口？customtkinter 会自动创建）
        # 这里直接使用 messagebox，但需要先初始化 tkinter
        root = ctk.CTk()  # 临时创建根窗口
        root.withdraw()  # 隐藏
        result = messagebox.askyesno(
            "配置提醒",
            f"本地仓库路径不存在：\n{repo_path}\n\n是否立即打开配置界面进行设置？\n（选择“否”将继续运行，但功能可能受限）"
        )
        root.destroy()
        if result:
            # TODO: 打开配置界面（后续实现）
            # 目前仅提醒后继续运行
            pass
    return config


if __name__ == "__main__":
    # 设置外观
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    # 环境检查
    check_environment()

    # 启动主窗口
    app = MainWindow()
    app.mainloop()