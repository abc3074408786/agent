"""
MCP Server - Model Context Protocol 服务器

让 VS Code、Cursor、Windsurf、Claude Code 等 IDE
通过 MCP 协议调用 Agent 的工具。

启动: python -m agent.mcp_server
配置: 在 VS Code settings.json 中添加 mcp.servers

MCP 协议核心是 JSON-RPC 2.0 over stdio。
"""

import json
import sys
import asyncio
import logging
import traceback
from typing import Any, Dict, List, Optional

# 日志输出到 stderr，不能污染 stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ─── Tool Definitions ──────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "file_read",
        "description": "读取文件内容，支持指定行范围",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "start_line": {"type": "integer", "description": "起始行号 (可选)"},
                "end_line": {"type": "integer", "description": "结束行号 (可选)"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "file_write",
        "description": "写入文件内容，创建或覆盖",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
                "create_dirs": {"type": "boolean", "description": "是否自动创建目录", "default": True},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "file_edit",
        "description": "编辑文件：查找并替换指定文本",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "old_text": {"type": "string", "description": "要替换的原文本"},
                "new_text": {"type": "string", "description": "替换后的新文本"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "grep_search",
        "description": "在文件中搜索文本模式 (正则表达式)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "搜索模式 (正则表达式)"},
                "path": {"type": "string", "description": "搜索目录或文件路径"},
                "include": {"type": "string", "description": "文件名过滤 (glob 模式)"},
                "case_sensitive": {"type": "boolean", "description": "是否区分大小写", "default": True},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "glob_search",
        "description": "通过 glob 模式查找文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob 模式 (如 **/*.py)"},
                "path": {"type": "string", "description": "搜索根目录"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_directory",
        "description": "列出目录内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "目录路径"},
                "recursive": {"type": "boolean", "description": "是否递归列出", "default": False},
                "max_depth": {"type": "integer", "description": "最大递归深度", "default": 2},
            },
            "required": ["path"],
        },
    },
    {
        "name": "bash_execute",
        "description": "执行 bash 命令",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "cwd": {"type": "string", "description": "工作目录 (可选)"},
                "timeout": {"type": "integer", "description": "超时秒数", "default": 120},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "获取 git 仓库状态",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "仓库路径"},
            },
            "required": [],
        },
    },
    {
        "name": "git_diff",
        "description": "获取 git diff",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "仓库路径"},
                "staged": {"type": "boolean", "description": "是否只看 staged 的变更", "default": False},
                "commit": {"type": "string", "description": "对比的 commit (可选)"},
            },
            "required": [],
        },
    },
    {
        "name": "git_log",
        "description": "获取 git 提交历史",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "仓库路径"},
                "count": {"type": "integer", "description": "显示条数", "default": 10},
                "oneline": {"type": "boolean", "description": "单行格式", "default": True},
            },
            "required": [],
        },
    },
    {
        "name": "git_commit",
        "description": "创建 git commit",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Commit 消息"},
                "path": {"type": "string", "description": "仓库路径"},
                "add_all": {"type": "boolean", "description": "是否 add all", "default": False},
            },
            "required": ["message"],
        },
    },
    {
        "name": "code_graph_query",
        "description": "查询代码图谱：函数/类的依赖关系",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "要查询的符号名 (函数/类)"},
                "path": {"type": "string", "description": "项目路径"},
                "depth": {"type": "integer", "description": "查询深度", "default": 2},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "code_graph_impact",
        "description": "分析代码修改的影响范围",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file": {"type": "string", "description": "修改的文件路径"},
                "symbol": {"type": "string", "description": "修改的符号名 (可选)"},
                "path": {"type": "string", "description": "项目路径"},
            },
            "required": ["file"],
        },
    },
    {
        "name": "auto_test",
        "description": "自动测试闭环：运行测试并分析失败原因",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "测试文件或目录"},
                "pattern": {"type": "string", "description": "测试名称过滤模式"},
                "auto_fix": {"type": "boolean", "description": "是否自动修复", "default": False},
                "max_retries": {"type": "integer", "description": "最大重试次数", "default": 3},
            },
            "required": [],
        },
    },
    {
        "name": "rag_search",
        "description": "RAG 语义搜索：在代码库中搜索相关内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索查询"},
                "path": {"type": "string", "description": "搜索范围 (目录路径)"},
                "top_k": {"type": "integer", "description": "返回结果数量", "default": 5},
                "file_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "限制文件类型 (如 ['.py', '.ts'])",
                },
            },
            "required": ["query"],
        },
    },
]


# ─── Tool Execution ────────────────────────────────────────────────────────────

