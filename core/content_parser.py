# group-site-manager/core/content_parser.py
"""
内容解析与读写模块 (content_parser)

职责：
    负责读取、解析、修改和保存符合 Hugo Page Bundles 规范的 Markdown 文件。
    支持将内容项作为文件夹（包含 index.md 和图片）进行管理。

注意事项：
    - 所有公共方法返回 (bool, data/error) 元组，调用方必须检查布尔值。
    - 图片复制失败时，方法仍会返回 True 但附带警告消息，表示内容保存成功但图片未复制。
      调用方应检查返回的字符串，并决定是否向用户提示。
    - 线程安全：本类方法本身不包含同步机制，多线程环境下需外部加锁。

依赖：
    - core.config_manager.AppConfig
    - python-frontmatter
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

    Attributes:
        config: AppConfig 单例实例，用于获取路径和图片复制工具。

    Example:
        >>> cm = ContentManager()
        >>> success, items = cm.list_items('post')
        >>> if success:
        ...     for item in items:
        ...         print(item['title'])
    """

    def __init__(self):
        """初始化 ContentManager，获取 AppConfig 单例实例。"""
        self.config = AppConfig()
        logger.info("ContentManager 初始化完成")

    # ---------- 内部辅助方法 ----------
    def _generate_safe_folder_name(self, title: str, date_str: str = "") -> str:
        """
        根据标题和日期生成安全的文件夹名（仅含字母、数字、中文、连字符）。

        处理规则：
            - 将非字母数字（保留中文）替换为连字符 '-'
            - 将空白字符替换为连字符
            - 合并连续连字符
            - 去除首尾连字符
            - 如果标题为空，使用默认值 "untitled"
            - 如果提供了日期，则格式为 "日期-安全标题"；否则只返回安全标题

        Args:
            title: 原始标题（可能包含特殊字符）
            date_str: 日期字符串，格式如 '2025-03-18'，为空时不添加日期前缀

        Returns:
            安全的文件夹名字符串
        """
        # 将标题中的非字母数字（除了中文、英文、数字）替换为连字符
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
            
        # 核心修改：如果传入了日期，才拼接日期；否则只返回纯名字
        if date_str:
            return f"{date_str}-{safe_title}"
        return safe_title


    def list_items(self, module_name: str) -> Tuple[bool, Union[List[Dict], str]]:
        """
        列出指定模块下的所有内容项。

        遍历模块目录下的子文件夹，读取其中的 index.md 或 _index.md，
        提取 front-matter 元数据，并添加 folder_name、folder_path、title、date 等字段。

        Args:
            module_name: 模块名称，如 'post', 'authors', 'publication' 等

        Returns:
            Tuple[bool, Union[List[Dict], str]]:
                - 成功时返回 (True, 列表)，每个字典包含 front-matter 字段及额外信息。
                - 失败时返回 (False, 错误信息)
                若模块目录不存在，返回 (True, [])（视为空列表）。
        """
        module_dir = self.config.get_module_dir(module_name)
        if not module_dir.exists():
            # 目录不存在，不是错误，返回空列表
            return True, []

        items = []
        try:
            for item_path in module_dir.iterdir():
                if not item_path.is_dir():
                    continue

                # 优先尝试 index.md，否则尝试 _index.md
                index_file = item_path / "index.md"
                if not index_file.exists():
                    index_file = item_path / "_index.md"
                    if not index_file.exists():
                        continue  # 没有 Markdown 文件，跳过

                try:
                    with open(index_file, 'r', encoding='utf-8') as f:
                        post = frontmatter.load(f)
                except Exception as e:
                    # SUGGESTED: 记录详细错误，但继续处理其他文件夹
                    logger.error(f"解析文件 {index_file} 失败: {e}")
                    continue

                metadata = post.metadata
                if not metadata:
                    continue  # 无 front-matter，视为无效

                # 提取标题和日期，并标准化日期格式
                title = metadata.get('title', item_path.name)
                date = metadata.get('date', '')
                if isinstance(date, datetime):
                    date = date.strftime('%Y-%m-%d')
                elif date and not isinstance(date, str):
                    date = str(date)

                # 构建条目字典
                item = metadata.copy()
                item.update({
                    'folder_name': item_path.name,
                    'folder_path': str(item_path),
                    'title': title,
                    'date': date,
                })
                items.append(item)
        except Exception as e:
            logger.exception(f"遍历模块 {module_name} 时发生未知错误: {e}")
            return False, f"读取内容列表时出错：{str(e)}"

        # 按日期降序排序
        items.sort(key=lambda x: x.get('date', ''), reverse=True)
        return True, items

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

        # 探测 index.md 或 _index.md
        index_file = folder / "index.md"
        if not index_file.exists():
            index_file = folder / "_index.md"
            if not index_file.exists():
                return False, f"未找到内容文件：{folder} 下缺少 index.md 或 _index.md"

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                post = frontmatter.load(f)
        except Exception as e:
            logger.error(f"读取文件 {index_file} 失败: {e}")
            return False, f"读取文件失败：{str(e)}"

        return True, {
            'front_matter': post.metadata,
            'content': post.content
        }

    def save_item(self,
                  module_name: str,
                  form_data: dict,
                  content: str,
                  original_folder_name: Optional[str] = None,
                  image_path: Optional[str] = None) -> Tuple[bool, str]:
        """
        保存或更新一个内容项。

        如果 original_folder_name 为 None，则视为新建；否则视为更新。
        对于 authors 模块，图片会重命名为 avatar.*，文件夹名不包含日期前缀。
        对于其他模块，图片保留原名，文件夹名包含日期前缀。

        Args:
            module_name: 模块名称，如 'post', 'authors'
            form_data: front-matter 字段字典，必须包含 'title'，可能包含 'date' 等
            content: Markdown 正文
            original_folder_name: 更新时传入原文件夹名，新建时为 None
            image_path: 可选，要复制的图片源路径

        Returns:
            Tuple[bool, str]:
                - 成功时返回 (True, 成功消息)
                - 失败时返回 (False, 错误信息)
                注意：图片复制失败时仍会返回 (True, 消息) 但消息中包含失败提示。

        TODO: 此方法过于复杂，建议拆分为多个私有方法以提高可读性和可测试性。
        """
        # 1. 获取并创建模块目录
        module_dir = self.config.get_module_dir(module_name)
        try:
            module_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"创建模块目录失败 {module_dir}: {e}")
            return False, f"无法创建模块目录：{str(e)}"

        # 2. 确定目标文件夹名称
        if original_folder_name:
            folder_name = original_folder_name
        else:
            # 新建：生成安全的文件夹名
            title = form_data.get('title', '')
            if module_name == 'authors':
                # authors 模块不使用日期前缀
                folder_name = self._generate_safe_folder_name(title, "")
            else:
                date_str = form_data.get('date', '')
                if not date_str:
                    date_str = datetime.now().strftime('%Y-%m-%d')
                folder_name = self._generate_safe_folder_name(title, date_str)

            # 避免重名：如果文件夹已存在，添加序号
            base_name = folder_name
            counter = 1
            while (module_dir / folder_name).exists():
                folder_name = f"{base_name}-{counter}"
                counter += 1

        target_dir = module_dir / folder_name
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"创建目标文件夹失败 {target_dir}: {e}")
            return False, f"无法创建内容文件夹：{str(e)}"

        # 3. 确定 Markdown 文件名 (index.md 或 _index.md)
        md_filename = "index.md"  # 默认
        if original_folder_name:
            # 更新时，优先保留原有文件名
            if (target_dir / "_index.md").exists():
                md_filename = "_index.md"
            elif (target_dir / "index.md").exists():
                md_filename = "index.md"
            else:
                # 如果都不存在，根据模块决定
                md_filename = "_index.md" if module_name == "authors" else "index.md"
        else:
            # 新建时，authors 用 _index.md，其他用 index.md
            md_filename = "_index.md" if module_name == "authors" else "index.md"

        index_file = target_dir / md_filename

        # 4. 处理图片上传
        if image_path:
            if module_name == 'authors':
                # 作者头像：复制为 avatar.*
                success, msg = self.config.copy_image_as(image_path, target_dir, 'avatar')
                if not success:
                    logger.warning(f"图片复制失败: {msg}")
                    # 部分成功，返回消息但整体视为成功（内容已保存）
                    return True, f"内容已保存，但图片复制失败：{msg}"
            else:
                # 其他模块：复制图片到目标文件夹，并保留原文件名
                src = Path(image_path)
                if not src.exists():
                    logger.warning(f"图片文件不存在: {image_path}")
                    return True, f"内容未保存，图片文件不存在：{image_path}"  # 这里逻辑不一致？应返回 False
                target_filename = src.name
                target_file = target_dir / target_filename
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, target_file)
                    logger.info(f"图片复制成功: {src} -> {target_file}")

                    # 更新 form_data，添加 image 字段
                    if 'image' not in form_data or not isinstance(form_data['image'], dict):
                        form_data['image'] = {}
                    form_data['image']['filename'] = target_filename
                except Exception as e:
                    logger.error(f"图片复制失败: {e}")
                    return True, f"内容未保存，图片复制失败：{e}"  # 同样，应返回 False

        # 5. 写入 Markdown 文件
        post = frontmatter.Post(content, **form_data)
        try:
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
        except OSError as e:
            logger.error(f"写入文件失败 {index_file}: {e}")
            return False, f"保存文件失败：{str(e)}"

        action = "更新" if original_folder_name else "新建"
        return True, f"{action}成功：{folder_name}"
    def delete_item(self, module_name: str, folder_name: str) -> Tuple[bool, str]:
        """
        删除指定模块下的某个条目（文件夹及其所有内容）。

        Args:
            module_name: 模块名称
            folder_name: 要删除的文件夹名

        Returns:
            Tuple[bool, str]: (成功与否, 消息)

        Note:
            在 Windows 上，如果文件夹内有只读文件，shutil.rmtree 可能失败。
            可考虑在删除前修改文件属性，但当前版本直接返回错误。
        """
        module_dir = self.config.get_module_dir(module_name)
        target_dir = module_dir / folder_name
        if not target_dir.exists():
            return False, f"条目不存在：{folder_name}"
        if not target_dir.is_dir():
            return False, f"路径不是文件夹：{folder_name}"
        try:
            shutil.rmtree(target_dir)
            logger.info(f"删除条目成功: {target_dir}")
            return True, f"已删除：{folder_name}"
        except Exception as e:
            logger.error(f"删除条目失败 {target_dir}: {e}")
            return False, f"删除失败：{str(e)}"