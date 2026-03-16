# group-site-manager/ui/main_window.py
"""
主窗口模块 (main_window)

职责：
    实现整个应用程序的主窗口，包括左侧导航栏、右侧内容区和全局操作栏。
    负责初始化配置和 Git 引擎，处理界面路由切换，提供外观切换和同步状态显示。
"""

import logging
import sys
import threading
import tkinter.messagebox as messagebox
import webbrowser
from pathlib import Path
from typing import Optional

import customtkinter as ctk

# 确保可以导入 core 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config_manager import AppConfig
from core.git_engine import GitManager
from core.preview_engine import HugoPreview

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")



class MainWindow(ctk.CTk):
    """应用程序主窗口"""

    NAV_ITEMS = [
        ("新闻动态", "post"),
        ("团队成员", "authors"),
        ("发表成果", "publication"),
        ("研究资源", "resource"),
        ("研究方向", "research_directions"),   # 新增
        ("研究领域", "research_fields"),        # 新增
        ("科研项目", "projects"),                # 新增
        ("全局配置", "settings"),
    ]

    def __init__(self):
        super().__init__()

        self.title("Group Site Manager")
        self.geometry("1200x700")
        self.minsize(900, 500)

        # 初始化核心组件
        self.config = AppConfig()
        self.config.load_or_create()
        self.git_manager = GitManager(self.config.repo_path)
        self.preview_engine = HugoPreview()

        self.current_nav_button: Optional[ctk.CTkButton] = None
        self.current_content_frame: Optional[ctk.CTkFrame] = None
        self.current_module: Optional[str] = None

        # 构建界面
        self._create_layout()
        self._create_nav_buttons()
        self._create_bottom_panel()
        self._create_main_content_area()
        self.select_frame_by_name("post")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ---------- 布局 ----------
    def _create_layout(self):
        """创建左右两栏布局"""
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(1, weight=1)

        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

    # ---------- 左侧导航栏 ----------
    def _create_nav_buttons(self):
        logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="Group Site Manager",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        nav_container = ctk.CTkScrollableFrame(self.sidebar_frame, label_text="导航")
        nav_container.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        nav_container.grid_columnconfigure(0, weight=1)

        self.nav_buttons = {}
        for i, (display_name, internal_name) in enumerate(self.NAV_ITEMS):
            btn = ctk.CTkButton(
                nav_container,
                text=display_name,
                anchor="w",
                command=lambda name=internal_name: self.select_frame_by_name(name),
            )
            btn.grid(row=i, column=0, padx=5, pady=5, sticky="ew")
            self.nav_buttons[internal_name] = btn

    def _create_bottom_panel(self):
        bottom_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        bottom_frame.grid(row=2, column=0, padx=10, pady=20, sticky="ew")
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.appearance_mode_menu = ctk.CTkOptionMenu(
            bottom_frame,
            values=["Light", "Dark", "System"],
            command=self.change_appearance_mode_event,
        )
        self.appearance_mode_menu.grid(row=0, column=0, pady=5, sticky="ew")
        self.appearance_mode_menu.set("System")

        status_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        status_frame.grid(row=1, column=0, pady=5, sticky="ew")

        ctk.CTkLabel(status_frame, text="Git 状态:").grid(row=0, column=0, padx=(0, 5))

        self.sync_status_dot = ctk.CTkLabel(
            status_frame,
            text="●",
            font=ctk.CTkFont(size=16),
            text_color=self._get_git_status_color(),
        )
        self.sync_status_dot.grid(row=0, column=1)

        refresh_btn = ctk.CTkButton(
            status_frame,
            text="刷新",
            width=50,
            command=self.update_git_status,
        )
        refresh_btn.grid(row=0, column=2, padx=(10, 0))

    def _get_git_status_color(self) -> str:
        return "green" if self.git_manager.is_valid() else "red"

    def update_git_status(self):
        self.sync_status_dot.configure(text_color=self._get_git_status_color())

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    # ---------- 右侧主工作区 ----------
    def _create_main_content_area(self):
        """创建右侧工具栏和内容容器（包含所有操作按钮）"""
        toolbar_frame = ctk.CTkFrame(self.main_frame, height=50, corner_radius=0)
        toolbar_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        toolbar_frame.grid_columnconfigure(5, weight=1)

        # 新建按钮
        self.new_btn = ctk.CTkButton(
            toolbar_frame,
            text="➕ 新建",
            command=self._on_new_item,
            width=80,
        )
        self.new_btn.grid(row=0, column=0, padx=5)

        # Git 操作按钮
        self.pull_btn = ctk.CTkButton(
            toolbar_frame,
            text="⬇️ 拉取更新",
            command=self.pull_updates,
            width=100,
        )
        self.pull_btn.grid(row=0, column=1, padx=5)

        self.commit_btn = ctk.CTkButton(
            toolbar_frame,
            text="📝 提交并推送",
            command=self.commit_and_push,
            width=120,
        )
        self.commit_btn.grid(row=0, column=2, padx=5)

        self.status_btn = ctk.CTkButton(
            toolbar_frame,
            text="🔄 刷新状态",
            command=self.update_git_status,
            width=100,
        )
        self.status_btn.grid(row=0, column=3, padx=5)

        # 预览按钮
        self.preview_btn = ctk.CTkButton(
            toolbar_frame,
            text="🌐 本地预览",
            command=self.toggle_preview,
            width=100,
        )
        self.preview_btn.grid(row=0, column=4, padx=5)

        toolbar_frame.grid_columnconfigure(5, weight=1)

        # 内容容器（改为普通 Frame，不再滚动）
        self.content_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content_container.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.content_container.grid_columnconfigure(0, weight=1)
        self.content_container.grid_rowconfigure(0, weight=1)   # 关键：让内部框架可拉伸
    def _show_projects_table(self):
        """显示科研项目管理表格"""
        if self.current_content_frame:
            self.current_content_frame.destroy()
        from ui.forms import ProjectsTableFrame  # 修正导入
        frame = ProjectsTableFrame(
            self.content_container,
            on_save_callback=self._show_projects_table  # 保存后重新显示表格
        )
        frame.grid(row=0, column=0, sticky="nsew")
        self.current_content_frame = frame
    # ---------- 路由与视图切换 ----------
    def select_frame_by_name(self, name: str):
        logger.info(f"切换到模块: {name}")

        if self.current_nav_button:
            self.current_nav_button.configure(fg_color="transparent")
        new_button = self.nav_buttons.get(name)
        if new_button:
            new_button.configure(fg_color=("gray75", "gray25"))
            self.current_nav_button = new_button

        self.current_module = name

        # === 核心修正：针对 projects 模块处理按钮状态 ===
        if name == "projects":
            self._show_projects_table()
        else:
            self.new_btn.configure(state="normal")
            self._show_list()

        

    def _show_list(self):
        """显示当前模块的列表视图"""
        if self.current_content_frame:
            self.current_content_frame.destroy()

        # 注意：需导入 ContentListFrame
        from ui.forms import ContentListFrame

        list_frame = ContentListFrame(
            self.content_container,
            module_name=self.current_module,
            on_edit_callback=self._on_edit_item
        )
        list_frame.grid(row=0, column=0, sticky="nsew")
        self.current_content_frame = list_frame

    def _on_edit_item(self, folder_name: str):
        self._show_form(folder_name)

    def _on_new_item(self):
        self._show_form(None)

    def _show_form(self, folder_name: Optional[str]):
        if self.current_content_frame:
            self.current_content_frame.destroy()

        from ui.forms import ContentFormFrame

        form_frame = ContentFormFrame(
            self.content_container,
            module_name=self.current_module,
            folder_name=folder_name,
            on_save_callback=self._show_list,
            on_cancel_callback=self._show_list
        )
        form_frame.grid(row=0, column=0, sticky="nsew")
        self.current_content_frame = form_frame

    # ---------- 预览功能 ----------
    def toggle_preview(self):
        if self.preview_engine.is_running():
            self.preview_engine.stop()
            self.preview_btn.configure(text="🌐 本地预览")
            messagebox.showinfo("预览已停止", "Hugo 预览服务器已关闭。")
        else:
            if not self.preview_engine.is_available():
                messagebox.showerror("错误", "未找到 Hugo 命令，请确保已安装 Hugo 并将其添加到 PATH。")
                return
            success = self.preview_engine.start(self.config.repo_path)
            if success:
                self.preview_btn.configure(text="🛑 停止预览")
                messagebox.showinfo("预览已启动", "Hugo 预览服务器已在后台运行。\n浏览器已自动打开 http://localhost:1313")
            else:
                messagebox.showerror("错误", "启动 Hugo 预览失败，请检查控制台日志。")

    # ---------- Git 操作 ----------
    def pull_updates(self):
        self.pull_btn.configure(state="disabled")
        self.update_idletasks()

        def task():
            success, msg = self.git_manager.pull_latest()
            self.after(0, lambda: self._pull_complete(success, msg))

        threading.Thread(target=task, daemon=True).start()

    def _pull_complete(self, success, msg):
        self.pull_btn.configure(state="normal")
        if success:
            messagebox.showinfo("拉取成功", msg)
        else:
            messagebox.showerror("拉取失败", msg)

    def commit_and_push(self):
        dialog = ctk.CTkInputDialog(
            text="请输入本次更新的备注信息（例如：更新了论文）:",
            title="提交备注"
        )
        commit_msg = dialog.get_input()
        if commit_msg is None:
            return
        if not commit_msg.strip():
            commit_msg = "Update content via Group Site Manager"

        self.commit_btn.configure(state="disabled")
        self.update_idletasks()

        def task():
            success, msg = self.git_manager.commit_and_push(commit_message=commit_msg)
            self.after(0, lambda: self._commit_complete(success, msg))

        threading.Thread(target=task, daemon=True).start()

    def _commit_complete(self, success, msg):
        self.commit_btn.configure(state="normal")
        if success:
            messagebox.showinfo("提交成功", msg)
        else:
            messagebox.showerror("提交失败", msg)

    # ---------- 关闭 ----------
    def on_closing(self):
        self.preview_engine.stop()
        logger.info("应用程序关闭")
        self.destroy()