# group-site-manager/tests/test_config.py
"""
测试 config_manager 模块
使用 pytest 和 tmp_path 模拟文件系统
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

# 导入待测试模块
from core.config_manager import AppConfig


@pytest.fixture
def mock_home(tmp_path):
    """模拟用户主目录，返回一个临时 Path"""
    home = tmp_path / "home"
    home.mkdir()
    with patch('pathlib.Path.home', return_value=home):
        yield home


@pytest.fixture
def config(mock_home):
    """返回一个全新的 AppConfig 实例（auto_load=False）避免自动加载影响测试"""
    # 清除单例，确保每个测试获得新实例
    AppConfig._instance = None
    cfg = AppConfig(auto_load=False)
    # 手动设置配置目录为 mock_home 下的 .group-site-manager
    cfg._config_dir = mock_home / '.group-site-manager'
    cfg._config_file = cfg._config_dir / 'config.json'
    return cfg


@pytest.fixture
def populated_config(config):
    """创建一个已有配置的 AppConfig 实例（手动设置配置内容）"""
    config._config = {
        "repo_path": str(config.repo_path),  # 使用默认值
        "remote_git_url": "https://example.com/repo.git"
    }
    return config


# ---------- 测试配置加载与保存 ----------
def test_load_or_create_creates_default_when_no_file(config, mock_home):
    """当配置文件不存在时，load_or_create 应创建默认配置并保存"""
    assert not config._config_file.exists()
    config.load_or_create()
    assert config._config_file.exists()
    assert config._config["repo_path"] == str(mock_home / "group-site-repo")
    assert config._config["remote_git_url"] == ""


def test_load_or_create_loads_existing_file(config, mock_home):
    """当配置文件存在时，load_or_create 应正确加载"""
    # 先创建配置文件
    config._config_dir.mkdir(parents=True)
    test_config = {
        "repo_path": "/custom/repo",
        "remote_git_url": "https://git.example.com/test.git"
    }
    with open(config._config_file, 'w') as f:
        json.dump(test_config, f)
    
    config.load_or_create()
    assert config._config["repo_path"] == "/custom/repo"
    assert config._config["remote_git_url"] == "https://git.example.com/test.git"


def test_save_writes_config_to_file(config, mock_home):
    """save 方法应将配置写入文件"""
    config._config = {"repo_path": "/a/b", "remote_git_url": "url"}
    result = config.save()
    assert result is True
    assert config._config_file.exists()
    with open(config._config_file) as f:
        data = json.load(f)
    assert data == config._config


def test_save_returns_false_on_error(config):
    """当目录无法创建时，save 应返回 False"""
    # 模拟无法创建目录的情况（如权限错误）
    config._config_dir = Path("/nonexistent")  # 无效路径
    with patch.object(Path, 'mkdir', side_effect=OSError):
        result = config.save()
        assert result is False


# ---------- 测试属性 ----------
def test_repo_path_property(config, mock_home):
    """测试 repo_path 的 getter/setter"""
    # 默认值
    assert config.repo_path == mock_home / "group-site-repo"
    
    # setter
    config.repo_path = "/new/path"
    assert config.repo_path == Path("/new/path").resolve()
    assert config._config["repo_path"] == str(Path("/new/path").resolve())


def test_remote_git_url_property(config):
    """测试 remote_git_url 的 getter/setter"""
    assert config.remote_git_url == ""
    config.remote_git_url = "  https://example.com  "
    assert config.remote_git_url == "https://example.com"


# ---------- 测试路径辅助方法 ----------
def test_get_content_dir(config):
    """get_content_dir 应返回 repo_path/content"""
    config.repo_path = "/my/repo"
    assert config.get_content_dir() == Path("/my/repo/content")


def test_get_module_dir(config):
    """get_module_dir 应返回 content/module_name"""
    config.repo_path = "/my/repo"
    assert config.get_module_dir("post") == Path("/my/repo/content/post")
    assert config.get_module_dir("authors") == Path("/my/repo/content/authors")


def test_get_assets_dir(config):
    """get_assets_dir 应返回 repo_path/assets"""
    config.repo_path = "/my/repo"
    assert config.get_assets_dir() == Path("/my/repo/assets")


def test_ensure_content_dirs_creates_directories(config, tmp_path):
    """ensure_content_dirs 应创建指定的目录（或默认列表）"""
    # 设置 repo_path 为临时目录下的 repo
    repo_base = tmp_path / "repo"
    config.repo_path = repo_base
    
    # 调用 ensure_content_dirs（默认列表）
    config.ensure_content_dirs()
    
    # 验证默认模块目录存在
    default_modules = [
        'post', 'authors', 'publication', 'event', 'resource',
        'people', 'contact', 'tour', 'admin', 'alumni', 'research_area'
    ]
    for module in default_modules:
        assert (repo_base / "content" / module).is_dir()
    
    # 测试自定义模块列表
    custom_modules = ['test1', 'test2']
    config.ensure_content_dirs(custom_modules)
    for module in custom_modules:
        assert (repo_base / "content" / module).is_dir()


# ---------- 测试图片复制 ----------
def test_copy_image_as_success(config, tmp_path):
    """成功复制并重命名图片（保留扩展名）"""
    src = tmp_path / "test.png"
    src.write_bytes(b"fake image data")  # 创建虚拟文件
    
    target_dir = tmp_path / "target"
    
    success, msg = config.copy_image_as(src, target_dir, "featured")
    assert success is True
    expected = target_dir / "featured.png"
    assert expected.exists()
    assert msg == str(expected)
    
    # 测试 avatar 类型
    success, msg = config.copy_image_as(src, target_dir, "avatar")
    assert success is True
    assert (target_dir / "avatar.png").exists()


def test_copy_image_as_overwrites_existing(config, tmp_path):
    """如果目标文件已存在，应覆盖"""
    src = tmp_path / "test.png"
    src.write_bytes(b"original")
    
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    existing = target_dir / "featured.png"
    existing.write_bytes(b"old")
    
    success, msg = config.copy_image_as(src, target_dir, "featured")
    assert success is True
    assert existing.read_bytes() == b"original"  # 被覆盖


def test_copy_image_as_invalid_type(config, tmp_path):
    """传入不支持的 image_type 应返回错误"""
    src = tmp_path / "test.png"
    src.write_bytes(b"data")
    success, msg = config.copy_image_as(src, tmp_path, "invalid")
    assert success is False
    assert "不支持的图片类型" in msg


def test_copy_image_as_src_not_exist(config, tmp_path):
    """源文件不存在应返回错误"""
    src = tmp_path / "nonexistent.jpg"
    success, msg = config.copy_image_as(src, tmp_path, "featured")
    assert success is False
    assert "源文件不存在" in msg


def test_copy_image_as_src_is_directory(config, tmp_path):
    """源路径是目录应返回错误"""
    src_dir = tmp_path / "somedir"
    src_dir.mkdir()
    success, msg = config.copy_image_as(src_dir, tmp_path, "featured")
    assert success is False
    assert "源路径不是文件" in msg


def test_copy_image_as_no_extension(config, tmp_path):
    """源文件没有扩展名应返回错误"""
    src = tmp_path / "test"  # 无扩展名
    src.write_bytes(b"data")
    success, msg = config.copy_image_as(src, tmp_path, "featured")
    assert success is False
    assert "没有扩展名" in msg


def test_copy_image_as_uncommon_extension(config, tmp_path):
    """扩展名不在允许列表中，仍应复制但发出警告（我们只检查成功）"""
    src = tmp_path / "test.webp"  # .webp 可能不在 allowed_ext 中
    src.write_bytes(b"data")
    target_dir = tmp_path / "target"
    success, msg = config.copy_image_as(src, target_dir, "featured")
    assert success is True
    expected = target_dir / "featured.webp"
    assert expected.exists()


def test_copy_image_as_creates_target_dir(config, tmp_path):
    """如果目标目录不存在，应自动创建"""
    src = tmp_path / "test.jpg"
    src.write_bytes(b"data")
    target_dir = tmp_path / "deep/nested/dir"
    assert not target_dir.exists()
    
    success, msg = config.copy_image_as(src, target_dir, "featured")
    assert success is True
    assert target_dir.is_dir()
    assert (target_dir / "featured.jpg").exists()


# ---------- 测试单例 ----------
def test_singleton_pattern():
    """AppConfig 应为单例，多次实例化返回同一对象"""
    AppConfig._instance = None  # 重置
    c1 = AppConfig(auto_load=False)
    c2 = AppConfig(auto_load=False)
    assert c1 is c2


# ---------- 测试与其他模块的隔离性（可选）----------
def test_no_global_instance_created_on_import():
    """确保模块导入时不会自动创建全局实例（因为已删除 config = AppConfig()）"""
    import core.config_manager
    assert not hasattr(core.config_manager, 'config')
