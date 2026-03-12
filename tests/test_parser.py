# group-site-manager/tests/test_parser.py
"""
测试 content_parser 模块
使用 pytest 和 tmp_path 模拟文件系统，mock AppConfig.copy_image_as 简化测试
"""

import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
import frontmatter  # 修改：直接导入整个模块

# 将项目根目录添加到 sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.content_parser import ContentManager
from core.config_manager import AppConfig


# ---------- Fixtures ----------
@pytest.fixture(autouse=True)
def reset_appconfig_singleton():
    """每个测试前重置 AppConfig 单例"""
    AppConfig._instance = None
    yield


@pytest.fixture
def config_with_temp_repo(tmp_path):
    """创建一个配置对象，repo_path 指向临时目录"""
    config = AppConfig(auto_load=False)
    config.repo_path = tmp_path / "repo"
    # 确保基础目录存在
    config.repo_path.mkdir(parents=True)
    return config


@pytest.fixture
def content_manager(config_with_temp_repo):
    """返回一个 ContentManager 实例，已绑定临时仓库"""
    # 由于 ContentManager 内部会获取 AppConfig 单例，而上面已设置好，直接使用
    return ContentManager()


@pytest.fixture
def mock_copy_image():
    """模拟 AppConfig.copy_image_as 方法，默认返回成功"""
    with patch.object(AppConfig, 'copy_image_as', return_value=(True, "mocked_path")) as mock:
        yield mock


# ---------- 测试 _generate_safe_folder_name ----------
def test_generate_safe_folder_name(content_manager):
    """测试安全文件夹名生成"""
    title = "我的第一篇文章！Hello, World! @2025"
    date = "2025-03-13"
    result = content_manager._generate_safe_folder_name(title, date)
    # 预期：日期-标题（特殊字符变连字符，合并，去除首尾）
    assert result == "2025-03-13-我的第一篇文章-Hello-World-2025"

    # 标题全是特殊字符
    title = "!!!@@@###"
    result = content_manager._generate_safe_folder_name(title, date)
    assert result == "2025-03-13-untitled"

    # 标题包含中文和空格
    title = "  你好  世界  "
    result = content_manager._generate_safe_folder_name(title, date)
    assert result == "2025-03-13-你好-世界"

    # 标题已有连字符
    title = "测试-文章"
    result = content_manager._generate_safe_folder_name(title, date)
    assert result == "2025-03-13-测试-文章"


# ---------- 准备测试数据 ----------
def create_test_item(base_dir: Path, folder_name: str, metadata: dict, content: str = ""):
    """辅助函数：在 base_dir 下创建一个内容项（文件夹 + index.md）"""
    item_dir = base_dir / folder_name
    item_dir.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(content, **metadata)
    with open(item_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(post))
    return item_dir


# ---------- 测试 list_items ----------
def test_list_items_success(content_manager, tmp_path):
    """list_items 应正确解析并排序"""
    # 设置 repo_path 指向临时目录下的 repo
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    # 创建三个测试项
    create_test_item(module_dir, "2025-03-01-first",
                     {"title": "第一篇文章", "date": "2025-03-01", "author": "张三"},
                     "内容1")
    create_test_item(module_dir, "2025-03-05-second",
                     {"title": "第二篇文章", "date": "2025-03-05", "author": "李四"},
                     "内容2")
    # 一个没有日期的项
    create_test_item(module_dir, "no-date-item",
                     {"title": "无日期文章", "author": "王五"},
                     "内容3")

    success, items = content_manager.list_items("post")
    assert success is True
    assert len(items) == 3

    # 验证排序：按日期降序，无日期的应在最后
    dates = [item.get('date', '') for item in items]
    assert dates == ["2025-03-05", "2025-03-01", ""]

    # 验证字段提取
    first = items[0]
    assert first['title'] == "第二篇文章"
    assert first['author'] == "李四"
    assert first['folder_name'] == "2025-03-05-second"
    assert (Path(first['folder_path']) == module_dir / "2025-03-05-second")


