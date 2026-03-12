# group-site-manager/ui/forms.py
"""
内容列表与编辑表单模块 (forms)

职责：
    提供内容列表视图（ContentListFrame）和内容编辑表单（ContentFormFrame），
    用于展示和编辑 Hugo 内容条目。

技术栈：
    - customtkinter：界面组件
    - tkinter.filedialog：文件选择对话框
    - tkinter.messagebox：消息提示框
    - threading：异步加载数据避免 UI 卡顿
    - core.content_parser：内容读写
"""

import threading
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
from pathlib import Path
from typing import Callable, Optional, Dict, Any

import customtkinter as ctk

from core.content_parser import ContentManager


class ContentListFrame(ctk.CTkScrollableFrame):
    """
    可滚动的内容列表框架，显示指定模块的所有条目。

    每个条目显示标题、日期和一个“编辑”按钮。点击编辑按钮调用 on_edit_callback。
    """

    def __init__(self, master, module_name: str, on_edit_callback: Callable[[str], None], **kwargs):
        """
        Args:
            master: 父容器
            module_name: 模块内部名称，如 'post', 'authors'
            on_edit_callback: 当点击编辑时调用，传入文件夹名（folder_name）
        """
        super().__init__(master, **kwargs)
        self.module_name = module_name
        self.on_edit_callback = on_edit_callback
        self.content_manager = ContentManager()

        # 显示加载状态
        self.loading_label = ctk.CTkLabel(self, text="加载中...", font=ctk.CTkFont(size=14))
        self.loading_label.pack(pady=20)

        # 异步加载数据
        self.after(100, self._load_items)  # 延迟一点让 UI 先渲染

    def _load_items(self):
        """在工作线程中加载列表，避免 UI 阻塞"""
        def load():
            success, data = self.content_manager.list_items(self.module_name)
            self.after(0, lambda: self._display_items(success, data))

        threading.Thread(target=load, daemon=True).start()

    def _display_items(self, success: bool, data):
        """显示加载后的条目"""
        # 移除加载标签
        self.loading_label.pack_forget()

        if not success:
            # 显示错误信息
            error_label = ctk.CTkLabel(self, text=f"加载失败：{data}", text_color="red")
            error_label.pack(pady=20)
            return

        items = data if success else []
        if not items:
            # 空状态
            empty_label = ctk.CTkLabel(self, text="暂无内容，点击上方「新建」开始。")
            empty_label.pack(pady=20)
            return

        # 为每个条目创建行
        for item in items:
            self._create_item_row(item)

    def _create_item_row(self, item: Dict[str, Any]):
        """创建单个条目行"""
        row_frame = ctk.CTkFrame(self)
        row_frame.pack(fill="x", padx=5, pady=2)

        # 标题和日期
        title = item.get('title', '无标题')
        date = item.get('date', '')
        display_text = f"{title}  [{date}]" if date else title

        info_label = ctk.CTkLabel(row_frame, text=display_text, anchor="w")
        info_label.pack(side="left", padx=10, pady=5, fill="x", expand=True)

        # 编辑按钮
        edit_btn = ctk.CTkButton(
            row_frame,
            text="编辑",
            width=60,
            command=lambda folder=item['folder_name']: self.on_edit_callback(folder)
        )
        edit_btn.pack(side="right", padx=10, pady=5)

    def refresh(self):
        """刷新列表（重新加载）"""
        # 清空现有内容
        for widget in self.winfo_children():
            widget.destroy()
        self.loading_label = ctk.CTkLabel(self, text="加载中...", font=ctk.CTkFont(size=14))
        self.loading_label.pack(pady=20)
        self._load_items()


