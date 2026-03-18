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
import logging
from typing import List, Callable, Optional, Dict, Any
import frontmatter
import customtkinter as ctk
import tkinter.messagebox as messagebox
from core.content_parser import ContentManager
import yaml
import re
import bibtexparser
from datetime import datetime


def parse_bibtex_to_dict(bibtex_string):
    """
    解析 BibTeX 字符串，返回包含各字段的字典。
    """
    try:
        parser = bibtexparser.bparser.BibTexParser(common_strings=True)
        bib_database = bibtexparser.loads(bibtex_string, parser)
        if not bib_database.entries:
            return None
        entry = bib_database.entries[0]

        def clean(text):
            if not text:
                return ""
            return re.sub(r'[{}]', '', text).strip()

        title = clean(entry.get('title', ''))
        year = clean(entry.get('year', ''))
        month = clean(entry.get('month', '01')).lower()
        month_map = {'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                     'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                     'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'}
        month = month_map.get(month[:3], '01') if not month.isdigit() else month.zfill(2)
        date_str = f"{year}-{month}-01" if year else datetime.now().strftime('%Y-%m-%d')
        journal = clean(entry.get('journal', entry.get('booktitle', '')))
        abstract = clean(entry.get('abstract', ''))
        doi = clean(entry.get('doi', ''))
        authors_raw = entry.get('author', '')
        authors = [clean(a) for a in authors_raw.split(' and ')] if authors_raw else []
        
        pub_type = entry.get('ENTRYTYPE', 'article')
        pub_type_map = {'article': '2', 'inproceedings': '1', 'conference': '1',
                        'techreport': '3', 'phdthesis': '4', 'mastersthesis': '5',
                        'book': '6', 'incollection': '7'}
        pub_type_code = pub_type_map.get(pub_type, '2')
        
        return {
            'title': title,
            'date': date_str,
            'authors': authors,
            'publication': journal,
            'publication_short': journal,
            'abstract': abstract,
            'doi': doi,
            'publication_type': pub_type_code,
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"BibTeX 解析失败: {e}")
        return None

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
        self.config = self.content_manager.config # 方便后续使用配置路径
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

        # === 建议的顺序：先 pack 删除 (最右)，再 pack 编辑 ===
        delete_btn = ctk.CTkButton(
            row_frame,
            text="删除",
            width=60,
            fg_color="#d9534f",      # 稍微柔和一点的红色
            hover_color="#c9302c",
            command=lambda folder=item['folder_name']: self._delete_item(folder)
        )
        delete_btn.pack(side="right", padx=10, pady=5)

        edit_btn = ctk.CTkButton(
            row_frame,
            text="编辑",
            width=60,
            command=lambda folder=item['folder_name']: self.on_edit_callback(folder)
        )
        edit_btn.pack(side="right", padx=(10, 0), pady=5)

    def refresh(self):
        """刷新列表（重新加载）"""
        # 清空现有内容
        for widget in self.winfo_children():
            widget.destroy()
        self.loading_label = ctk.CTkLabel(self, text="加载中...", font=ctk.CTkFont(size=14))
        self.loading_label.pack(pady=20)
        self._load_items()
    #删除条目
    def _delete_item(self, folder_name: str):
        """弹出确认对话框，删除指定条目"""
        if messagebox.askyesno("确认删除", f"确定要删除“{folder_name}”及其所有内容吗？\n此操作不可撤销。"):
            success, msg = self.content_manager.delete_item(self.module_name, folder_name)
            if success:
                messagebox.showinfo("成功", msg)
                self.refresh()  # 刷新列表
            else:
                messagebox.showerror("错误", msg)

