# group-site-manager/core/git_engine.py
"""
Git 同步引擎模块 (git_engine)

职责：
    封装所有底层 Git 操作，提供简单、健壮的接口供 UI 层调用。
    所有对外方法均返回 (bool, str) 元组，成功时 bool=True，消息为成功提示；
    失败时 bool=False，消息为友好的中文错误信息，绝不抛出异常。

安全与并发注意：
    1. 本模块包含网络与磁盘 I/O，属于同步阻塞调用。UI 层调用时【必须】放入后台工作线程，严禁在主线程直接调用。
    2. Git 的 stderr 可能包含明文凭证（HTTPS Token 等），本模块的日志系统需确保敏感信息不被落盘。

依赖：
    - GitPython
"""

import logging
from pathlib import Path
from typing import Tuple, Union
from git import Repo, GitCommandError, InvalidGitRepositoryError, NoSuchPathError

logger = logging.getLogger(__name__)


class GitManager:
    """
    Git 操作管理器

    封装常见的 Git 操作：检查状态、拉取、提交和推送。
    所有公共方法均返回 (bool, str)，上层根据 bool 判断操作是否成功，
    并根据 str 提示用户（成功消息或错误说明）。
    """

    def __init__(self, repo_path: Union[str, Path]):
        """
        初始化 GitManager，尝试打开指定路径的 Git 仓库。

        Args:
            repo_path: 本地仓库路径（字符串或 Path 对象）

        如果路径不存在或不是合法的 Git 仓库，则记录错误并将 self.repo 置为 None，
        后续调用 is_valid() 将返回 False，其他方法也会返回错误提示。
        """
        self.repo_path = Path(repo_path).resolve()
        self.repo = None
        try:
            self.repo = Repo(self.repo_path)
            # 确保这是一个非 bare 仓库
            if self.repo.bare:
                logger.error(f"仓库是 bare 仓库，无法操作: {self.repo_path}")
                self.repo = None
            else:
                logger.info(f"成功打开 Git 仓库: {self.repo_path}")
        except (InvalidGitRepositoryError, NoSuchPathError) as e:
            logger.error(f"无法打开 Git 仓库 {self.repo_path}: {e}")
        except Exception as e:
            logger.exception(f"打开 Git 仓库时发生未知错误: {e}")

    def is_valid(self) -> bool:
        """检查当前 GitManager 是否绑定了一个有效的 Git 仓库。"""
        return self.repo is not None and not self.repo.bare

    def _ensure_valid(self) -> Tuple[bool, str]:
        """
        内部辅助方法：检查仓库是否有效，若无效返回错误元组。

        Returns:
            Tuple[bool, str]: (False, 错误信息) 如果无效，否则 (True, "")
        """
        if not self.is_valid():
            return False, "尚未配置有效的 Git 仓库，请先在设置中指定正确的仓库路径。"
        return True, ""

    def check_uncommitted_changes(self) -> bool:
        """
        检查工作区是否有未提交的更改（包括未跟踪的文件）。

        Returns:
            bool: 有未提交更改返回 True，否则返回 False。
                  如果仓库无效，返回 False（但会记录警告）。
        """
        if not self.is_valid():
            logger.warning("尝试在无效仓库上检查未提交更改")
            return False
        # is_dirty() 检测工作区修改和暂存区未提交的更改
        # untracked_files=True 包括未跟踪的文件
        return self.repo.is_dirty(untracked_files=True)

    def pull_latest(self) -> Tuple[bool, str]:
        """
        执行 git pull 从远程仓库拉取最新更改。

        Returns:
            Tuple[bool, str]: (成功标志, 提示信息/错误信息)
        """
        # 1. 检查仓库有效性
        valid, err = self._ensure_valid()
        if not valid:
            return False, err

        # 2. 检查是否有远程仓库配置
        try:
            origin = self.repo.remote(name='origin')
        except ValueError:
            return False, "未配置远程仓库（origin），请先在 Git 中设置远程地址。"

        # 3. 执行 pull
        try:
            # pull 会返回拉取的信息，我们只关心是否成功
            pull_info = origin.pull()
            logger.info(f"Pull 成功: {pull_info}")
            return True, "已成功从远程仓库拉取最新更改。"
        except GitCommandError as e:
            # Git 命令执行失败，可能是网络问题、冲突、认证失败等
            logger.error(f"Pull 失败: {e}")
            # 尝试根据错误信息返回友好的中文提示
            stderr = e.stderr.lower() if e.stderr else ""
            if "conflict" in stderr:
                return False, "拉取时发生冲突，请手动解决冲突或联系管理员。"
            elif "authentication" in stderr or "auth" in stderr:
                return False, "远程仓库认证失败，请检查用户名/密码或 SSH 密钥。"
            elif "could not resolve host" in stderr or "connection refused" in stderr:
                return False, "无法连接到远程仓库，请检查网络连接。"
            else:
                return False, f"拉取失败：{e.stderr or str(e)}"
        except Exception as e:
            logger.exception(f"Pull 时发生未知异常: {e}")
            return False, f"拉取时发生未知错误：{str(e)}"

    def commit_and_push(self, commit_message: str = "Update content via Group Site Manager") -> Tuple[bool, str]:
        """
        提交所有更改并推送到远程仓库。

        执行流程：
            1. 检查是否有更改，若无更改则直接返回成功。
            2. git add .
            3. git commit -m <message> （无论是否有远程仓库，都先在本地提交）
            4. 检查是否有远程仓库，若无则返回“已在本地提交但无法推送”的提示。
            5. 如果有远程仓库，执行 git push（指定当前分支以避免上游分支问题）。

        Args:
            commit_message: 提交信息，默认为 "Update content via Group Site Manager"

        Returns:
            Tuple[bool, str]: (成功标志, 提示信息/错误信息)
        """
        # 1. 检查仓库有效性
        valid, err = self._ensure_valid()
        if not valid:
            return False, err

        # 2. 检查是否有更改
        if not self.check_uncommitted_changes():
            return True, "没有需要同步的更改。"

        # 3. 执行 add 和 commit（本地提交，与远程无关）
        try:
            self.repo.git.add(A=True)
            logger.info("执行 git add . 成功")
            self.repo.index.commit(commit_message)
            logger.info(f"执行 git commit -m '{commit_message}' 成功")
        except GitCommandError as e:
            logger.error(f"Add 或 Commit 失败: {e}")
            return False, f"本地提交失败：{e.stderr or str(e)}"
        except Exception as e:
            logger.exception(f"Add/Commit 时发生未知异常: {e}")
            return False, f"本地提交时发生未知错误：{str(e)}"

        # 4. 检查是否有远程仓库
        try:
            origin = self.repo.remote(name='origin')
        except ValueError:
            # 没有远程仓库，提交已完成但无法推送
            return True, "更改已在本地提交，但未配置远程仓库，无法推送到服务器。"

        # 5. 执行 push（指定当前分支以避免上游分支未设置的问题）
        try:
            current_branch = self.repo.active_branch.name
            push_info = origin.push(current_branch)
            logger.info(f"Push 成功: {push_info}")
            return True, "更改已成功推送到远程仓库。"
        except GitCommandError as e:
            logger.error(f"Push 失败: {e}")
            stderr = e.stderr.lower() if e.stderr else ""
            if "fetch first" in stderr:
                return False, "推送失败，远程仓库有更新尚未拉取。请先执行“拉取”操作。"
            elif "authentication" in stderr or "auth" in stderr:
                return False, "远程仓库认证失败，请检查用户名/密码或 SSH 密钥。"
            elif "could not resolve host" in stderr or "connection refused" in stderr:
                return False, "无法连接到远程仓库，请检查网络连接。"
            elif "no upstream branch" in stderr:
                # 常见于本地分支尚未与远程分支建立追踪关系
                return False, "当前分支没有设置上游分支，请先在终端执行一次推送：git push -u origin main（将 main 替换为你的分支名）"
            else:
                return False, f"推送失败：{e.stderr or str(e)}"
        except Exception as e:
            logger.exception(f"Push 时发生未知异常: {e}")
            return False, f"推送时发生未知错误：{str(e)}"