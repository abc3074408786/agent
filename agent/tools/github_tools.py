"""
GitHub 集成工具

通过 subprocess 调用 gh CLI 实现:
- github_create_pr: 创建 Pull Request
- github_list_issues: 列出 Issues
- github_get_issue: 获取单个 Issue 详情

依赖: gh CLI (GitHub CLI) 已安装并认证
"""

import subprocess
import json
from typing import Optional

from pydantic import BaseModel, Field

from agent.tools import create_tool, ToolRegistry


# ============ Input Schemas ============

class GitHubCreatePRInput(BaseModel):
    """创建 Pull Request 输入"""
    title: str = Field(description="PR 标题")
    body: str = Field(default="", description="PR 描述内容")
    base: str = Field(default="main", description="目标分支（默认 main）")
    head: Optional[str] = Field(default=None, description="源分支（默认当前分支）")
    draft: bool = Field(default=False, description="是否创建为草稿 PR")
    repo: Optional[str] = Field(default=None, description="仓库 (owner/repo 格式)，默认当前仓库")
    cwd: str = Field(default=".", description="工作目录（Git 仓库路径）")


class GitHubListIssuesInput(BaseModel):
    """列出 Issues 输入"""
    state: str = Field(default="open", description="Issue 状态: open, closed, all")
    labels: Optional[str] = Field(default=None, description="标签过滤（逗号分隔）")
    assignee: Optional[str] = Field(default=None, description="指派人过滤")
    limit: int = Field(default=20, description="最大返回数量")
    repo: Optional[str] = Field(default=None, description="仓库 (owner/repo 格式)，默认当前仓库")
    cwd: str = Field(default=".", description="工作目录（Git 仓库路径）")


class GitHubGetIssueInput(BaseModel):
    """获取 Issue 详情输入"""
    number: int = Field(description="Issue 编号")
    repo: Optional[str] = Field(default=None, description="仓库 (owner/repo 格式)，默认当前仓库")
    cwd: str = Field(default=".", description="工作目录（Git 仓库路径）")


# ============ 辅助函数 ============