def test_list_items_empty_module(content_manager, tmp_path):
    """模块目录不存在或为空时，应返回空列表"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    # 模块目录未创建
    success, items = content_manager.list_items("post")
    assert success is True
    assert items == []

    # 创建空目录
    content_manager.config.get_module_dir("post").mkdir(parents=True)
    success, items = content_manager.list_items("post")
    assert success is True
    assert items == []


def test_list_items_skip_invalid_files(content_manager, tmp_path, caplog):
    """遇到无法解析的 index.md 应跳过，不中断"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    # 正常项
    create_test_item(module_dir, "valid-item",
                     {"title": "有效", "date": "2025-03-01"},
                     "内容")

    # 无效项：index.md 不是有效的 YAML front-matter（比如没有 front-matter 分隔符）
    invalid_dir = module_dir / "invalid-item"
    invalid_dir.mkdir()
    with open(invalid_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write("This is just plain text, no front matter.")

    # 另一个无效项：文件为空
    empty_dir = module_dir / "empty-item"
    empty_dir.mkdir()
    (empty_dir / "index.md").touch()

    success, items = content_manager.list_items("post")
    assert success is True
    assert len(items) == 1
    assert items[0]['title'] == "有效"

    # 验证日志记录了错误
    # assert "解析文件" in caplog.text


# ---------- 测试 read_item ----------
def test_read_item_success(content_manager, tmp_path):
    """正常读取 index.md 应返回 front-matter 和内容"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    folder_path = create_test_item(module_dir, "test-item",
                                   {"title": "测试", "date": "2025-03-13", "tags": ["a", "b"]},
                                   "这是正文内容。\n第二行。")

    success, result = content_manager.read_item(folder_path)
    assert success is True
    assert result['front_matter']['title'] == "测试"
    assert result['front_matter']['date'] == "2025-03-13"
    assert result['front_matter']['tags'] == ["a", "b"]
    # 去除 .strip()，并删除预期末尾的换行
    assert result['content'] == "这是正文内容。\n第二行。"


def test_read_item_not_found(content_manager):
    """文件不存在应返回错误"""
    success, result = content_manager.read_item("/nonexistent/path")
    assert success is False
    assert "文件不存在" in result


def test_read_item_invalid_yaml(content_manager, tmp_path):
    """YAML 格式错误应捕获并返回错误"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    invalid_dir = module_dir / "invalid"
    invalid_dir.mkdir()
    with open(invalid_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write("---\ninvalid: [unclosed list\n---\ncontent")

    success, result = content_manager.read_item(invalid_dir)
    assert success is False
    assert "读取文件失败" in result


# ---------- 测试 save_item ----------
def test_save_item_new(content_manager, tmp_path, mock_copy_image):
    """新建内容项应创建文件夹和 index.md，并复制图片（如果有）"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    form_data = {
        'title': '新文章！测试',
        'date': '2025-03-13',
        'author': '测试员',
        'draft': True
    }
    content = "这是正文。\n新的一行。"

    # 模拟图片路径
    image_path = tmp_path / "test.png"
    image_path.write_bytes(b"fake image")

    success, msg = content_manager.save_item("post", form_data, content,
                                             original_folder_name=None,
                                             image_path=image_path)

    assert success is True
    assert "新建成功" in msg

    # 验证文件夹被创建，名称应为生成的 safe folder name
    expected_folder_name = "2025-03-13-新文章-测试"
    target_dir = module_dir / expected_folder_name
    assert target_dir.exists()
    index_file = target_dir / "index.md"
    assert index_file.exists()

    # 验证文件内容
    with open(index_file, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
    assert post.metadata['title'] == '新文章！测试'
    assert post.metadata['author'] == '测试员'
    assert post.metadata['draft'] is True
    assert post.content == "这是正文。\n新的一行。"

    # 验证图片复制被调用
    mock_copy_image.assert_called_once_with(image_path, target_dir, 'featured')


def test_save_item_new_avoid_duplicate(content_manager, tmp_path):
    """新建时如果生成的文件夹名已存在，应自动添加序号"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    # 预先创建一个同名文件夹
    (module_dir / "2025-03-13-测试").mkdir()

    form_data = {'title': '测试', 'date': '2025-03-13'}
    content = "正文"

    success, msg = content_manager.save_item("post", form_data, content)
    assert success is True

    # 新文件夹应为 2025-03-13-测试-1
    target_dir = module_dir / "2025-03-13-测试-1"
    assert target_dir.exists()
    assert (target_dir / "index.md").exists()


def test_save_item_update(content_manager, tmp_path, mock_copy_image):
    """更新现有内容应覆盖 index.md，并可选更新图片"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    # 先创建一个已有项
    original_folder = "2025-03-13-原文章"
    original_dir = module_dir / original_folder
    original_dir.mkdir()
    original_post = frontmatter.Post("原内容", title="原文章", date="2025-03-13", status="published")
    with open(original_dir / "index.md", 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(original_post))

    # 更新数据
    form_data = {'title': '新标题', 'date': '2025-03-14', 'status': 'draft'}
    new_content = "新内容"

    # 模拟图片路径
    image_path = tmp_path / "new.png"
    image_path.write_bytes(b"new image")

    success, msg = content_manager.save_item("post", form_data, new_content,
                                             original_folder_name=original_folder,
                                             image_path=image_path)

    assert success is True
    assert "更新成功" in msg

    # 验证文件被更新
    index_file = original_dir / "index.md"
    with open(index_file, 'r', encoding='utf-8') as f:
        post = frontmatter.load(f)
    assert post.metadata['title'] == '新标题'
    assert post.metadata['date'] == '2025-03-14'
    assert post.metadata['status'] == 'draft'
    assert post.content == "新内容"

    # 验证图片复制被调用
    mock_copy_image.assert_called_once_with(image_path, original_dir, 'featured')


def test_save_item_update_no_image(content_manager, tmp_path):
    """更新时不提供图片，不应调用复制"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    original_folder = "existing-item"
    original_dir = module_dir / original_folder
    original_dir.mkdir()
    (original_dir / "index.md").write_text("---\ntitle: 旧\n---\n旧内容", encoding='utf-8')

    with patch.object(AppConfig, 'copy_image_as') as mock_copy:
        form_data = {'title': '新'}
        success, msg = content_manager.save_item("post", form_data, "新内容",
                                                 original_folder_name=original_folder,
                                                 image_path=None)
        assert success is True
        mock_copy.assert_not_called()


def test_save_item_new_with_avatar_for_authors(content_manager, tmp_path, mock_copy_image):
    """authors 模块应使用 avatar 图片类型"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("authors")
    module_dir.mkdir(parents=True)

    form_data = {'title': '张三', 'date': '2025-03-13'}
    content = "简介"
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"photo")

    success, msg = content_manager.save_item("authors", form_data, content,
                                             original_folder_name=None,
                                             image_path=image_path)

    assert success is True
    # 验证图片复制时 type='avatar'
    expected_folder_name = "2025-03-13-张三"
    target_dir = module_dir / expected_folder_name
    mock_copy_image.assert_called_once_with(image_path, target_dir, 'avatar')


def test_save_item_image_copy_failure(content_manager, tmp_path, caplog):
    """图片复制失败应返回部分成功消息"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    form_data = {'title': '文章', 'date': '2025-03-13'}
    content = "正文"
    image_path = tmp_path / "test.png"
    image_path.write_bytes(b"data")

    # mock copy_image_as 返回失败
    with patch.object(AppConfig, 'copy_image_as', return_value=(False, "磁盘空间不足")):
        success, msg = content_manager.save_item("post", form_data, content,
                                                 original_folder_name=None,
                                                 image_path=image_path)
        # 内容应该保存成功，但图片失败
        assert success is True
        assert "内容已保存，但图片复制失败" in msg
        assert "磁盘空间不足" in msg

    # 验证 index.md 存在
    target_dir = module_dir / "2025-03-13-文章"
    assert (target_dir / "index.md").exists()


def test_save_item_permission_error(content_manager, tmp_path):
    """目录创建或文件写入失败时应返回错误"""
    repo_root = tmp_path / "repo"
    content_manager.config.repo_path = repo_root
    module_dir = content_manager.config.get_module_dir("post")
    module_dir.mkdir(parents=True)

    # 模拟 mkdir 抛出 OSError
    with patch('pathlib.Path.mkdir', side_effect=OSError("权限不足")):
        form_data = {'title': '测试'}
        success, msg = content_manager.save_item("post", form_data, "内容")
        assert success is False
        assert "无法创建模块目录" in msg