async def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具调用，返回结果"""
    import subprocess
    import os
    import glob as glob_mod
    import re

    try:
        if name == "file_read":
            path = arguments["path"]
            start_line = arguments.get("start_line")
            end_line = arguments.get("end_line")
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if start_line is not None or end_line is not None:
                start = (start_line or 1) - 1
                end = end_line or len(lines)
                lines = lines[start:end]
            content = "".join(lines)
            return {"content": [{"type": "text", "text": content}]}

        elif name == "file_write":
            path = arguments["path"]
            content = arguments["content"]
            create_dirs = arguments.get("create_dirs", True)
            if create_dirs:
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"content": [{"type": "text", "text": f"Written to {path}"}]}

        elif name == "file_edit":
            path = arguments["path"]
            old_text = arguments["old_text"]
            new_text = arguments["new_text"]
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return {"content": [{"type": "text", "text": f"Error: old_text not found in {path}"}], "isError": True}
            content = content.replace(old_text, new_text, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"content": [{"type": "text", "text": f"Edited {path}"}]}

        elif name == "grep_search":
            pattern = arguments["pattern"]
            path = arguments.get("path", ".")
            include = arguments.get("include", "")
            case_sensitive = arguments.get("case_sensitive", True)
            cmd = ["grep", "-rn"]
            if not case_sensitive:
                cmd.append("-i")
            if include:
                cmd.extend(["--include", include])
            cmd.extend([pattern, path])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            output = result.stdout or result.stderr or "No matches found"
            return {"content": [{"type": "text", "text": output[:50000]}]}

        elif name == "glob_search":
            pattern = arguments["pattern"]
            path = arguments.get("path", ".")
            full_pattern = os.path.join(path, pattern) if path else pattern
            matches = sorted(glob_mod.glob(full_pattern, recursive=True))
            result = "\n".join(matches[:500]) or "No files found"
            return {"content": [{"type": "text", "text": result}]}

        elif name == "list_directory":
            path = arguments["path"]
            recursive = arguments.get("recursive", False)
            max_depth = arguments.get("max_depth", 2)
            entries = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    depth = root.replace(path, "").count(os.sep)
                    if depth >= max_depth:
                        dirs.clear()
                        continue
                    indent = "  " * depth
                    entries.append(f"{indent}{os.path.basename(root)}/")
                    for f in sorted(files):
                        entries.append(f"{indent}  {f}")
            else:
                for item in sorted(os.listdir(path)):
                    full = os.path.join(path, item)
                    suffix = "/" if os.path.isdir(full) else ""
                    entries.append(f"{item}{suffix}")
            return {"content": [{"type": "text", "text": "\n".join(entries)}]}

        elif name == "bash_execute":
            command = arguments["command"]
            cwd = arguments.get("cwd")
            timeout = arguments.get("timeout", 120)
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                cwd=cwd, timeout=timeout
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            output += f"\n[exit code: {result.returncode}]"
            return {"content": [{"type": "text", "text": output.strip()}]}

        elif name == "git_status":
            path = arguments.get("path", ".")
            result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=path
            )
            return {"content": [{"type": "text", "text": result.stdout or "Clean working tree"}]}

        elif name == "git_diff":
            path = arguments.get("path", ".")
            cmd = ["git", "diff"]
            if arguments.get("staged"):
                cmd.append("--staged")
            if arguments.get("commit"):
                cmd.append(arguments["commit"])
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=path)
            return {"content": [{"type": "text", "text": result.stdout or "No diff"}]}

        elif name == "git_log":
            path = arguments.get("path", ".")
            count = arguments.get("count", 10)
            cmd = ["git", "log", f"-{count}"]
            if arguments.get("oneline", True):
                cmd.append("--oneline")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=path)
            return {"content": [{"type": "text", "text": result.stdout or "No commits"}]}

        elif name == "git_commit":
            path = arguments.get("path", ".")
            message = arguments["message"]
            if arguments.get("add_all"):
                subprocess.run(["git", "add", "-A"], cwd=path)
            result = subprocess.run(
                ["git", "commit", "-m", message], capture_output=True, text=True, cwd=path
            )
            output = result.stdout + result.stderr
            return {"content": [{"type": "text", "text": output.strip()}]}

        elif name == "code_graph_query":
            symbol = arguments["symbol"]
            path = arguments.get("path", ".")
            depth = arguments.get("depth", 2)
            # 简单实现：通过 grep 查找符号引用
            cmd = ["grep", "-rn", symbol, path, "--include=*.py"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            refs = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return {"content": [{"type": "text", "text": f"Symbol: {symbol}\nReferences ({len(refs)}):\n" + "\n".join(refs[:50])}]}

        elif name == "code_graph_impact":
            file = arguments["file"]
            path = arguments.get("path", ".")
            # 简单实现：查找导入该文件的模块
            basename = os.path.splitext(os.path.basename(file))[0]
            cmd = ["grep", "-rn", f"import.*{basename}", path, "--include=*.py"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            importers = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return {"content": [{"type": "text", "text": f"Impact of {file}:\nImported by ({len(importers)}):\n" + "\n".join(importers[:50])}]}

        elif name == "auto_test":
            path = arguments.get("path", ".")
            pattern = arguments.get("pattern", "")
            cmd = ["python", "-m", "pytest", path, "-v", "--tb=short"]
            if pattern:
                cmd.extend(["-k", pattern])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            output = result.stdout + "\n" + result.stderr
            return {"content": [{"type": "text", "text": output.strip()[:50000]}]}

        elif name == "rag_search":
            query = arguments["query"]
            path = arguments.get("path", ".")
            top_k = arguments.get("top_k", 5)
            # 简单实现：基于关键词搜索
            keywords = query.split()
            pattern = "|".join(keywords[:5])
            cmd = ["grep", "-rn", "-i", "-E", pattern, path, "--include=*.py", "--include=*.ts", "--include=*.md"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return {"content": [{"type": "text", "text": f"RAG results for '{query}' (top {top_k}):\n" + "\n".join(lines[:top_k])}]}

        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

    except subprocess.TimeoutExpired:
        return {"content": [{"type": "text", "text": f"Tool '{name}' timed out"}], "isError": True}
    except FileNotFoundError as e:
        return {"content": [{"type": "text", "text": f"File not found: {e}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Error in {name}: {type(e).__name__}: {e}"}], "isError": True}


# ─── MCP Server ────────────────────────────────────────────────────────────────

class MCPServer:
    """
    MCP (Model Context Protocol) 服务器
    
    通过 stdin/stdout 进行 JSON-RPC 2.0 通信，
    将 Agent 工具暴露给 IDE 使用。
    """

    SERVER_INFO = {
        "name": "agent-mcp-server",
        "version": "0.2.0",
    }

    CAPABILITIES = {
        "tools": {},
    }

    def __init__(self):
        self._running = False

    async def handle_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理单个 JSON-RPC 请求"""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        logger.debug(f"Received: method={method}, id={req_id}")

        # Notifications (no id) don't need a response
        if req_id is None:
            await self._handle_notification(method, params)
            return None

        try:
            result = await self._dispatch(method, params)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }
        except MethodNotFoundError as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": str(e)},
            }
        except InvalidParamsError as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": str(e)},
            }
        except ToolExecutionError as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }
        except Exception as e:
            logger.error(f"Internal error: {traceback.format_exc()}")
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            }

    async def _handle_notification(self, method: str, params: Dict[str, Any]):
        """处理通知（无需响应）"""
        if method == "notifications/initialized":
            logger.info("Client initialized")
        elif method == "notifications/cancelled":
            logger.info(f"Request cancelled: {params}")
        else:
            logger.debug(f"Unknown notification: {method}")

    async def _dispatch(self, method: str, params: Dict[str, Any]) -> Any:
        """路由请求到对应处理器"""
        if method == "initialize":
            return self._handle_initialize(params)
        elif method == "tools/list":
            return self._handle_tools_list(params)
        elif method == "tools/call":
            return await self._handle_tools_call(params)
        elif method == "ping":
            return {}
        else:
            raise MethodNotFoundError(f"Method not found: {method}")

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理 initialize 请求，返回服务器能力"""
        logger.info(f"Initialize from: {params.get('clientInfo', {})}")
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": self.CAPABILITIES,
            "serverInfo": self.SERVER_INFO,
        }

    def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有可用工具"""
        return {"tools": TOOLS}

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            raise InvalidParamsError("Missing 'name' in tools/call")

        # 检查工具是否存在
        valid_names = {t["name"] for t in TOOLS}
        if tool_name not in valid_names:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")

        logger.info(f"Calling tool: {tool_name}")
        result = await execute_tool(tool_name, arguments)
        return result

    async def run(self):
        """主运行循环：从 stdin 读取请求，写响应到 stdout"""
        self._running = True
        logger.info("MCP Server starting (stdio mode)")

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        while self._running:
            try:
                line = await reader.readline()
                if not line:
                    logger.info("EOF on stdin, shutting down")
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    request = json.loads(line_str)
                except json.JSONDecodeError as e:
                    error_resp = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"Parse error: {e}"},
                    }
                    self._write_response(error_resp)
                    continue

                response = await self.handle_request(request)
                if response is not None:
                    self._write_response(response)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                continue

        logger.info("MCP Server stopped")

    def _write_response(self, response: Dict[str, Any]):
        """将 JSON-RPC 响应写到 stdout"""
        data = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(data + "\n")
        sys.stdout.flush()

    def stop(self):
        """停止服务器"""
        self._running = False


# ─── Exceptions ────────────────────────────────────────────────────────────────

class MethodNotFoundError(Exception):
    pass


class InvalidParamsError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    """MCP Server 入口"""
    server = MCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
