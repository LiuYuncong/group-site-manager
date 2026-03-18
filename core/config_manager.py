# group-site-manager/core/config_manager.py
"""
配置管理模块 (config_manager)

职责：
    1. 使用单例模式维护全局配置（repo_path, remote_git_url），从用户目录的 .group-site-manager/config.json 加载/保存。
    2. 提供基于 pathlib 的路径辅助方法，用于定位 Hugo 站点的各个内容目录。
    3. 提供安全的图片复制工具，用于将用户选择的图片复制到指定目录并重命名为 featured.* 或 avatar.*。

技术栈：
    - pathlib：跨平台路径操作
    - json：配置文件读写
    - logging：记录错误和警告（不涉及 UI）
    - 类型注解与文档字符串确保可维护性

注意事项：
    - 配置加载失败时会回退到默认配置，并记录错误日志。
    - 图片复制操作会覆盖目标文件，请确保调用前已确认。

依赖：无（仅使用 Python 标准库）
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Optional, Tuple, Union, List

# 配置日志记录（core 层只记录到文件或控制台，不弹窗）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AppConfig:
    """
    应用程序配置类（单例模式）

    管理配置文件的加载、保存和访问。配置存储在用户主目录下的 .group-site-manager/config.json 中。
    默认配置：
        - repo_path: 用户主目录 / group-site-repo
        - remote_git_url: "" (空字符串)

    线程安全：单例创建未加锁，多线程环境下需外部同步。

    Attributes:
        _instance: 类级别的单例实例。
        _config_dir: 配置目录 Path 对象。
        _config_file: 配置文件 Path 对象。
        _config: 配置数据字典。
    """

    _instance = None
    _config_dir: Path
    _config_file: Path
    _config: dict

    def __new__(cls, *args, **kwargs):
        """实现单例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, auto_load: bool = True):
        """
        初始化配置对象。

        Args:
            auto_load: 是否自动从文件加载配置。若为 False，则使用默认配置（通常用于测试）。
        """
        # SUGGESTED: 防止重复初始化
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self._config_dir = Path.home() / '.group-site-manager'
        self._config_file = self._config_dir / 'config.json'
        self._config = {}

        if auto_load:
            self.load_or_create()

    def load_or_create(self) -> None:
        """
        加载配置文件，若文件不存在则创建默认配置文件。
        如果目录不存在，也会一并创建。

        Raises:
            # 该方法内部捕获所有异常，不会向外抛出，仅记录日志。
            # 调用者可通过检查日志或后续配置值判断是否成功。
        """
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            if self._config_file.exists():
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                logger.info(f"配置文件加载成功: {self._config_file}")
            else:
                self._create_default_config()
                self.save()
                logger.info(f"已创建默认配置文件: {self._config_file}")
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"配置文件操作失败: {e}，将使用默认配置")
            self._create_default_config()  # 回退到默认配置

    def _create_default_config(self) -> None:
        """生成默认配置字典"""
        self._config = {
            "repo_path": str(Path.home() / "group-site-repo"),
            "remote_git_url": ""
        }

    def save(self) -> bool:
        """
        将当前配置保存到文件。

        Returns:
            bool: 保存成功返回 True，否则返回 False。
        """
        try:
            # 再次确保目录存在（可能在运行时被删除）
            self._config_dir.mkdir(parents=True, exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存到 {self._config_file}")
            return True
        except OSError as e:
            logger.error(f"保存配置文件失败: {e}")
            return False

    @property
    def repo_path(self) -> Path:
        """返回仓库路径的 Path 对象"""
        path_str = self._config.get("repo_path", "")
        return Path(path_str) if path_str else Path.home() / "group-site-repo"

    @repo_path.setter
    def repo_path(self, value: Union[str, Path]) -> None:
        """设置仓库路径（自动转换为字符串存储）"""
        # SUGGESTED: 考虑使用 try-except 捕获 resolve() 可能引发的异常
        # try:
        #     resolved = str(Path(value).resolve())
        # except OSError as e:
        #     logger.error(f"路径解析失败: {e}，将使用原始路径")
        #     resolved = str(Path(value).absolute())
        self._config["repo_path"] = str(Path(value).resolve())

    @property
    def remote_git_url(self) -> str:
        """返回远程 Git 仓库 URL"""
        return self._config.get("remote_git_url", "")

    @remote_git_url.setter
    def remote_git_url(self, value: str) -> None:
        """设置远程 Git 仓库 URL"""
        self._config["remote_git_url"] = value.strip()

    # ---------- 路径辅助方法 ----------
    def get_content_dir(self) -> Path:
        """返回 content 目录路径 (repo_path/content)"""
        return self.repo_path / "content"

    def get_module_dir(self, module_name: str) -> Path:
        """
        返回指定内容模块的目录路径，例如 'post' 对应 repo_path/content/post。
        注意：module_name 应为直接位于 content 下的子目录名称。

        Args:
            module_name: 模块名称，如 'post', 'authors', 'publication' 等

        Returns:
            Path: 模块目录的 Path 对象
        """
        return self.get_content_dir() / module_name

    def get_assets_dir(self) -> Path:
        """返回静态资源目录路径 (repo_path/assets)"""
        return self.repo_path / "assets"

    def ensure_content_dirs(self, modules: Optional[List[str]] = None) -> None:
        """
        确保所有指定的内容子目录存在。
        如果目录不存在，则创建。

        Args:
            modules: 需要确保存在的模块名称列表，例如 ['post', 'authors', 'publication']。
                     若为 None，则使用基于 Hugo Blox 主题的常用模块默认列表。
        """
        if modules is None:
            # 根据提供的网站结构，常用的内容模块列表
            modules = [
                'post', 'authors', 'publication', 'event', 'resource',
                'people', 'contact', 'tour', 'admin', 'alumni', 'research_area'
            ]
        for module in modules:
            try:
                module_dir = self.get_module_dir(module)
                module_dir.mkdir(parents=True, exist_ok=True)
                logger.debug(f"确保目录存在: {module_dir}")
            except OSError as e:
                logger.error(f"创建目录失败 {module_dir}: {e}")

    # ---------- 图片安全复制工具 ----------
    def copy_image_as(self,
                      src_path: Union[str, Path],
                      target_dir: Union[str, Path],
                      image_type: str = 'featured') -> Tuple[bool, str]:
        """
        安全地将源图片复制到目标目录，并重命名为指定类型对应的文件名（保留原始扩展名）。

        支持的 image_type:
            - 'featured' : 重命名为 featured.原扩展名（例如 featured.png）
            - 'avatar'   : 重命名为 avatar.原扩展名
        如果目标文件已存在，将被覆盖。

        Args:
            src_path: 源图片路径
            target_dir: 目标目录
            image_type: 图片类型，'featured' 或 'avatar'

        Returns:
            Tuple[bool, str]: (是否成功, 成功时为目标文件路径字符串，失败时为错误信息)

        Example:
            >>> config = AppConfig()
            >>> success, result = config.copy_image_as('C:/temp/photo.jpg', 'C:/repo/content/post/hello', 'featured')
            >>> if success:
            ...     print(f"图片已复制到 {result}")
            ... else:
            ...     print(f"错误: {result}")
        """
        # 参数校验
        if image_type not in ('featured', 'avatar'):
            return False, f"不支持的图片类型: {image_type}，仅支持 'featured' 或 'avatar'"

        src = Path(src_path)
        dst_dir = Path(target_dir)

        # 检查源文件是否存在且为文件
        if not src.exists():
            return False, f"源文件不存在: {src}"
        if not src.is_file():
            return False, f"源路径不是文件: {src}"

        suffix = src.suffix.lower()
        if not suffix:
            return False, f"源文件没有扩展名: {src}，无法确定图片格式"

        # 可选：检查是否为常见图片格式（仅警告，不阻止复制）
        allowed_ext = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg'}
        if suffix not in allowed_ext:
            logger.warning(f"源文件扩展名 {src.suffix} 可能不是常见图片格式，仍将尝试复制")

        target_filename = f"{image_type}{suffix}"  # 注意：扩展名已转为小写
        target_path = dst_dir / target_filename

        # 确保目标目录存在
        try:
            dst_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return False, f"无法创建目标目录 {dst_dir}: {e}"

        # 执行复制，保留元数据
        try:
            shutil.copy2(src, target_path)
            logger.info(f"图片复制成功: {src} -> {target_path}")
            return True, str(target_path)
        except (shutil.Error, OSError) as e:
            logger.error(f"图片复制失败: {e}")
            return False, f"复制图片时发生错误: {e}"