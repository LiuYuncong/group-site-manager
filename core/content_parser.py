# group-site-manager/core/content_parser.py
"""
内容解析与读写模块 (content_parser)

职责：
    负责读取、解析、修改和保存符合 Hugo Page Bundles 规范的 Markdown 文件。
    支持将内容项作为文件夹（包含 index.md 和图片）进行管理。

技术栈：
    - python-frontmatter：解析和生成 Markdown 文件的 front-matter
    - pathlib：跨平台路径操作
    - re：生成安全的文件夹名
    - datetime：处理日期
    - logging：记录错误和警告
    - 依赖 core.config_manager.AppConfig 获取路径和图片复制工具

依赖：
    - core.config_manager
    - python-frontmatter (需在 requirements.txt 中添加)
"""

import re
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Union, Tuple, Optional

import frontmatter  # 修改：直接导入整个模块

from core.config_manager import AppConfig

logger = logging.getLogger(__name__)


class ContentManager:
    """
    内容管理器

    提供对 Hugo Page Bundles 内容的增删改查（仅实现查、改、新建）。
    所有公共方法均返回 (bool, data/error) 元组，上层根据 bool 判断操作是否成功。
    """

    def __init__(self):
        """初始化 ContentManager，获取 AppConfig 单例实例。"""
        self.config = AppConfig()
        logger.info("ContentManager 初始化完成")

    # ---------- 内部辅助方法 ----------
    def _generate_safe_folder_name(self, title: str, date_str: str) -> str:
        """
        根据标题和日期生成安全的文件夹名。

        规则：
            - 日期格式：假设为 YYYY-MM-DD
            - 将标题中的非字母数字（保留中文、字母、数字）替换为连字符 '-'
            - 多个连续连字符合并为一个
            - 去掉首尾连字符
            - 最终格式：{date_str}-{safe_title}

        Args:
            title: 文章标题（可能包含中文、空格、标点）
            date_str: 日期字符串，如 "2025-03-13"

        Returns:
            str: 安全的文件夹名，例如 "2025-03-13-我的第一篇文章"
        """
        # 将标题中的非字母数字（除了中文、英文、数字）替换为连字符
        # 使用正则：匹配任何不是字母、数字、中文的字符
        # 中文范围：\u4e00-\u9fff
        safe_title = re.sub(r'[^\w\s\u4e00-\u9fff]', '-', title, flags=re.UNICODE)
        # 将空格也替换为连字符
        safe_title = re.sub(r'\s+', '-', safe_title)
        # 合并连续的连字符
        safe_title = re.sub(r'-+', '-', safe_title)
        # 去掉开头和结尾的连字符
        safe_title = safe_title.strip('-')
        # 如果标题被清空了，使用默认值
        if not safe_title:
            safe_title = "untitled"
        # 组合日期和标题
        return f"{date_str}-{safe_title}"

    # ---------- 列表方法 ----------
    def list_items(self, module_name: str) -> Tuple[bool, Union[List[Dict], str]]:
        """
        列出指定模块下的所有内容项。

        每个模块目录下应有多个子文件夹，每个子文件夹代表一个内容项，
        内含 index.md 或 _index.md 文件。该方法遍历子文件夹，读取文件，
        提取标题、日期等信息。

        Args:
            module_name: 模块名称，如 'post', 'authors', 'publication' 等

        Returns:
            Tuple[bool, Union[List[Dict], str]]:
                - 成功时返回 (True, 列表)，每个字典包含：
                    folder_name (str): 文件夹名
                    folder_path (str): 完整路径
                    title (str): 标题（若无则用文件夹名）
                    date (str): 日期（若无则用空字符串）
                    以及其他 front-matter 字段
                - 失败时返回 (False, 错误信息)
        """
        module_dir = self.config.get_module_dir(module_name)
        if not module_dir.exists():
            # 模块目录不存在，返回空列表（不是错误）
            return True, []

        items = []
        try:
            for item_path in module_dir.iterdir():
                if not item_path.is_dir():
                    continue

                # === 修改点：双重探测 index.md 或 _index.md ===
                # 首先尝试 index.md
                index_file = item_path / "index.md"
                if not index_file.exists():
                    # 如果不存在，再尝试 _index.md（用于 authors 等分支包）
                    index_file = item_path / "_index.md"
                    if not index_file.exists():
                        # 两种文件都不存在，跳过该文件夹
                        continue

                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        post = frontmatter.load(f)
                    # 如果 front-matter 为空，视为无效内容，跳过
                    if not post.metadata:
                        continue
                except Exception as e:
                    logger.error(f"解析文件 {index_file} 失败: {e}")
                    continue

                metadata = post.metadata
                title = metadata.get('title', item_path.name)
                date = metadata.get('date', '')
                # 将 datetime 对象转换为字符串
                if isinstance(date, datetime):
                    date = date.strftime('%Y-%m-%d')
                elif date and not isinstance(date, str):
                    date = str(date)

                # 创建条目字典：复制所有元数据，并手动添加必要字段
                item = metadata.copy()
                item['folder_name'] = item_path.name
                item['folder_path'] = str(item_path)
                item['title'] = title
                item['date'] = date
                items.append(item)
        except Exception as e:
            logger.exception(f"遍历模块 {module_name} 时发生未知错误: {e}")
            return False, f"读取内容列表时出错：{str(e)}"

        # 按日期降序排序（新日期在前），无日期的排最后
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        return True, items

    # ---------- 读取单个内容 ----------
    def read_item(self, folder_path: Union[str, Path]) -> Tuple[bool, Union[Dict, str]]:
        """
        读取指定文件夹下的 index.md 或 _index.md，返回 front-matter 和正文。

        Args:
            folder_path: 内容项所在的文件夹路径

        Returns:
            Tuple[bool, Union[Dict, str]]:
                - 成功时返回 (True, 字典)，包含：
                    front_matter (dict): front-matter 元数据
                    content (str): 正文文本
                - 失败时返回 (False, 错误信息)
        """
        folder = Path(folder_path)

        # === 修改点：双重探测 index.md 或 _index.md ===
        # 先尝试 index.md
        index_file = folder / "index.md"
        if not index_file.exists():
            # 如果不存在，尝试 _index.md
            index_file = folder / "_index.md"
            if not index_file.exists():
                # 两种文件都不存在，返回错误
                return False, f"未找到内容文件：{folder} 下缺少 index.md 或 _index.md"

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            logger.error(f"读取文件 {index_file} 失败: {e}")
            return False, f"读取文件失败：{str(e)}"

        # 返回 front-matter 和正文
        return True, {
            'front_matter': post.metadata,
            'content': post.content
        }

    # ---------- 保存/更新内容 ----------
    def save_item(self,
                  module_name: str,
                  form_data: dict,
                  content: str,
                  original_folder_name: Optional[str] = None,
                  image_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        新建或更新一个内容项。

        逻辑：
            - 如果 original_folder_name 为空，则为新建：生成安全的文件夹名，在模块目录下创建文件夹。
            - 如果 original_folder_name 有值，则为更新：直接定位到该文件夹。
            - 将 form_data 作为 front-matter，content 作为正文，写入文件夹下的 index.md。
            - 如果提供了 image_path，调用 AppConfig.copy_image_as 复制图片到该文件夹，
              并根据模块名决定图片类型：'authors' 模块使用 'avatar'，其他使用 'featured'。

        Args:
            module_name: 模块名称，如 'post'
            form_data: 包含 front-matter 字段的字典
            content: 正文内容字符串
            original_folder_name: 更新时的原文件夹名；新建时为 None
            image_path: 可选，图片源路径

        Returns:
            Tuple[bool, str]: (成功标志, 提示信息/错误信息)
        """
        # 获取模块目录
        module_dir = self.config.get_module_dir(module_name)
        try:
            module_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"创建模块目录失败 {module_dir}: {e}")
            return False, f"无法创建模块目录：{str(e)}"

        # 确定目标文件夹
        if original_folder_name:
            # 更新：使用原有文件夹名
            folder_name = original_folder_name
        else:
            # 新建：生成安全的文件夹名
            title = form_data.get('title', '')
            date_str = form_data.get('date', '')
            if not date_str:
                # 如果没有日期，使用当前日期
                date_str = datetime.now().strftime('%Y-%m-%d')
            folder_name = self._generate_safe_folder_name(title, date_str)
            # 避免重名：如果文件夹已存在，添加序号
            original_folder_name_candidate = folder_name
            counter = 1
            while (module_dir / folder_name).exists():
                folder_name = f"{original_folder_name_candidate}-{counter}"
                counter += 1

        target_dir = module_dir / folder_name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"创建目标文件夹失败 {target_dir}: {e}")
            return False, f"无法创建内容文件夹：{str(e)}"

        # 创建 Post 对象（使用 frontmatter.Post）
        post = frontmatter.Post(content, **form_data)

         # === 优化点：智能确定文件名 ===
        md_filename = "index.md"  # 默认值

        if original_folder_name:
            # 更新：探测原有文件名
            if (target_dir / "_index.md").exists():
                md_filename = "_index.md"
            elif (target_dir / "index.md").exists():
                md_filename = "index.md"
            else:
                # 理论上不应发生（文件夹存在但没有任何文件），回退到模块默认
                md_filename = "_index.md" if module_name == "authors" else "index.md"
        else:
            # 新建：根据模块分配
            if module_name == "authors":
                md_filename = "_index.md"
            else:
                md_filename = "index.md"

        index_file = target_dir / md_filename
        # ================================

        # 创建 Post 对象
        post = frontmatter.Post(content, **form_data)

        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
        except OSError as e:
            logger.error(f"写入文件失败 {index_file}: {e}")
            return False, f"保存文件失败：{str(e)}"
# === 核心处理：图片上传与字段绑定 ===
        if image_path:
            if module_name == 'authors':
                # 作者头像：强制重命名为 avatar.*（保留原扩展名）
                image_type = 'avatar'
                success, msg = self.config.copy_image_as(image_path, target_dir, image_type)
                if not success:
                    logger.warning(f"图片复制失败: {msg}")
                    return True, f"内容已保存，但图片复制失败：{msg}"
            else:
                # 其他模块：保持原始文件名，复制到目标文件夹
                src = Path(image_path)
                if not src.exists():
                    logger.warning(f"图片文件不存在: {image_path}")
                    return True, f"内容未保存，图片文件不存在：{image_path}"
                
                target_filename = src.name
                target_file = target_dir / target_filename
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target_file)
                    logger.info(f"图片复制成功: {src} -> {target_file}")
                    
                    # 兼容复杂的 image 字典结构（如包含 caption）
                    if 'image' not in form_data or not isinstance(form_data['image'], dict):
                        form_data['image'] = {}
                    form_data['image']['filename'] = target_filename
                    
                except Exception as e:
                    logger.error(f"图片复制失败: {e}")
                    return True, f"内容未保存，图片复制失败：{e}"

        # === 核心修正 2：用包含了 image 字段的 form_data 重新生成 Post ===
        # === 创建 Post 对象并写入文件 ===
        post = frontmatter.Post(content, **form_data)

        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
        except OSError as e:
            logger.error(f"写入文件失败 {index_file}: {e}")
            return False, f"保存文件失败：{str(e)}"

        action = "更新" if original_folder_name else "新建"
        return True, f"{action}成功：{folder_name}"
    
    #删除条目
    def delete_item(self, module_name: str, folder_name: str) -> Tuple[bool, str]:
        """
        删除指定模块下的某个条目（文件夹及其所有内容）。
        """
        module_dir = self.config.get_module_dir(module_name)
        target_dir = module_dir / folder_name
        if not target_dir.exists():
            return False, f"条目不存在：{folder_name}"
        if not target_dir.is_dir():
            return False, f"路径不是文件夹：{folder_name}"
        try:
            import shutil
            shutil.rmtree(target_dir)
            logger.info(f"删除条目成功: {target_dir}")
            return True, f"已删除：{folder_name}"
        except Exception as e:
            logger.error(f"删除条目失败 {target_dir}: {e}")
            return False, f"删除失败：{str(e)}"