def _run_gh_command(args: list, cwd: str = ".") -> str:
    """执行 gh CLI 命令"""
    try:
        result = subprocess.run(
            ["gh"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return f"GitHub CLI 错误:\n{error_msg}"
        
        return result.stdout.strip() if result.stdout else "(操作成功，无输出)"
        
    except subprocess.TimeoutExpired:
        return "错误: GitHub CLI 命令执行超时（30秒）"
    except FileNotFoundError:
        return "错误: 未找到 gh 命令。请安装 GitHub CLI: https://cli.github.com/"
    except Exception as e:
        return f"错误: 执行 gh 命令失败 - {str(e)}"


# ============ 工具函数 ============

def github_create_pr(
    title: str,
    body: str = "",
    base: str = "main",
    head: Optional[str] = None,
    draft: bool = False,
    repo: Optional[str] = None,
    cwd: str = ".",
) -> str:
    """
    创建 Pull Request
    
    使用 gh pr create 命令创建 PR。
    """
    args = ["pr", "create"]
    
    args.extend(["--title", title])
    
    if body:
        args.extend(["--body", body])
    else:
        args.extend(["--body", ""])
    
    args.extend(["--base", base])
    
    if head:
        args.extend(["--head", head])
    
    if draft:
        args.append("--draft")
    
    if repo:
        args.extend(["--repo", repo])
    
    result = _run_gh_command(args, cwd=cwd)
    
    return result


def github_list_issues(
    state: str = "open",
    labels: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 20,
    repo: Optional[str] = None,
    cwd: str = ".",
) -> str:
    """
    列出 Issues
    
    使用 gh issue list 命令列出仓库的 issues。
    """
    args = ["issue", "list"]
    
    args.extend(["--state", state])
    args.extend(["--limit", str(min(limit, 100))])  # 限制最大100
    
    if labels:
        args.extend(["--label", labels])
    
    if assignee:
        args.extend(["--assignee", assignee])
    
    if repo:
        args.extend(["--repo", repo])
    
    # 使用 JSON 输出以获得结构化数据
    args.extend(["--json", "number,title,state,author,labels,createdAt,updatedAt"])
    
    result = _run_gh_command(args, cwd=cwd)
    
    # 尝试格式化 JSON 输出
    if result and not result.startswith("错误") and not result.startswith("GitHub CLI"):
        try:
            issues = json.loads(result)
            if not issues:
                return "没有找到匹配的 Issues"
            
            output_lines = [f"Issues ({state}): 共 {len(issues)} 个\n"]
            
            for issue in issues:
                labels_str = ", ".join(
                    label.get("name", "") for label in issue.get("labels", [])
                )
                author = issue.get("author", {}).get("login", "unknown")
                
                line = f"  #{issue['number']} [{issue['state']}] {issue['title']}"
                if labels_str:
                    line += f" ({labels_str})"
                line += f" - by {author}"
                
                output_lines.append(line)
            
            return "\n".join(output_lines)
        except json.JSONDecodeError:
            pass
    
    return result


def github_get_issue(
    number: int,
    repo: Optional[str] = None,
    cwd: str = ".",
) -> str:
    """
    获取单个 Issue 详情
    
    使用 gh issue view 命令获取 issue 的完整信息。
    """
    args = ["issue", "view", str(number)]
    
    if repo:
        args.extend(["--repo", repo])
    
    # 使用 JSON 输出
    args.extend(["--json", "number,title,state,body,author,labels,assignees,comments,createdAt,updatedAt,closedAt"])
    
    result = _run_gh_command(args, cwd=cwd)
    
    # 尝试格式化输出
    if result and not result.startswith("错误") and not result.startswith("GitHub CLI"):
        try:
            issue = json.loads(result)
            
            output_lines = [
                f"Issue #{issue['number']}: {issue['title']}",
                f"状态: {issue['state']}",
                f"作者: {issue.get('author', {}).get('login', 'unknown')}",
                f"创建时间: {issue.get('createdAt', '')}",
                f"更新时间: {issue.get('updatedAt', '')}",
            ]
            
            # 标签
            labels = issue.get("labels", [])
            if labels:
                label_names = [l.get("name", "") for l in labels]
                output_lines.append(f"标签: {', '.join(label_names)}")
            
            # 指派人
            assignees = issue.get("assignees", [])
            if assignees:
                assignee_names = [a.get("login", "") for a in assignees]
                output_lines.append(f"指派: {', '.join(assignee_names)}")
            
            # 正文
            body = issue.get("body", "").strip()
            if body:
                output_lines.append(f"\n--- 描述 ---\n{body}")
            
            # 评论
            comments = issue.get("comments", [])
            if comments:
                output_lines.append(f"\n--- 评论 ({len(comments)}) ---")
                for comment in comments[:10]:  # 最多显示10条
                    author = comment.get("author", {}).get("login", "unknown")
                    created = comment.get("createdAt", "")[:10]
                    comment_body = comment.get("body", "")[:300]
                    output_lines.append(f"\n[{author} @ {created}]")
                    output_lines.append(comment_body)
            
            return "\n".join(output_lines)
        except json.JSONDecodeError:
            pass
    
    return result


# ============ 创建 LangChain 工具 ============

github_create_pr_tool = create_tool(
    name="github_create_pr",
    description="创建 GitHub Pull Request。需要 gh CLI 已安装并认证。支持设置标题、描述、目标分支和草稿模式。",
    func=github_create_pr,
    args_schema=GitHubCreatePRInput,
)

github_list_issues_tool = create_tool(
    name="github_list_issues",
    description="列出 GitHub 仓库的 Issues。支持按状态、标签、指派人过滤。需要 gh CLI。",
    func=github_list_issues,
    args_schema=GitHubListIssuesInput,
)

github_get_issue_tool = create_tool(
    name="github_get_issue",
    description="获取单个 GitHub Issue 的详细信息，包括描述、评论、标签和指派人。需要 gh CLI。",
    func=github_get_issue,
    args_schema=GitHubGetIssueInput,
)


# ============ 注册函数 ============

def register_github_tools(registry: ToolRegistry) -> None:
    """注册所有 GitHub 工具到注册器"""
    registry.register(github_create_pr_tool, category="github", tags=["github", "pr", "pull-request"])
    registry.register(github_list_issues_tool, category="github", tags=["github", "issues", "list"])
    registry.register(github_get_issue_tool, category="github", tags=["github", "issue", "detail"])
