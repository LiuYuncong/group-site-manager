# Group Site Manager

一个专为学术课题组设计的 Hugo 网站内容管理桌面应用。
无需任何 Git、Markdown 或命令行知识，即可轻松维护基于 Hugo (Blox 框架) 的静态学术网站。

[https://screenshot.png](https://screenshot.png/)
*(截图占位，运行后可见实际界面)*

## ✨ 功能特性

- **图形化内容管理** – 在熟悉的表单中编辑文章、作者、成果等，无需手动编写 Markdown。
- **自动 Git 同步** – 一键拉取/提交/推送，静默管理版本，无技术背景也能协作。
- **本地实时预览** – 点击「本地预览」自动启动 Hugo 服务器并在浏览器中查看效果。
- **多模块支持** – 内置 `post`（新闻）、`authors`（团队成员）、`publication`（成果）、`resource`（资源）等模块。
- **图片自动处理** – 上传图片自动复制到正确位置并重命名为 `featured.jpg` 或 `avatar.jpg`。
- **跨平台** – 基于 Python 和 CustomTkinter，可在 Windows、macOS、Linux 上运行。

## 📦 安装前提

- Python 3.8 或更高版本
- Git（可选，若需远程同步）
- Hugo（可选，若需本地预览）

## 🚀 快速开始

### 1. 获取代码

bash

```
git clone https://github.com/yourgroup/group-site-manager.git
cd group-site-manager
```



### 2. 创建虚拟环境并安装依赖

bash

```
python -m venv venv
source venv/bin/activate      # Linux/macOS
# 或 .\venv\Scripts\activate  # Windows

pip install -r requirements.txt
```



### 3. 配置网站仓库路径

首次运行会自动生成配置文件 `~/.group-site-manager/config.json`。
**请编辑该文件**，将 `repo_path` 改为你的 Hugo 网站根目录（即 `hugo` 命令所在的文件夹）：

json

```
{
    "repo_path": "/home/username/my-hugo-site",
    "remote_git_url": "https://github.com/yourlab/website.git"
}
```



- `repo_path` **必须**指向一个已存在的目录（可以是空的，但 Git 功能需要该目录为 Git 仓库）。
- `remote_git_url` 为远程仓库地址，若无需远程同步可留空。

### 4. 启动程序

bash

```
python main.py
```



看到主窗口后即可开始使用。

## 🖥️ 使用指南

### 界面布局

- **左侧导航栏**：切换不同内容模块（新闻、团队成员、成果、资源、全局配置）。
- **顶部工具栏**：常用操作按钮（新建、拉取更新、提交推送、刷新 Git 状态、本地预览）。
- **右侧主工作区**：根据所选模块显示内容列表或编辑表单。

### 管理内容

1. **浏览列表**：点击左侧模块，右侧会列出所有现有条目（显示标题和日期）。
2. **新建条目**：点击顶部 `➕ 新建` 按钮，填写标题、日期、正文，可选择封面/头像图片，最后点击「保存」。
3. **编辑条目**：在列表中点击条目右侧的「编辑」按钮，修改信息后保存。

### Git 同步

- **状态指示**：左侧底部圆点绿色表示仓库有效，红色表示无效。
- **拉取更新**：点击 `⬇️ 拉取更新` 从远程仓库下载最新更改。
- **提交并推送**：点击 `📝 提交并推送`，输入备注后自动执行 `add`、`commit`、`push`。
  *若未配置远程仓库，仍会完成本地提交，但无法推送。*

### 本地预览

确保系统已安装 [Hugo](https://gohugo.io/installation/)，然后点击 `🌐 本地预览`，程序会自动运行 `hugo server -D` 并在默认浏览器中打开预览地址。

## ❓ 常见问题

**Q：启动时提示“无法打开 Git 仓库”**
A：请检查配置文件中的 `repo_path` 是否正确，且该目录是一个 Git 仓库（存在 `.git` 文件夹）。若无需 Git 功能，可忽略此警告。

**Q：点击预览按钮报错“未找到 Hugo 命令”**
A：请安装 Hugo 并将其所在目录添加到系统 PATH 环境变量中。

**Q：保存内容时提示“无法创建内容文件夹”**
A：请确保网站目录有写入权限，并且 `repo_path` 指向的路径存在。

**Q：Git 按钮一直显示禁用？**
A：程序在执行 Git 操作时会暂时禁用按钮，操作完成后会自动恢复。若长时间未恢复，可能是操作卡住，可重启程序。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request。请确保代码符合 PEP 8 规范，并添加必要的单元测试。

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](https://license/) 文件。

## 🙏 致谢

- 感谢 [Hugo](https://gohugo.io/) 和 [Blox](https://blox.com/) 提供的优秀静态站点框架。
- UI 基于 [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) 构建。
- 感谢所有课题组成员的反馈与支持。

------

**现在就开始用 Group Site Manager 轻松维护你的学术网站吧！**