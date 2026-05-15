"""
文件操作工具集

提供安全的文件系统操作工具:
- file_read: 读取文件内容（支持行号范围）
- file_write: 创建/覆盖文件
- file_edit: 字符串替换编辑
- grep_search: 用正则搜索文件内容
- glob_search: 按模式搜索文件路径
- list_directory: 列出目录内容
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Optional, List

from pydantic import BaseModel, Field

from agent.tools import create_tool, ToolRegistry


# ============ 安全校验 ============

# 敏感路径模式 - 禁止访问
SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    ".ssh",
    ".ssh/*",
    ".gnupg",
    ".gnupg/*",
    ".aws/credentials",
    ".config/gcloud",
    "id_rsa",
    "id_ed25519",
    ".git/config",
    "__pycache__",
]

# 敏感目录前缀
SENSITIVE_DIRS = [
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/gcloud",
]


def _is_sensitive_path(path: str) -> bool:
    """检查路径是否为敏感路径"""
    path_obj = Path(path)
    name = path_obj.name
    parts = path_obj.parts

    # 检查文件名模式
    for pattern in SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
        # 检查完整路径
        if fnmatch.fnmatch(str(path_obj), f"*/{pattern}"):
            return True

    # 检查路径中是否包含敏感目录
    for part in parts:
        if part in (".ssh", ".gnupg"):
            return True

    # 检查 .env 文件（各种形式）
    if name.startswith(".env"):
        return True

    return False


def _resolve_path(path: str, base_dir: Optional[str] = None) -> str:
    """解析路径，确保安全"""
    if base_dir:
        resolved = Path(base_dir) / path
    else:
        resolved = Path(path)

    resolved = resolved.resolve()

    # 检查敏感路径
    if _is_sensitive_path(str(resolved)):
        raise PermissionError(f"访问被拒绝: 路径 '{path}' 是敏感文件/目录")

    return str(resolved)


# ============ Input Schemas ============

class FileReadInput(BaseModel):
    """文件读取输入"""
    path: str = Field(description="要读取的文件路径")
    start_line: Optional[int] = Field(default=None, description="起始行号（从1开始）")
    end_line: Optional[int] = Field(default=None, description="结束行号（包含）")


class FileWriteInput(BaseModel):
    """文件写入输入"""
    path: str = Field(description="要写入的文件路径")
    content: str = Field(description="要写入的内容")
    create_dirs: bool = Field(default=True, description="是否自动创建父目录")


class FileEditInput(BaseModel):
    """文件编辑输入（字符串替换）"""
    path: str = Field(description="要编辑的文件路径")
    old_str: str = Field(description="要替换的原始字符串（必须精确匹配）")
    new_str: str = Field(description="替换后的新字符串")


class GrepSearchInput(BaseModel):
    """正则搜索输入"""
    pattern: str = Field(description="正则表达式模式")
    path: str = Field(default=".", description="搜索的根路径（文件或目录）")
    include_pattern: Optional[str] = Field(default=None, description="文件名包含模式，如 '*.py'")
    max_results: int = Field(default=50, description="最大结果数量")
    case_sensitive: bool = Field(default=True, description="是否区分大小写")


class GlobSearchInput(BaseModel):
    """Glob 搜索输入"""
    pattern: str = Field(description="Glob 模式，如 '**/*.py' 或 'src/**/*.ts'")
    path: str = Field(default=".", description="搜索根目录")
    max_results: int = Field(default=100, description="最大结果数量")


class ListDirectoryInput(BaseModel):
    """目录列表输入"""
    path: str = Field(default=".", description="目录路径")
    show_hidden: bool = Field(default=False, description="是否显示隐藏文件")
    max_depth: int = Field(default=1, description="最大递归深度")


# ============ 工具函数 ============

def file_read(path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """读取文件内容，支持行号范围"""
    try:
        resolved = _resolve_path(path)

        if not os.path.exists(resolved):
            return f"错误: 文件不存在 '{path}'"

        if not os.path.isfile(resolved):
            return f"错误: '{path}' 不是文件"

        # 检查文件大小（限制 1MB）
        size = os.path.getsize(resolved)
        if size > 1_000_000:
            return f"错误: 文件过大 ({size} bytes)，请使用行号范围读取"

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)

        if start_line is not None or end_line is not None:
            start = (start_line or 1) - 1  # 转为0索引
            end = end_line or total_lines

            # 边界检查
            start = max(0, min(start, total_lines))
            end = max(0, min(end, total_lines))

            selected = lines[start:end]
            content = "".join(selected)

            header = f"[文件: {path}, 行 {start + 1}-{end}/{total_lines}]\n"
            return header + content
        else:
            content = "".join(lines)
            header = f"[文件: {path}, 共 {total_lines} 行]\n"
            return header + content

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: 读取文件失败 - {str(e)}"


def file_write(path: str, content: str, create_dirs: bool = True) -> str:
    """创建或覆盖文件"""
    try:
        resolved = _resolve_path(path)

        if _is_sensitive_path(resolved):
            return f"错误: 不允许写入敏感路径 '{path}'"

        if create_dirs:
            os.makedirs(os.path.dirname(resolved) or ".", exist_ok=True)

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(content)

        lines = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"成功: 已写入文件 '{path}' ({lines} 行, {len(content)} 字符)"

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: 写入文件失败 - {str(e)}"


def file_edit(path: str, old_str: str, new_str: str) -> str:
    """字符串替换编辑文件"""
    try:
        resolved = _resolve_path(path)

        if not os.path.exists(resolved):
            return f"错误: 文件不存在 '{path}'"

        if _is_sensitive_path(resolved):
            return f"错误: 不允许编辑敏感路径 '{path}'"

        with open(resolved, "r", encoding="utf-8") as f:
            content = f.read()

        # 检查 old_str 是否存在
        count = content.count(old_str)
        if count == 0:
            return f"错误: 未找到匹配的字符串。请确保 old_str 精确匹配文件中的内容（包括空格和缩进）。"
        if count > 1:
            return f"错误: 找到 {count} 处匹配。请提供更多上下文使匹配唯一。"

        # 执行替换
        new_content = content.replace(old_str, new_str, 1)

        with open(resolved, "w", encoding="utf-8") as f:
            f.write(new_content)

        # 计算变更信息
        old_lines = old_str.count("\n") + 1
        new_lines = new_str.count("\n") + 1
        return f"成功: 已编辑 '{path}' (替换了 {old_lines} 行为 {new_lines} 行)"

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: 编辑文件失败 - {str(e)}"


def grep_search(
    pattern: str,
    path: str = ".",
    include_pattern: Optional[str] = None,
    max_results: int = 50,
    case_sensitive: bool = True,
) -> str:
    """用正则表达式搜索文件内容"""
    try:
        resolved = _resolve_path(path)

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return f"错误: 正则表达式无效 - {str(e)}"

        results = []
        files_searched = 0

        if os.path.isfile(resolved):
            # 搜索单个文件
            matches = _search_file(resolved, regex)
            results.extend(matches)
            files_searched = 1
        elif os.path.isdir(resolved):
            # 递归搜索目录
            for root, dirs, files in os.walk(resolved):
                # 跳过隐藏目录和常见排除目录
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv", ".venv")
                ]

                for filename in files:
                    if filename.startswith("."):
                        continue

                    # 应用文件名过滤
                    if include_pattern and not fnmatch.fnmatch(filename, include_pattern):
                        continue

                    filepath = os.path.join(root, filename)

                    # 跳过敏感文件
                    if _is_sensitive_path(filepath):
                        continue

                    # 跳过二进制文件
                    if _is_binary(filepath):
                        continue

                    matches = _search_file(filepath, regex, base_path=resolved)
                    results.extend(matches)
                    files_searched += 1

                    if len(results) >= max_results:
                        break

                if len(results) >= max_results:
                    break
        else:
            return f"错误: 路径不存在 '{path}'"

        # 格式化输出
        if not results:
            return f"未找到匹配 (搜索了 {files_searched} 个文件)"

        output_lines = [f"找到 {len(results)} 处匹配 (搜索了 {files_searched} 个文件):"]
        output_lines.append("")

        for match in results[:max_results]:
            output_lines.append(f"{match['file']}:{match['line_no']}: {match['text'].rstrip()}")

        if len(results) > max_results:
            output_lines.append(f"\n... 截断，共 {len(results)} 处匹配")

        return "\n".join(output_lines)

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: 搜索失败 - {str(e)}"


def _search_file(filepath: str, regex: re.Pattern, base_path: Optional[str] = None) -> List[dict]:
    """搜索单个文件"""
    matches = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line_no, line in enumerate(f, 1):
                if regex.search(line):
                    rel_path = os.path.relpath(filepath, base_path) if base_path else filepath
                    matches.append({
                        "file": rel_path,
                        "line_no": line_no,
                        "text": line,
                    })
    except (OSError, UnicodeDecodeError):
        pass
    return matches


def _is_binary(filepath: str) -> bool:
    """检查文件是否为二进制"""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(1024)
            return b"\x00" in chunk
    except OSError:
        return True


def glob_search(pattern: str, path: str = ".", max_results: int = 100) -> str:
    """按模式搜索文件路径"""
    try:
        resolved = _resolve_path(path)

        if not os.path.isdir(resolved):
            return f"错误: 目录不存在 '{path}'"

        search_path = Path(resolved)
        results = []

        for match in search_path.glob(pattern):
            # 跳过敏感路径
            if _is_sensitive_path(str(match)):
                continue

            rel_path = match.relative_to(search_path)
            # 跳过隐藏文件和排除目录
            parts = rel_path.parts
            if any(p.startswith(".") for p in parts):
                continue
            if any(p in ("node_modules", "__pycache__", "venv", ".venv") for p in parts):
                continue

            suffix = "/" if match.is_dir() else ""
            results.append(str(rel_path) + suffix)

            if len(results) >= max_results:
                break

        if not results:
            return f"未找到匹配模式 '{pattern}' 的文件"

        output = f"找到 {len(results)} 个匹配:\n\n"
        output += "\n".join(sorted(results))

        if len(results) >= max_results:
            output += f"\n\n... 结果已截断 (最大 {max_results})"

        return output

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: Glob 搜索失败 - {str(e)}"


def list_directory(path: str = ".", show_hidden: bool = False, max_depth: int = 1) -> str:
    """列出目录内容"""
    try:
        resolved = _resolve_path(path)

        if not os.path.isdir(resolved):
            return f"错误: 目录不存在 '{path}'"

        output_lines = [f"目录: {path}"]
        output_lines.append("")

        _list_dir_recursive(resolved, output_lines, show_hidden, max_depth, current_depth=0, prefix="")

        return "\n".join(output_lines)

    except PermissionError as e:
        return f"错误: {str(e)}"
    except Exception as e:
        return f"错误: 列出目录失败 - {str(e)}"


def _list_dir_recursive(
    dir_path: str,
    output: List[str],
    show_hidden: bool,
    max_depth: int,
    current_depth: int,
    prefix: str,
) -> None:
    """递归列出目录"""
    try:
        entries = sorted(os.listdir(dir_path))
    except PermissionError:
        output.append(f"{prefix}[权限不足]")
        return

    # 过滤
    if not show_hidden:
        entries = [e for e in entries if not e.startswith(".")]

    # 排除常见无用目录
    entries = [e for e in entries if e not in ("node_modules", "__pycache__", ".git", "venv", ".venv")]

    dirs = []
    files = []

    for entry in entries:
        full_path = os.path.join(dir_path, entry)
        if os.path.isdir(full_path):
            dirs.append(entry)
        else:
            files.append(entry)

    # 先列出目录
    for d in dirs:
        size_info = ""
        output.append(f"{prefix}{d}/")
        if current_depth < max_depth - 1:
            _list_dir_recursive(
                os.path.join(dir_path, d),
                output,
                show_hidden,
                max_depth,
                current_depth + 1,
                prefix + "  ",
            )

    # 再列出文件
    for f in files:
        full_path = os.path.join(dir_path, f)
        try:
            size = os.path.getsize(full_path)
            size_str = _format_size(size)
            output.append(f"{prefix}{f}  ({size_str})")
        except OSError:
            output.append(f"{prefix}{f}")


def _format_size(size: int) -> str:
    """格式化文件大小"""
    if size < 1024:
        return f"{size}B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    else:
        return f"{size / (1024 * 1024):.1f}MB"


# ============ 创建 LangChain 工具 ============

file_read_tool = create_tool(
    name="file_read",
    description="读取文件内容。支持指定行号范围读取部分内容。文件大小限制 1MB。",
    func=file_read,
    args_schema=FileReadInput,
)

file_write_tool = create_tool(
    name="file_write",
    description="创建或覆盖文件。自动创建父目录。禁止写入敏感文件（如 .env, .ssh）。",
    func=file_write,
    args_schema=FileWriteInput,
)

file_edit_tool = create_tool(
    name="file_edit",
    description="通过字符串替换编辑文件。old_str 必须精确匹配文件中的内容（包含空格和缩进），且匹配必须唯一。",
    func=file_edit,
    args_schema=FileEditInput,
)

grep_search_tool = create_tool(
    name="grep_search",
    description="用正则表达式搜索文件内容。支持递归搜索目录、文件名过滤、大小写控制。",
    func=grep_search,
    args_schema=GrepSearchInput,
)

glob_search_tool = create_tool(
    name="glob_search",
    description="按 glob 模式搜索文件路径。如 '**/*.py' 搜索所有 Python 文件。",
    func=glob_search,
    args_schema=GlobSearchInput,
)

list_directory_tool = create_tool(
    name="list_directory",
    description="列出目录内容，显示文件和子目录。支持递归深度控制和隐藏文件显示。",
    func=list_directory,
    args_schema=ListDirectoryInput,
)


# ============ 注册函数 ============

def register_file_tools(registry: ToolRegistry) -> None:
    """注册所有文件操作工具到注册器"""
    registry.register(file_read_tool, category="filesystem", tags=["file", "read"])
    registry.register(file_write_tool, category="filesystem", tags=["file", "write"])
    registry.register(file_edit_tool, category="filesystem", tags=["file", "edit"])
    registry.register(grep_search_tool, category="filesystem", tags=["search", "grep", "regex"])
    registry.register(glob_search_tool, category="filesystem", tags=["search", "glob", "files"])
    registry.register(list_directory_tool, category="filesystem", tags=["directory", "list"])
