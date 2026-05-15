"""
Bash 工具 - 安全的 shell 命令执行

提供:
- bash_execute: 执行 bash 命令并返回 stdout/stderr
- 安全限制: 命令黑名单、超时、输出长度限制
- 使用 asyncio.subprocess 异步执行
"""

import asyncio
import shlex
import re
from typing import Optional

from pydantic import BaseModel, Field

from agent.tools import create_tool, ToolRegistry


# ============ 安全配置 ============

# 命令黑名单 - 危险命令模式
COMMAND_BLACKLIST = [
    # 文件系统破坏
    r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\s*$",  # rm -rf /
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/",  # rm -rf /path (root)
    r"\bdd\b.*\bof=/dev/",  # dd of=/dev/...
    r"\bmkfs\b",  # mkfs
    r"\bformat\b",  # format
    # 系统破坏
    r":\(\)\{\s*:\|:&\s*\};:",  # fork bomb
    r"\b>\s*/dev/sd",  # write to disk device
    r"\bchmod\s+-R\s+777\s+/",  # chmod -R 777 /
    r"\bchown\s+-R\s+.*\s+/\s*$",  # chown -R ... /
    # 网络攻击
    r"\bnc\s+-[a-zA-Z]*l",  # netcat listen (reverse shell)
    r"\bcurl\b.*\|\s*bash",  # curl | bash
    r"\bwget\b.*\|\s*bash",  # wget | bash
    r"\bcurl\b.*\|\s*sh",  # curl | sh
    r"\bwget\b.*\|\s*sh",  # wget | sh
    # 密码和凭证
    r"\bpasswd\b",  # passwd
    r"/etc/shadow",  # shadow file
    # 关机重启
    r"\bshutdown\b",  # shutdown
    r"\breboot\b",  # reboot
    r"\binit\s+[0-6]",  # init level
    r"\bhalt\b",  # halt
    r"\bpoweroff\b",  # poweroff
]

# 单条命令黑名单（精确匹配命令名）
EXACT_BLACKLIST = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -rf ~/*",
    ":(){ :|:& };:",
    "dd if=/dev/zero of=/dev/sda",
    "mkfs.ext4 /dev/sda",
    "shutdown -h now",
    "reboot",
    "halt",
    "poweroff",
]

# 默认配置
DEFAULT_TIMEOUT = 30  # 秒
MAX_OUTPUT_LENGTH = 10000  # 字符
MAX_COMMAND_LENGTH = 2000  # 命令最大长度


def _is_command_safe(command: str) -> tuple[bool, str]:
    """
    检查命令是否安全

    Returns:
        (is_safe, reason) - 是否安全及原因
    """
    # 检查命令长度
    if len(command) > MAX_COMMAND_LENGTH:
        return False, f"命令过长（最大 {MAX_COMMAND_LENGTH} 字符）"

    # 精确黑名单
    cmd_stripped = command.strip()
    for blocked in EXACT_BLACKLIST:
        if cmd_stripped == blocked:
            return False, f"命令被禁止: '{blocked}'"

    # 正则黑名单
    for pattern in COMMAND_BLACKLIST:
        if re.search(pattern, command):
            return False, f"命令包含危险模式: '{pattern}'"

    # 检查是否尝试访问敏感文件
    sensitive_patterns = [
        r"\.env\b",
        r"\.ssh/",
        r"/etc/shadow",
        r"/etc/passwd",
        r"id_rsa",
        r"id_ed25519",
    ]
    for pattern in sensitive_patterns:
        if re.search(pattern, command):
            # 允许 cat .env.example 等
            if ".env.example" in command or ".env.template" in command:
                continue
            # 只有直接操作敏感文件的命令才被阻止
            if any(op in command for op in ["cat ", "less ", "more ", "head ", "tail ", "cp ", "mv "]):
                if re.search(r"\.(env|env\.local|env\.production)\b", command):
                    return False, f"不允许访问敏感文件"

    return True, ""


def _truncate_output(output: str, max_length: int = MAX_OUTPUT_LENGTH) -> str:
    """截断过长的输出"""
    if len(output) <= max_length:
        return output

    half = max_length // 2
    truncated_msg = f"\n\n... [输出被截断，总长度 {len(output)} 字符，显示前 {half} 和后 {half} 字符] ...\n\n"
    return output[:half] + truncated_msg + output[-half:]


# ============ Input Schema ============

class BashExecuteInput(BaseModel):
    """Bash 执行输入"""
    command: str = Field(description="要执行的 bash 命令")
    cwd: Optional[str] = Field(default=None, description="工作目录路径（可选）")
    timeout: int = Field(default=DEFAULT_TIMEOUT, description=f"超时时间（秒），默认 {DEFAULT_TIMEOUT}s，最大 120s")


# ============ 工具函数 ============

async def bash_execute(command: str, cwd: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> str:
    """
    执行 bash 命令并返回结果

    安全限制:
    - 命令黑名单检查
    - 超时限制（默认 30s，最大 120s）
    - 输出长度限制（最大 10000 字符）
    """
    # 安全检查
    is_safe, reason = _is_command_safe(command)
    if not is_safe:
        return f"错误: 命令被安全策略阻止 - {reason}"

    # 限制超时范围
    timeout = max(1, min(timeout, 120))

    # 验证工作目录
    if cwd:
        import os
        if not os.path.isdir(cwd):
            return f"错误: 工作目录不存在 '{cwd}'"

    try:
        # 使用 asyncio.subprocess 执行命令
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            return f"错误: 命令执行超时（{timeout}秒）\n命令: {command}"

        # 解码输出
        stdout_str = stdout.decode("utf-8", errors="replace") if stdout else ""
        stderr_str = stderr.decode("utf-8", errors="replace") if stderr else ""

        # 构建结果
        parts = []

        if stdout_str:
            parts.append(_truncate_output(stdout_str))

        if stderr_str:
            parts.append(f"[STDERR]\n{_truncate_output(stderr_str)}")

        if process.returncode != 0:
            parts.append(f"\n[退出码: {process.returncode}]")

        result = "\n".join(parts) if parts else "(无输出)"

        # 最终长度检查
        return _truncate_output(result)

    except FileNotFoundError:
        return f"错误: 命令未找到 - 请检查命令是否正确"
    except PermissionError:
        return f"错误: 权限不足"
    except Exception as e:
        return f"错误: 执行命令失败 - {type(e).__name__}: {str(e)}"


# ============ 创建 LangChain 工具 ============

bash_execute_tool = create_tool(
    name="bash_execute",
    description=(
        "执行 bash 命令并返回 stdout/stderr。"
        "支持设置工作目录和超时时间。"
        "安全限制: 禁止危险命令（如 rm -rf /、dd、mkfs、fork bomb 等），"
        "超时限制最大 120 秒，输出最大 10000 字符。"
    ),
    func=bash_execute,
    args_schema=BashExecuteInput,
)


# ============ 注册函数 ============

def register_bash_tools(registry: ToolRegistry) -> None:
    """注册 Bash 工具到注册器"""
    registry.register(bash_execute_tool, category="system", tags=["bash", "shell", "command"])