class ContentFormFrame(ctk.CTkScrollableFrame):  # 原为 ctk.CTkFrame
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
        self.config = self.content_manager.config
        self._other_social_links = [] 

        # 表单数据存储
        self.form_data = {}
        self.image_path_var = ctk.StringVar()  # 存储图片路径

        # 创建界面
        self._create_widgets()

        # 如果是更新，加载现有数据
        if self.folder_name:
            self._load_existing_data()
    
    def _import_from_bibtex(self):
        dialog = ctk.CTkInputDialog(
            text="请粘贴 BibTeX 条目内容：",
            title="从 BibTeX 导入"
        )
        bibtex_str = dialog.get_input()
        if not bibtex_str:
            return

        parsed = parse_bibtex_to_dict(bibtex_str)
        if not parsed:
            messagebox.showerror("错误", "无法解析 BibTeX，请检查内容格式。")
            return

        # 填充表单
        self.title_entry.delete(0, 'end')
        self.title_entry.insert(0, parsed.get('title', ''))
        
        self.date_entry.delete(0, 'end')
        self.date_entry.insert(0, parsed.get('date', ''))
        
        authors = parsed.get('authors', [])
        self.authors_text.delete("1.0", "end")
        self.authors_text.insert("1.0", "\n".join(authors))
        
        self.publication_entry.delete(0, 'end')
        self.publication_entry.insert(0, parsed.get('publication', ''))
        
        self.publication_short_entry.delete(0, 'end')
        self.publication_short_entry.insert(0, parsed.get('publication_short', ''))
        
        self.abstract_text.delete("1.0", "end")
        self.abstract_text.insert("1.0", parsed.get('abstract', ''))
        
        self.doi_entry.delete(0, 'end')
        self.doi_entry.insert(0, parsed.get('doi', ''))
        
        pub_type = parsed.get('publication_type', '2')
        pub_type_map = {'1': '1 会议论文', '2': '2 期刊论文', '3': '3 预印本',
                        '4': '4 学位论文', '5': '5 专著', '6': '6 其他'}
        self.pub_type_option.set(pub_type_map.get(pub_type, '2 期刊论文'))
        
        messagebox.showinfo("成功", "BibTeX 解析完成，请检查并补充信息。")

    def _load_user_groups_options(self) -> List[str]:
        """从 people/index.md 和 alumni/_index.md 中动态提取 user_groups 选项，兼容多种 Hugo 结构"""
        options = set()
        default_options = [
            "团队负责人(PI)", "团队合作专家", "专任教师", "博士后",
            "博士研究生", "硕士研究生", "研究员", "管理人员",
            "访问学者", "博士", "硕士", "本科生"
        ]

        def extract_groups(meta_dict):
            """内部辅助：在 metadata 字典中灵活寻找 user_groups"""
            # 兼容 Hugo Blox v7+ (blocks) 和 v5/v6 (sections)
            for key in ['blocks', 'sections']:
                for item in meta_dict.get(key, []):
                    if isinstance(item, dict):
                        options.update(item.get('content', {}).get('user_groups', []))
            # 兼容极简配置或旧版 (直接挂载在 content 下)
            options.update(meta_dict.get('content', {}).get('user_groups', []))

        # 1. 尝试读取在校团队的类别
        people_index = self.config.get_module_dir("people") / "index.md"
        if not people_index.exists():
            people_index = self.config.get_module_dir("people") / "_index.md"

        if people_index.exists():
            try:
                with open(people_index, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    extract_groups(post.metadata)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"读取 {people_index.name} 获取身份类别失败: {e}")

        # 2. 尝试读取校友团队的类别
        alumni_index = self.config.get_module_dir("alumni") / "_index.md"
        if not alumni_index.exists():
            alumni_index = self.config.get_module_dir("alumni") / "index.md"

        if alumni_index.exists():
            try:
                with open(alumni_index, 'r', encoding='utf-8') as f:
                    post = frontmatter.load(f)
                    extract_groups(post.metadata)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.warning(f"读取 {alumni_index.name} 获取身份类别失败: {e}")

        # 合并默认配置
        if not options:
            options.update(default_options)
        else:
            # 补齐隐藏类别
            options.update(["博士", "硕士", "本科生"])

        # 过滤并排序
        return sorted([opt for opt in list(options) if opt and isinstance(opt, str)])
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
                # 1. 身份类别 (系统分类)
                ctk.CTkLabel(self, text="身份组别 (user_groups)：\n(决定显示在哪个页面)", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.user_group_option = ctk.CTkOptionMenu(
                    self,
                    values=self._load_user_groups_options(),
                    width=250
                )
                self.user_group_option.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 添加角色输入框，用于描述具体头衔或角色信息
                ctk.CTkLabel(self, text="头衔/角色 (role)：\n(例如：2021级博士生)", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.role_entry = ctk.CTkEntry(self, width=250)
                self.role_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 入学年份 (enrollment_year) —— 新增
                ctk.CTkLabel(self, text="入学年份：", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
                self.enrollment_year_entry = ctk.CTkEntry(self, width=100, placeholder_text="例如 2023")
                self.enrollment_year_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 排序权重 (weight) —— 新增
                ctk.CTkLabel(self, text="排序权重 (weight)：\n(数值越小越靠前)", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.weight_entry = ctk.CTkEntry(self, width=100, placeholder_text="例如 1, 2, 3...")
                self.weight_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1
                            # 新增：联系邮箱
                ctk.CTkLabel(self, text="邮箱 (email)：", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
                self.email_entry = ctk.CTkEntry(self, width=300)
                self.email_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 新增：组织/单位 (每行格式: 组织名称|组织网址，网址可选)
                ctk.CTkLabel(self, text="组织/单位 (organizations)：\n每行格式：名称|网址 (网址可选)", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.organizations_text = ctk.CTkTextbox(self, height=80, width=300)
                self.organizations_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 新增：教育背景 (每行格式: 学位|学校|年份)
                ctk.CTkLabel(self, text="教育背景 (education)：\n每行格式：学位|学校|年份", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.education_text = ctk.CTkTextbox(self, height=100, width=300)
                self.education_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 新增：社交链接
                ctk.CTkLabel(self, text="Google Scholar 链接：", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
                self.google_scholar_entry = ctk.CTkEntry(self, width=300)
                self.google_scholar_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                ctk.CTkLabel(self, text="ResearchGate 链接：", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
                self.researchgate_entry = ctk.CTkEntry(self, width=300)
                self.researchgate_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

                # 研究方向 (interests)
                ctk.CTkLabel(self, text="研究方向 (interests)：\n每行一项", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                self.interests_text = ctk.CTkTextbox(self, height=120, width=300)
                self.interests_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
                row_counter += 1

        
            
        if self.module_name in ["research_directions", "research_fields"]:
                        ctk.CTkLabel(self, text="摘要 (summary)：", anchor="w", justify="left").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
                        self.summary_entry = ctk.CTkEntry(self, width=400)
                        self.summary_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="ew")
                        row_counter += 1
        elif self.module_name == "publication":
            # 从 BibTeX 导入按钮
            import_btn = ctk.CTkButton(self, text="📥 从 BibTeX 导入", command=self._import_from_bibtex)
            import_btn.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=10, sticky="w")
            row_counter += 1

        
            # 作者
            ctk.CTkLabel(self, text="作者 (每行一位)：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
            self.authors_text = ctk.CTkTextbox(self, height=80, width=300)
            self.authors_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 作者备注
            ctk.CTkLabel(self, text="作者备注 (可选，每行一位)：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
            self.author_notes_text = ctk.CTkTextbox(self, height=80, width=300)
            self.author_notes_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 出版物类型
            ctk.CTkLabel(self, text="出版物类型：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.pub_type_option = ctk.CTkOptionMenu(
                self,
                values=["1 会议论文", "2 期刊论文", "3 预印本", "4 学位论文", "5 专著", "6 其他"],
                width=150
            )
            self.pub_type_option.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            self.pub_type_option.set("2 期刊论文")
            row_counter += 1

            # 出版物名称
            ctk.CTkLabel(self, text="出版物名称：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.publication_entry = ctk.CTkEntry(self, width=300)
            self.publication_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="ew")
            row_counter += 1

            # 出版物简称
            ctk.CTkLabel(self, text="出版物简称：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.publication_short_entry = ctk.CTkEntry(self, width=200)
            self.publication_short_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 摘要
            ctk.CTkLabel(self, text="摘要：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="nw")
            self.abstract_text = ctk.CTkTextbox(self, height=100, width=400)
            self.abstract_text.grid(row=row_counter, column=1, padx=10, pady=5, sticky="ew")
            row_counter += 1

            # DOI
            ctk.CTkLabel(self, text="DOI：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.doi_entry = ctk.CTkEntry(self, width=250)
            self.doi_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 标签
            ctk.CTkLabel(self, text="标签 (逗号分隔)：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.tags_entry = ctk.CTkEntry(self, width=300)
            self.tags_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 是否推荐
            self.featured_var = ctk.BooleanVar(value=False)
            self.featured_check = ctk.CTkCheckBox(self, text="推荐此论文 (featured)", variable=self.featured_var)
            self.featured_check.grid(row=row_counter, column=0, columnspan=2, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 图片说明 (caption)
            ctk.CTkLabel(self, text="图片说明 (可选)：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.image_caption_entry = ctk.CTkEntry(self, width=300)
            self.image_caption_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
            row_counter += 1

            # 相关项目
            ctk.CTkLabel(self, text="相关项目 (逗号分隔)：", anchor="w").grid(row=row_counter, column=0, padx=10, pady=5, sticky="w")
            self.projects_entry = ctk.CTkEntry(self, width=300)
            self.projects_entry.grid(row=row_counter, column=1, padx=10, pady=5, sticky="w")
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
            # 从 front matter 中加载用户组别信息
            # 如果存在用户组别列表，默认选择第一个主要类别显示在下拉框中
            # 注意：当前 UI 限制为单选下拉框，因此多组别的情况会被覆盖
            # 如果读取到的值不在抓取的选项列表中，将其动态插入并设置为当前值

            user_groups = fm.get('user_groups', [])
            if user_groups and isinstance(user_groups, list):
                # 默认取第一个主要类别显示在下拉框中
                if user_groups[0] in self.user_group_option._values:
                    self.user_group_option.set(user_groups[0])
                else:
                    # 如果读取到的值不在抓取的选项列表中，强行插入显示
                    self.user_group_option.configure(values=self.user_group_option._values + [user_groups[0]])
                    self.user_group_option.set(user_groups[0])

            # 从 front matter 中加载角色信息
            # 清空角色输入框并填充读取到的角色值
            role = fm.get('role', '')
            self.role_entry.delete(0, 'end')
            self.role_entry.insert(0, role)
                        # 从 front matter 中加载社交链接
            social = fm.get('social', [])
            gs_link = ""
            rg_link = ""
            email_link = ""
            other_social = []
            for item in social:
                icon = item.get('icon')
                link = item.get('link', '')
                if icon == 'google-scholar':
                    gs_link = link
                elif icon == 'researchgate':
                    rg_link = link
                elif icon == 'envelope':
                    # 邮箱链接格式为 mailto:xxx
                    if link.startswith('mailto:'):
                        email_link = link[7:]  # 去掉 'mailto:'
                    else:
                        email_link = link
                else:
                    other_social.append(item)
            # 加载入学年份（自定义字段 enrollment_year）
            enrollment_year = fm.get('enrollment_year', '')
            self.enrollment_year_entry.delete(0, 'end')
            self.enrollment_year_entry.insert(0, enrollment_year)

            # 加载 weight
            weight = fm.get('weight', '')
            self.weight_entry.delete(0, 'end')
            self.weight_entry.insert(0, str(weight) if weight else '')
            # 填充邮箱、Google Scholar、ResearchGate 输入框
            self.email_entry.delete(0, 'end')
            self.email_entry.insert(0, email_link)
            self.google_scholar_entry.delete(0, 'end')
            self.google_scholar_entry.insert(0, gs_link)
            self.researchgate_entry.delete(0, 'end')
            self.researchgate_entry.insert(0, rg_link)

            # 保存其他社交链接，以便在保存时重新合并
            self._other_social_links = other_social
            # 加载研究方向
            interests = fm.get('interests', [])
            if interests and isinstance(interests, list):
                self.interests_text.delete("1.0", "end")
                self.interests_text.insert("1.0", "\n".join(interests))
            

        if self.module_name in ["research_directions", "research_fields"]:
                summary = fm.get('summary', '')
                self.summary_entry.delete(0, 'end')
                self.summary_entry.insert(0, summary)
        elif self.module_name == "publication":
            self.title_entry.delete(0, 'end')
            self.title_entry.insert(0, fm.get('title', ''))
            
            self.date_entry.delete(0, 'end')
            self.date_entry.insert(0, fm.get('date', ''))
            
            authors = fm.get('authors', [])
            if isinstance(authors, list):
                self.authors_text.delete("1.0", "end")
                self.authors_text.insert("1.0", "\n".join(authors))
                
            author_notes = fm.get('author_notes', [])
            if isinstance(author_notes, list):
                self.author_notes_text.delete("1.0", "end")
                self.author_notes_text.insert("1.0", "\n".join(author_notes))
                
            pub_types = fm.get('publication_types', ['2'])
            if pub_types and isinstance(pub_types, list):
                pub_type_code = str(pub_types[0]) if len(pub_types) > 0 else '2'
                pub_type_map = {'1': '1 会议论文', '2': '2 期刊论文', '3': '3 预印本',
                                '4': '4 学位论文', '5': '5 专著', '6': '6 其他'}
                self.pub_type_option.set(pub_type_map.get(pub_type_code, '2 期刊论文'))
                
            self.publication_entry.delete(0, 'end')
            self.publication_entry.insert(0, fm.get('publication', ''))
            
            self.publication_short_entry.delete(0, 'end')
            self.publication_short_entry.insert(0, fm.get('publication_short', ''))
            
            self.abstract_text.delete("1.0", "end")
            self.abstract_text.insert("1.0", fm.get('abstract', ''))
            
            self.doi_entry.delete(0, 'end')
            self.doi_entry.insert(0, fm.get('doi', ''))
            
            tags = fm.get('tags', [])
            if isinstance(tags, list):
                self.tags_entry.delete(0, 'end')
                self.tags_entry.insert(0, ', '.join(tags))
                
            self.featured_var.set(fm.get('featured', False))
            
            # 安全加载 image caption
            image_data = fm.get('image', {})
            if isinstance(image_data, dict):
                self.image_caption_entry.delete(0, 'end')
                self.image_caption_entry.insert(0, image_data.get('caption', ''))
                
            projects = fm.get('projects', [])
            if isinstance(projects, list):
                self.projects_entry.delete(0, 'end')
                self.projects_entry.insert(0, ', '.join(projects))
                
            # 【修复点】：加载正确的 markdown 正文内容（根据你的环境，这里可能是 content 或 original_content）
            # --- 修改后 ---
            self.content_text.delete("1.0", "end")
            self.content_text.insert("1.0", content) # 直接使用开头提取的 content 变量
    def _save(self):
        """收集表单数据并保存"""
        # 收集通用字段
        form_data = {
            'title': self.title_entry.get().strip(),
            'date': self.date_entry.get().strip(),
        }
        content = self.content_text.get("1.0", "end-1c")  # 去除末尾换行

        # 研究方向和研究领域不需要 date 字段（删除它）
        if self.module_name in ["research_directions", "research_fields"]:
            if 'date' in form_data:
                del form_data['date']

        # 收集模块特有字段
        if self.module_name == "authors":
            # user_groups 信息
            form_data['user_groups'] = [self.user_group_option.get()]

            # role 信息
            role_val = self.role_entry.get().strip()
            form_data['role'] = role_val if role_val else ""
            # 入学年份
            enrollment_year_val = self.enrollment_year_entry.get().strip()
            if enrollment_year_val:
                form_data['enrollment_year'] = enrollment_year_val
            else:
                form_data.pop('enrollment_year', None)  # 避免空字段

            # 排序权重
            weight_val = self.weight_entry.get().strip()
            if weight_val:
                try:
                    form_data['weight'] = int(weight_val)
                except ValueError:
                    messagebox.showwarning("警告", "排序权重必须是整数")
                    return
            else:
                form_data.pop('weight', None)
            # email 信息（单独字段，但也会通过 social 列表存储，这里保留 email 字段兼容旧数据）
            email_val = self.email_entry.get().strip()
            if email_val:
                form_data['email'] = email_val

            # organizations 信息
            org_text = self.organizations_text.get("1.0", "end-1c").strip()
            org_list = []
            if org_text:
                for line in org_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        org_list.append({'name': parts[0].strip(), 'url': parts[1].strip()})
                    else:
                        org_list.append({'name': parts[0].strip()})
            if org_list:
                form_data['organizations'] = org_list

            # education 信息
            edu_text = self.education_text.get("1.0", "end-1c").strip()
            edu_list = []
            if edu_text:
                for line in edu_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split('|', 2)
                    course = parts[0].strip() if len(parts) > 0 else ""
                    institution = parts[1].strip() if len(parts) > 1 else ""
                    year = parts[2].strip() if len(parts) > 2 else ""
                    edu_list.append({'course': course, 'institution': institution, 'year': year})
            if edu_list:
                form_data['education'] = {'courses': edu_list}

            # social links 信息
            social_list = []

            # 邮箱（以 mailto 格式存入 social）
            email_val = self.email_entry.get().strip()
            if email_val:
                social_list.append({'icon': 'envelope', 'icon_pack': 'fas', 'link': f'mailto:{email_val}'})

            # Google Scholar
            gs_link = self.google_scholar_entry.get().strip()
            if gs_link:
                social_list.append({'icon': 'google-scholar', 'icon_pack': 'ai', 'link': gs_link})

            # ResearchGate
            rg_link = self.researchgate_entry.get().strip()
            if rg_link:
                social_list.append({'icon': 'researchgate', 'icon_pack': 'ai', 'link': rg_link})

            # 合并之前保存的其他社交链接
            if hasattr(self, '_other_social_links') and self._other_social_links:
                social_list.extend(self._other_social_links)

            if social_list:
                form_data['social'] = social_list

            # 研究方向
            interests_text = self.interests_text.get("1.0", "end-1c").strip()
            if interests_text:
                interests_list = [line.strip() for line in interests_text.split('\n') if line.strip()]
                if interests_list:
                    form_data['interests'] = interests_list

        elif self.module_name in ["research_directions", "research_fields"]:
            # 摘要字段（已在前面删除了 date）
            summary_val = self.summary_entry.get().strip()
            if summary_val:
                form_data['summary'] = summary_val

        elif self.module_name == "publication":
            
            authors_text = self.authors_text.get("1.0", "end-1c").strip()
            if authors_text:
                form_data['authors'] = [line.strip() for line in authors_text.split('\n') if line.strip()]
                
            notes_text = self.author_notes_text.get("1.0", "end-1c").strip()
            if notes_text:
                form_data['author_notes'] = [line.strip() for line in notes_text.split('\n') if line.strip()]
                
            pub_type_str = self.pub_type_option.get()
            pub_type_code = pub_type_str.split()[0]
            form_data['publication_types'] = [pub_type_code]
            
            pub_name = self.publication_entry.get().strip()
            if pub_name:
                form_data['publication'] = pub_name
                
            pub_short = self.publication_short_entry.get().strip()
            if pub_short:
                form_data['publication_short'] = pub_short
                
            abstract = self.abstract_text.get("1.0", "end-1c").strip()
            if abstract:
                form_data['abstract'] = abstract
                
            doi = self.doi_entry.get().strip()
            if doi:
                form_data['doi'] = doi
                
            tags_str = self.tags_entry.get().strip()
            if tags_str:
                form_data['tags'] = [tag.strip() for tag in tags_str.split(',') if tag.strip()]
                
            form_data['featured'] = self.featured_var.get()
            
            # 【修复点】：预设 caption，核心处理图片部分将补充 filename
            caption = self.image_caption_entry.get().strip()
            if caption:
                form_data['image'] = {'caption': caption}
                
            projects_str = self.projects_entry.get().strip()
            if projects_str:
                form_data['projects'] = [proj.strip() for proj in projects_str.split(',') if proj.strip()]
                
            content = self.content_text.get("1.0", "end-1c")

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
    

class ProjectsTableFrame(ctk.CTkFrame):
    """科研项目管理表格，支持编辑项目列表"""
    COLUMNS = ["项目编号", "项目名称", "项目来源", "起讫时间", "承担角色", "项目类别"]

    def __init__(self, master, on_save_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_save_callback = on_save_callback
        
        # 延迟导入以避免循环依赖
        from core.content_parser import ContentManager
        self.content_manager = ContentManager()
        self.config = self.content_manager.config
        self.file_path = self.config.get_module_dir("projects") / "_index.md"
        self.rows = []
        
        self._create_widgets()
        self._load_data()

    def _create_widgets(self):
        # 页面标题
        ctk.CTkLabel(self, text="科研项目管理", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)

        # 可编辑的页面标题
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(pady=5, padx=10, fill="x")
        ctk.CTkLabel(title_frame, text="页面标题：", width=100).pack(side="left")
        self.title_entry = ctk.CTkEntry(title_frame, width=300)
        self.title_entry.pack(side="left", padx=5)

        # 表格容器
        self.table_container = ctk.CTkScrollableFrame(self, label_text="项目列表")
        self.table_container.pack(pady=10, padx=10, fill="both", expand=True)

        # === 核心修改 1：将 header_frame 保存为 self.header_frame ===
        self.header_frame = ctk.CTkFrame(self.table_container, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=2)
        for i, col in enumerate(self.COLUMNS):
            ctk.CTkLabel(self.header_frame, text=col, width=120, anchor="w").grid(row=0, column=i, padx=2)

        # 按钮
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(pady=10)
        
        # === 核心修改 2：给命令传参，要求置顶添加 ===
        self.add_btn = ctk.CTkButton(button_frame, text="添加行", command=lambda: self._add_row(at_top=True), width=100)
        self.add_btn.pack(side="left", padx=5)
        
        self.save_btn = ctk.CTkButton(button_frame, text="保存", command=self._save, width=100)
        self.save_btn.pack(side="left", padx=5)
        self.cancel_btn = ctk.CTkButton(button_frame, text="取消", command=self._cancel, width=100)
        self.cancel_btn.pack(side="left", padx=5)

    def _add_row(self, values=None, at_top=False):
        row_frame = ctk.CTkFrame(self.table_container)
        
        # === 核心修改 3：UI 渲染置顶或追加 ===
        if at_top and hasattr(self, 'header_frame'):
            # 在 UI 上将新行紧贴在表头下方
            row_frame.pack(fill="x", pady=2, after=self.header_frame)
        else:
            # 默认：追加到末尾（用于加载已有的文件数据）
            row_frame.pack(fill="x", pady=2)

        entries = []
        for i in range(6):
            entry = ctk.CTkEntry(row_frame, width=120)
            entry.grid(row=0, column=i, padx=2)
            if values and i < len(values):
                entry.insert(0, values[i])
            entries.append(entry)

        del_btn = ctk.CTkButton(row_frame, text="✖", width=30, command=lambda: self._delete_row(row_frame, entries))
        del_btn.grid(row=0, column=6, padx=2)
        
        # === 核心修改 4：逻辑列表置顶或追加 ===
        if at_top:
            self.rows.insert(0, (row_frame, entries))  # 插入到数据最前面，保证保存时在最上面
        else:
            self.rows.append((row_frame, entries))     # 追加到数据末尾

    def _delete_row(self, row_frame, entries):
        row_frame.destroy()
        self.rows = [(f, e) for (f, e) in self.rows if f != row_frame]

    def _load_data(self):
        # 每次加载前清空旧行，防止叠加
        for f, e in self.rows:
            f.destroy()
        self.rows.clear()

        if not self.file_path.exists():
            self.title_entry.insert(0, "科研项目")
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            import frontmatter
            post = frontmatter.loads(content)
            self.title_entry.delete(0, 'end')
            self.title_entry.insert(0, post.metadata.get('title', '科研项目'))

            # === 智能提取表格数据（解决读写一致性 Bug） ===
            table_text = ""
            sections = post.metadata.get('sections', [])
            if sections and isinstance(sections, list) and len(sections) > 0:
                table_text = sections[0].get('content', {}).get('text', '')
            
            if not table_text.strip():
                table_text = post.content

            # 解析每一行
            lines = table_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                # 过滤掉 markdown 表格的分隔符行和表头行
                if line.startswith('|') and not line.startswith('| :---') and '项目编号' not in line:
                    cells = [cell.strip() for cell in line.split('|')[1:-1]]
                    if len(cells) == 6:
                        self._add_row(cells)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"加载项目数据失败: {e}")
            messagebox.showerror("错误", f"加载项目数据失败：{e}")

    def _save(self):
        rows_data = []
        for _, entries in self.rows:
            row = [entry.get().strip() for entry in entries]
            # 如果整行全空则跳过
            if all(cell == '' for cell in row):
                continue
            rows_data.append(row)

        # 构建表格 Markdown
        table = "| " + " | ".join(self.COLUMNS) + " |\n"
        table += "| " + " | ".join([":---"] * 6) + " |\n"
        for row in rows_data:
            table += "| " + " | ".join(row) + " |\n"

        # 构建 front matter
        front_matter = {
            'title': self.title_entry.get().strip() or '科研项目',
            'type': 'landing',
            'sections': [
                {
                    'block': 'markdown',
                    'content': {
                        'title': '科研项目',
                        'text': table
                    },
                    'design': {
                        'columns': '1',
                        'css_class': 'custom-project-table'
                    }
                }
            ]
        }

        # 写入文件
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write("---\n")
                yaml.dump(front_matter, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                f.write("---\n\n")
                # 兼容旧版主题：也将表格写入正文
                f.write(table)
                
            messagebox.showinfo("成功", "科研项目已保存")
            if self.on_save_callback:
                self.on_save_callback()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败：{e}")

    def _cancel(self):
        """取消编辑，恢复原状"""
        self._load_data()
        messagebox.showinfo("已取消", "已放弃修改，恢复为原数据。")


class SettingsFrame(ctk.CTkFrame):
    """全局配置界面，用于修改本地仓库路径和远程 Git URL"""
    def __init__(self, master, config, on_save_callback=None, **kwargs):
        super().__init__(master, **kwargs)
        self.config = config
        self.on_save_callback = on_save_callback
        self._create_widgets()
        self._load_settings()

    def _create_widgets(self):
        # 标题
        ctk.CTkLabel(self, text="全局配置", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=3, padx=20, pady=20
        )
        
        # 本地仓库路径
        ctk.CTkLabel(self, text="本地仓库路径：", anchor="w").grid(row=1, column=0, padx=10, pady=10, sticky="w")
        self.repo_path_entry = ctk.CTkEntry(self, width=400)
        self.repo_path_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        self.browse_btn = ctk.CTkButton(self, text="浏览...", width=80, command=self._browse_folder)
        self.browse_btn.grid(row=1, column=2, padx=10, pady=10)
        
        # 远程 Git URL
        ctk.CTkLabel(self, text="远程 Git URL：", anchor="w").grid(row=2, column=0, padx=10, pady=10, sticky="w")
        self.remote_url_entry = ctk.CTkEntry(self, width=400)
        self.remote_url_entry.grid(row=2, column=1, columnspan=2, padx=10, pady=10, sticky="ew")
        
        # 按钮行
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=3, column=0, columnspan=3, pady=20)
        self.save_btn = ctk.CTkButton(button_frame, text="保存", command=self._save, width=100)
        self.save_btn.pack(side="left", padx=10)
        self.cancel_btn = ctk.CTkButton(button_frame, text="取消", command=self._cancel, width=100)
        self.cancel_btn.pack(side="left", padx=10)
        
        self.grid_columnconfigure(1, weight=1)

    def _browse_folder(self):
        """打开文件夹选择对话框"""
        folder = filedialog.askdirectory(title="选择本地仓库目录")
        if folder:
            self.repo_path_entry.delete(0, 'end')
            self.repo_path_entry.insert(0, folder)

    def _load_settings(self):
        """加载当前配置到输入框"""
        self.repo_path_entry.delete(0, 'end')
        self.repo_path_entry.insert(0, str(self.config.repo_path))
        self.remote_url_entry.delete(0, 'end')
        self.remote_url_entry.insert(0, self.config.remote_git_url)

    def _save(self):
        """保存配置"""
        new_repo_path = self.repo_path_entry.get().strip()
        new_remote_url = self.remote_url_entry.get().strip()
        
        if not new_repo_path:
            messagebox.showwarning("警告", "本地仓库路径不能为空")
            return
            
        # 【安全修正】：转换为 Path 对象，防止其他模块拼接路径时报错
        self.config.repo_path = Path(new_repo_path)
        self.config.remote_git_url = new_remote_url
        
        if self.config.save():
            messagebox.showinfo("成功", "配置已保存。")
            if self.on_save_callback:
                self.on_save_callback()
        else:
            messagebox.showerror("错误", "保存配置失败，请检查日志。")

    def _cancel(self):
        """取消编辑，返回上一级"""
        if self.on_save_callback:
            self.on_save_callback()