class ContentFormFrame(ctk.CTkFrame):
    """
    内容编辑表单，支持新建和更新。

    根据模块类型动态调整字段：
        - authors 模块：增加身份类别选项
        - publication 模块：增加 BibTeX 引用输入
    其他模块只显示通用字段（标题、日期、正文、图片上传）。
    """

    def __init__(self,
                 master,
                 module_name: str,
                 folder_name: Optional[str] = None,
                 on_save_callback: Optional[Callable[[], None]] = None,
                 on_cancel_callback: Optional[Callable[[], None]] = None,
                 **kwargs):
        """
        Args:
            master: 父容器
            module_name: 模块内部名称
            folder_name: 如果为 None，表示新建；否则为更新，传入原文件夹名
            on_save_callback: 保存成功后调用的回调（通常返回列表视图）
            on_cancel_callback: 取消时调用的回调
        """
        super().__init__(master, **kwargs)
        self.module_name = module_name
        self.folder_name = folder_name
        self.on_save_callback = on_save_callback
        self.on_cancel_callback = on_cancel_callback
        self.content_manager = ContentManager()

        # 表单数据存储
        self.form_data = {}
        self.image_path_var = ctk.StringVar()  # 存储图片路径

        # 创建界面
        self._create_widgets()

        # 如果是更新，加载现有数据
        if self.folder_name:
            self._load_existing_data()

    def _create_widgets(self):
        """构建表单界面"""
        # 标题行
        ctk.CTkLabel(self, text="标题：", anchor="w").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.title_entry = ctk.CTkEntry(self, width=400)
        self.title_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        # 日期行
        ctk.CTkLabel(self, text="日期 (YYYY-MM-DD)：", anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.date_entry = ctk.CTkEntry(self, width=200)
        self.date_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        # 可添加日期选择器，暂用输入框

        # 图片上传行
        ctk.CTkLabel(self, text="封面/头像：", anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        image_frame = ctk.CTkFrame(self, fg_color="transparent")
        image_frame.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        self.select_image_btn = ctk.CTkButton(
            image_frame,
            text="选择图片...",
            width=100,
            command=self._select_image
        )
        self.select_image_btn.pack(side="left", padx=(0, 10))

        self.image_path_label = ctk.CTkLabel(image_frame, textvariable=self.image_path_var, width=250, anchor="w")
        self.image_path_label.pack(side="left")

        # 模块特有字段
        row_counter = 3

        # authors 模块特有字段
        if self.module_name == "authors":
            ctk.CTkLabel(self, text="身份类别：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.role_option = ctk.CTkOptionMenu(
                self,
                values=["教授", "副教授", "讲师", "博士后", "博士生", "硕士生", "校友", "其他"]
            )
            self.role_option.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            self.role_option.set("教授")  # 默认值
            row_counter += 1

        # publication 模块特有字段
        if self.module_name == "publication":
            ctk.CTkLabel(self, text="BibTeX 引用：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
            self.bibtex_text = ctk.CTkTextbox(self, height=150, width=400)
            self.bibtex_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="ew")
            row_counter += 1

        # 正文（所有模块都有）
        ctk.CTkLabel(self, text="正文：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
        self.content_text = ctk.CTkTextbox(self, height=300, width=500)
        self.content_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="nsew")
        row_counter += 1

        # 按钮行
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=row_counter, column=0, columnspan=2, pady=20)

        self.save_btn = ctk.CTkButton(button_frame, text="保存", command=self._save, width=100)
        self.save_btn.pack(side="left", padx=10)

        self.cancel_btn = ctk.CTkButton(button_frame, text="取消", command=self._cancel, width=100)
        self.cancel_btn.pack(side="left", padx=10)

        # 配置列权重，使输入框可拉伸
        self.grid_columnconfigure(1, weight=1)

    def _select_image(self):
        """打开文件选择对话框选择图片"""
        file_path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.gif *.bmp"), ("所有文件", "*.*")]
        )
        if file_path:
            self.image_path_var.set(file_path)

    def _load_existing_data(self):
        """加载现有数据填充表单"""
        folder_path = self.content_manager.config.get_module_dir(self.module_name) / self.folder_name
        success, data = self.content_manager.read_item(folder_path)
        if not success:
            # 显示错误并退出编辑
            messagebox.showerror("错误", f"无法加载数据：{data}")
            if self.on_cancel_callback:
                self.on_cancel_callback()
            return

        fm = data['front_matter']
        content = data['content']

        # 填充通用字段
        self.title_entry.insert(0, fm.get('title', ''))
        self.date_entry.insert(0, fm.get('date', ''))

        # 填充正文
        self.content_text.insert("1.0", content)

        # 填充模块特有字段
        if self.module_name == "authors":
            role = fm.get('role', '教授')
            self.role_option.set(role)
        elif self.module_name == "publication":
            bibtex = fm.get('bibtex', '')
            self.bibtex_text.insert("1.0", bibtex)

        # 图片路径无法自动获取，用户需要重新选择或留空

    def _save(self):
        """收集表单数据并保存"""
        # 收集通用字段
        form_data = {
            'title': self.title_entry.get().strip(),
            'date': self.date_entry.get().strip(),
        }
        content = self.content_text.get("1.0", "end-1c")  # 去除末尾换行

        # 收集模块特有字段
        if self.module_name == "authors":
            form_data['role'] = self.role_option.get()
        elif self.module_name == "publication":
            form_data['bibtex'] = self.bibtex_text.get("1.0", "end-1c")

        # 简单验证
        if not form_data['title']:
            messagebox.showwarning("提示", "标题不能为空")
            return

        # 调用保存方法
        image_path = self.image_path_var.get() or None
        success, msg = self.content_manager.save_item(
            module_name=self.module_name,
            form_data=form_data,
            content=content,
            original_folder_name=self.folder_name,
            image_path=image_path
        )

        if success:
            messagebox.showinfo("成功", msg)
            if self.on_save_callback:
                self.on_save_callback()
        else:
            messagebox.showerror("错误", msg)

    def _cancel(self):
        """取消编辑，返回列表"""
        if self.on_cancel_callback:
            self.on_cancel_callback()
