# group-site-manager/tests/test_git.py
"""
测试 git_engine 模块
使用 pytest 和 mock 模拟 GitPython 的行为，避免连接真实远程仓库
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# 将项目根目录添加到 sys.path，确保可以导入 core 模块
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.git_engine import GitManager
from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError


# ---------- Fixtures ----------
@pytest.fixture
def mock_repo():
    """创建一个模拟的 Repo 对象"""
    repo = MagicMock()
    # 模拟 remote 方法
    mock_remote = MagicMock()
    repo.remote.return_value = mock_remote
    # 模拟 bare 属性
    repo.bare = False
    # 模拟 active_branch（返回一个模拟的分支对象，有 name 属性）
    mock_branch = MagicMock()
    mock_branch.name = "main"
    repo.active_branch = mock_branch
    return repo


@pytest.fixture
def git_manager(mock_repo, tmp_path):
    """返回一个 GitManager 实例，其 self.repo 被替换为 mock_repo"""
    with patch('core.git_engine.Repo', return_value=mock_repo) as mock_repo_class:
        # 使用临时路径作为 repo_path
        mgr = GitManager(tmp_path / "dummy_repo")
        # 确保 Repo 被调用
        mock_repo_class.assert_called_once()
        # 替换为我们的 mock_repo（实际上 Repo 返回的就是 mock_repo）
        mgr.repo = mock_repo
        yield mgr


# ---------- 测试初始化 ----------
def test_init_success(tmp_path):
    """正常初始化应成功创建 Repo 对象"""
    repo_path = tmp_path / "valid_repo"
    repo_path.mkdir()
    with patch('core.git_engine.Repo') as mock_repo_class:
        mock_repo_instance = MagicMock()
        mock_repo_instance.bare = False
        mock_repo_class.return_value = mock_repo_instance

        mgr = GitManager(repo_path)
        mock_repo_class.assert_called_once_with(repo_path)
        assert mgr.is_valid() is True


def test_init_invalid_repo(tmp_path):
    """当路径不是 Git 仓库时，应捕获异常，self.repo 为 None"""
    repo_path = tmp_path / "not_repo"
    repo_path.mkdir()
    with patch('core.git_engine.Repo', side_effect=InvalidGitRepositoryError):
        mgr = GitManager(repo_path)
        assert mgr.is_valid() is False


def test_init_path_not_exist(tmp_path):
    """当路径不存在时，应捕获 NoSuchPathError，self.repo 为 None"""
    repo_path = tmp_path / "nonexistent"
    with patch('core.git_engine.Repo', side_effect=NoSuchPathError):
        mgr = GitManager(repo_path)
        assert mgr.is_valid() is False


def test_init_bare_repo(tmp_path):
    """如果仓库是 bare 仓库，应视为无效"""
    repo_path = tmp_path / "bare_repo"
    repo_path.mkdir()
    with patch('core.git_engine.Repo') as mock_repo_class:
        mock_repo_instance = MagicMock()
        mock_repo_instance.bare = True  # bare 仓库
        mock_repo_class.return_value = mock_repo_instance

        mgr = GitManager(repo_path)
        assert mgr.is_valid() is False


# ---------- 测试 check_uncommitted_changes ----------
def test_check_uncommitted_changes_true(git_manager, mock_repo):
    """有未提交更改时应返回 True"""
    mock_repo.is_dirty.return_value = True
    assert git_manager.check_uncommitted_changes() is True
    mock_repo.is_dirty.assert_called_once_with(untracked_files=True)


def test_check_uncommitted_changes_false(git_manager, mock_repo):
    """无未提交更改时应返回 False"""
    mock_repo.is_dirty.return_value = False
    assert git_manager.check_uncommitted_changes() is False


def test_check_uncommitted_changes_invalid_repo(git_manager):
    """仓库无效时，应返回 False 且不引发异常"""
    git_manager.repo = None
    assert git_manager.check_uncommitted_changes() is False


# ---------- 测试 pull_latest ----------
def test_pull_latest_success(git_manager, mock_repo):
    """pull 成功应返回 (True, 成功消息)"""
    mock_remote = mock_repo.remote.return_value
    mock_remote.pull.return_value = ["some info"]
    success, msg = git_manager.pull_latest()
    assert success is True
    assert "成功从远程仓库拉取" in msg
    mock_repo.remote.assert_called_once_with(name='origin')
    mock_remote.pull.assert_called_once()


def test_pull_latest_no_remote(git_manager, mock_repo):
    """没有配置远程仓库时，应返回错误信息"""
    mock_repo.remote.side_effect = ValueError("Remote named 'origin' didn't exist")
    success, msg = git_manager.pull_latest()
    assert success is False
    assert "未配置远程仓库" in msg


def test_pull_latest_network_error(git_manager, mock_repo):
    """网络错误导致 pull 失败时，应返回友好的错误信息"""
    mock_remote = mock_repo.remote.return_value
    # 模拟 GitCommandError，设置 stderr
    error = GitCommandError("pull", b"stderr", "could not resolve host")
    error.stderr = "Could not resolve host: github.com"
    mock_remote.pull.side_effect = error

    success, msg = git_manager.pull_latest()
    assert success is False
    assert "无法连接到远程仓库" in msg


def test_pull_latest_conflict(git_manager, mock_repo):
    """pull 产生冲突时，应返回冲突提示"""
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("pull", b"stderr", "conflict")
    error.stderr = "Automatic merge failed; fix conflicts and then commit the result."
    mock_remote.pull.side_effect = error

    success, msg = git_manager.pull_latest()
    assert success is False
    assert "发生冲突" in msg


def test_pull_latest_auth_error(git_manager, mock_repo):
    """认证失败时，应返回认证失败提示"""
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("pull", b"stderr", "authentication failed")
    error.stderr = "fatal: Authentication failed for 'https://github.com/user/repo.git'"
    mock_remote.pull.side_effect = error

    success, msg = git_manager.pull_latest()
    assert success is False
    assert "认证失败" in msg


def test_pull_latest_invalid_repo(git_manager):
    """仓库无效时，应返回错误"""
    git_manager.repo = None
    success, msg = git_manager.pull_latest()
    assert success is False
    assert "尚未配置有效的 Git 仓库" in msg


# ---------- 测试 commit_and_push ----------
def test_commit_and_push_no_changes(git_manager, mock_repo):
    """没有更改时，应直接返回成功，不执行 add/commit/push"""
    mock_repo.is_dirty.return_value = False
    success, msg = git_manager.commit_and_push()
    assert success is True
    assert "没有需要同步的更改" in msg
    # 确保没有调用 git add / commit / push
    mock_repo.git.add.assert_not_called()
    mock_repo.index.commit.assert_not_called()
    mock_repo.remote.return_value.push.assert_not_called()


def test_commit_and_push_success(git_manager, mock_repo):
    """有更改且远程正常时，应成功执行 add, commit, push（带分支名）"""
    mock_repo.is_dirty.return_value = True
    mock_remote = mock_repo.remote.return_value
    mock_remote.push.return_value = ["ok"]

    success, msg = git_manager.commit_and_push("test commit")
    assert success is True
    assert "成功推送到远程仓库" in msg

    # 验证调用顺序
    mock_repo.git.add.assert_called_once_with(A=True)
    mock_repo.index.commit.assert_called_once_with("test commit")
    # 验证 push 时传入了当前分支名
    mock_remote.push.assert_called_once_with("main")  # 从 fixture 得到分支名为 main


def test_commit_and_push_no_remote(git_manager, mock_repo):
    """没有远程仓库时，应完成本地提交并返回特定消息，不执行 push"""
    mock_repo.is_dirty.return_value = True
    # 模拟 remote 不存在
    mock_repo.remote.side_effect = ValueError("No origin")

    success, msg = git_manager.commit_and_push()
    assert success is True
    assert "已在本地提交" in msg and "未配置远程仓库" in msg
    # add 和 commit 应该被执行
    mock_repo.git.add.assert_called_once_with(A=True)
    mock_repo.index.commit.assert_called_once()
    # push 不应被调用
    mock_repo.remote.assert_called_once_with(name='origin')
    mock_repo.remote.return_value.push.assert_not_called()


def test_commit_and_push_need_pull_first(git_manager, mock_repo):
    """push 失败因为需要先 pull，应返回相应提示"""
    mock_repo.is_dirty.return_value = True
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("push", b"stderr", "failed to push")
    error.stderr = " ! [rejected]        main -> main (fetch first)"
    mock_remote.push.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "远程仓库有更新尚未拉取" in msg
    mock_repo.git.add.assert_called_once()
    mock_repo.index.commit.assert_called_once()
    mock_remote.push.assert_called_once_with("main")


def test_commit_and_push_auth_error(git_manager, mock_repo):
    """push 认证失败"""
    mock_repo.is_dirty.return_value = True
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("push", b"stderr", "authentication failed")
    error.stderr = "fatal: Authentication failed"
    mock_remote.push.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "认证失败" in msg


def test_commit_and_push_network_error(git_manager, mock_repo):
    """push 网络错误"""
    mock_repo.is_dirty.return_value = True
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("push", b"stderr", "could not resolve host")
    error.stderr = "fatal: unable to access 'https://...': Could not resolve host"
    mock_remote.push.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "无法连接到远程仓库" in msg


def test_commit_and_push_no_upstream_branch(git_manager, mock_repo):
    """push 时本地分支没有上游分支，应给出提示"""
    mock_repo.is_dirty.return_value = True
    mock_remote = mock_repo.remote.return_value
    error = GitCommandError("push", b"stderr", "no upstream branch")
    error.stderr = "fatal: The current branch main has no upstream branch."
    mock_remote.push.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "没有设置上游分支" in msg


def test_commit_and_push_invalid_repo(git_manager):
    """仓库无效时，应返回错误"""
    git_manager.repo = None
    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "尚未配置有效的 Git 仓库" in msg


def test_commit_and_push_git_add_failure(git_manager, mock_repo):
    """git add 失败应捕获并返回错误"""
    mock_repo.is_dirty.return_value = True
    # 模拟 git add 抛出 GitCommandError
    error = GitCommandError("add", b"stderr", "some error")
    mock_repo.git.add.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "本地提交失败" in msg
    # commit 和 push 不应被调用
    mock_repo.index.commit.assert_not_called()
    mock_repo.remote.return_value.push.assert_not_called()


def test_commit_and_push_commit_failure(git_manager, mock_repo):
    """git commit 失败应捕获并返回错误"""
    mock_repo.is_dirty.return_value = True
    error = GitCommandError("commit", b"stderr", "nothing to commit")
    mock_repo.index.commit.side_effect = error

    success, msg = git_manager.commit_and_push()
    assert success is False
    assert "本地提交失败" in msg
    mock_repo.git.add.assert_called_once()
    mock_remote = mock_repo.remote.return_value
    mock_remote.push.assert_not_called()