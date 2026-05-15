"""
Git 工具集

提供 Git 仓库操作工具:
- git_status: 显示当前仓库状态
- git_diff: 显示文件差异
- git_log: 查看提交历史
- git_commit: 提交更改
- git_branch: 分支管理 (list/create/switch)
"""

import subprocess
from typing import Optional

from pydantic import BaseModel, Field

from agent.tools import create_tool, ToolRegistry


# ============ Input Schemas ============

class GitStatusInput(BaseModel):
    """Git status 输入"""
    path: str = Field(default=".", description="仓库路径")
    short: bool = Field(default=False, description="是否使用简短格式输出")


class GitDiffInput(BaseModel):
    """Git diff 输入"""
    path: str = Field(default=".", description="仓库路径")
    file: Optional[str] = Field(default=None, description="指定文件路径（可选，默认全部）")
    staged: bool = Field(default=False, description="是否查看暂存区的差异 (--staged)")
    commit: Optional[str] = Field(default=None, description="与指定 commit 比较")


class GitLogInput(BaseModel):
    """Git log 输入"""
    path: str = Field(default=".", description="仓库路径")
    max_count: int = Field(default=10, description="最大显示条数")
    oneline: bool = Field(default=True, description="是否使用单行格式")
    file: Optional[str] = Field(default=None, description="只查看指定文件的历史")
    author: Optional[str] = Field(default=None, description="按作者过滤")


class GitCommitInput(BaseModel):
    """Git commit 输入"""
    path: str = Field(default=".", description="仓库路径")
    message: str = Field(description="提交信息")
    files: Optional[str] = Field(default=None, description="要暂存的文件（空格分隔），为空则提交已暂存的内容")
    all: bool = Field(default=False, description="是否自动暂存所有已跟踪文件的修改 (-a)")


class GitBranchInput(BaseModel):
    """Git branch 输入"""
    path: str = Field(default=".", description="仓库路径")
    action: str = Field(
        default="list",
        description="操作类型: 'list' (列出分支), 'create' (创建分支), 'switch' (切换分支)"
    )
    name: Optional[str] = Field(default=None, description="分支名称（create/switch 时必需）")
    show_remote: bool = Field(default=False, description="list 时是否显示远程分支")


# ============ 工具函数 ============

def _run_git_command(args: list, cwd: str = ".") -> str:
    """执行 git 命令并返回结果"""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n"
            output += result.stderr
        
        if result.returncode != 0:
            return f"Git 错误 (退出码 {result.returncode}):\n{output}"
        
        return output if output else "(无输出)"
        
    except subprocess.TimeoutExpired:
        return "错误: Git 命令执行超时（30秒）"
    except FileNotFoundError:
        return "错误: 未找到 git 命令，请确保 git 已安装"
    except Exception as e:
        return f"错误: 执行 git 命令失败 - {str(e)}"


def git_status(path: str = ".", short: bool = False) -> str:
    """显示当前 Git 仓库状态"""
    args = ["status"]
    if short:
        args.append("--short")
    return _run_git_command(args, cwd=path)


def git_diff(
    path: str = ".",
    file: Optional[str] = None,
    staged: bool = False,
    commit: Optional[str] = None,
) -> str:
    """显示文件差异"""
    args = ["diff"]
    
    if staged:
        args.append("--staged")
    
    if commit:
        args.append(commit)
    
    if file:
        args.append("--")
        args.append(file)
    
    result = _run_git_command(args, cwd=path)
    
    # 限制输出长度
    if len(result) > 10000:
        result = result[:10000] + "\n\n... [差异输出被截断，总长度超过 10000 字符]"
    
    return result


def git_log(
    path: str = ".",
    max_count: int = 10,
    oneline: bool = True,
    file: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    """查看提交历史"""
    args = ["log", f"--max-count={max_count}"]
    
    if oneline:
        args.append("--oneline")
    else:
        args.append("--format=%H %an <%ae> %ad%n  %s%n")
        args.append("--date=short")
    
    if author:
        args.append(f"--author={author}")
    
    if file:
        args.append("--")
        args.append(file)
    
    return _run_git_command(args, cwd=path)


def git_commit(
    path: str = ".",
    message: str = "",
    files: Optional[str] = None,
    all: bool = False,
) -> str:
    """提交更改"""
    if not message:
        return "错误: 提交信息不能为空"
    
    # 如果指定了文件，先 add
    if files:
        file_list = files.split()
        add_result = _run_git_command(["add"] + file_list, cwd=path)
        if "错误" in add_result:
            return f"暂存文件失败:\n{add_result}"
    
    # 构建 commit 命令
    args = ["commit"]
    
    if all:
        args.append("-a")
    
    args.extend(["-m", message])
    
    return _run_git_command(args, cwd=path)


def git_branch(
    path: str = ".",
    action: str = "list",
    name: Optional[str] = None,
    show_remote: bool = False,
) -> str:
    """分支管理"""
    if action == "list":
        args = ["branch"]
        if show_remote:
            args.append("-a")
        return _run_git_command(args, cwd=path)
    
    elif action == "create":
        if not name:
            return "错误: 创建分支需要指定分支名称"
        return _run_git_command(["branch", name], cwd=path)
    
    elif action == "switch":
        if not name:
            return "错误: 切换分支需要指定分支名称"
        return _run_git_command(["checkout", name], cwd=path)
    
    else:
        return f"错误: 未知操作 '{action}'。支持的操作: list, create, switch"


# ============ 创建 LangChain 工具 ============

git_status_tool = create_tool(
    name="git_status",
    description="显示 Git 仓库当前状态，包括已修改、已暂存和未跟踪的文件。",
    func=git_status,
    args_schema=GitStatusInput,
)

git_diff_tool = create_tool(
    name="git_diff",
    description="显示 Git 文件差异。支持查看工作区差异、暂存区差异或与指定 commit 的比较。",
    func=git_diff,
    args_schema=GitDiffInput,
)

git_log_tool = create_tool(
    name="git_log",
    description="查看 Git 提交历史。支持按作者过滤、指定文件、自定义显示条数。",
    func=git_log,
    args_schema=GitLogInput,
)

git_commit_tool = create_tool(
    name="git_commit",
    description="提交 Git 更改。可以指定要暂存的文件或使用 -a 自动暂存所有已跟踪文件的修改。",
    func=git_commit,
    args_schema=GitCommitInput,
)

git_branch_tool = create_tool(
    name="git_branch",
    description="Git 分支管理。支持列出分支、创建新分支和切换分支。",
    func=git_branch,
    args_schema=GitBranchInput,
)


# ============ 注册函数 ============

def register_git_tools(registry: ToolRegistry) -> None:
    """注册所有 Git 工具到注册器"""
    registry.register(git_status_tool, category="git", tags=["git", "status", "vcs"])
    registry.register(git_diff_tool, category="git", tags=["git", "diff", "vcs"])
    registry.register(git_log_tool, category="git", tags=["git", "log", "history", "vcs"])
    registry.register(git_commit_tool, category="git", tags=["git", "commit", "vcs"])
    registry.register(git_branch_tool, category="git", tags=["git", "branch", "vcs"])
