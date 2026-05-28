"""
Team Collaboration Web Server (Pure Stdlib)

零依赖 WebSocket + HTTP 服务器
基于 asyncio + http.server 实现
"""

import asyncio
import hashlib
import base64
import json
import struct
import time
import uuid
import logging
from typing import Any, Dict, List, Optional, Set
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs

from agent.web.leader import LeaderAgent, TaskPlan, SubTask
from agent.web.executor import TeamExecutor, ExecutionEvent, EventType

logger = logging.getLogger(__name__)


# ============ WebSocket 协议实现 ============

WEBSOCKET_MAGIC = b"258EAFA5-E914-47DA-95CA-5AB9FC6B7393"


def compute_accept_key(key: str) -> str:
    """计算 WebSocket Accept Key"""
    sha1 = hashlib.sha1(key.encode() + WEBSOCKET_MAGIC).digest()
    return base64.b64encode(sha1).decode()


def encode_ws_frame(data: str, opcode: int = 0x1) -> bytes:
    """编码 WebSocket 文本帧"""
    payload = data.encode("utf-8")
    length = len(payload)

    frame = bytearray()
    frame.append(0x80 | opcode)  # FIN + opcode

    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack("!Q", length))

    frame.extend(payload)
    return bytes(frame)


def decode_ws_frame(data: bytes):
    """解码 WebSocket 帧 (返回 opcode, payload, 剩余数据)"""
    if len(data) < 2:
        return None, None, data

    first_byte = data[0]
    second_byte = data[1]
    opcode = first_byte & 0x0F
    masked = second_byte & 0x80
    payload_length = second_byte & 0x7F

    offset = 2

    if payload_length == 126:
        if len(data) < 4:
            return None, None, data
        payload_length = struct.unpack("!H", data[2:4])[0]
        offset = 4
    elif payload_length == 127:
        if len(data) < 10:
            return None, None, data
        payload_length = struct.unpack("!Q", data[2:10])[0]
        offset = 10

    if masked:
        if len(data) < offset + 4:
            return None, None, data
        mask_key = data[offset:offset + 4]
        offset += 4

    if len(data) < offset + payload_length:
        return None, None, data

    payload = data[offset:offset + payload_length]

    if masked:
        payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

    remaining = data[offset + payload_length:]
    return opcode, payload, remaining


# ============ WebSocket 连接 ============

class WebSocketConnection:
    """单个 WebSocket 连接"""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.is_open = True
        self._buffer = b""

    async def send(self, data: str):
        """发送文本消息"""
        if not self.is_open:
            return
        try:
            frame = encode_ws_frame(data)
            self.writer.write(frame)
            await self.writer.drain()
        except Exception:
            self.is_open = False

    async def send_json(self, obj: Any):
        """发送 JSON 消息"""
        await self.send(json.dumps(obj, ensure_ascii=False))

    async def receive(self) -> Optional[str]:
        """接收消息"""
        while self.is_open:
            try:
                chunk = await asyncio.wait_for(self.reader.read(8192), timeout=60)
                if not chunk:
                    self.is_open = False
                    return None
                self._buffer += chunk

                opcode, payload, self._buffer = decode_ws_frame(self._buffer)
                if opcode is None:
                    continue

                if opcode == 0x1:  # 文本帧
                    return payload.decode("utf-8")
                elif opcode == 0x8:  # 关闭帧
                    self.is_open = False
                    # 回复关闭帧
                    self.writer.write(encode_ws_frame("", opcode=0x8))
                    await self.writer.drain()
                    return None
                elif opcode == 0x9:  # Ping
                    self.writer.write(encode_ws_frame(payload.decode("utf-8") if payload else "", opcode=0xA))
                    await self.writer.drain()
                    continue
                elif opcode == 0xA:  # Pong
                    continue

            except asyncio.TimeoutError:
                # 发送 ping 保活
                try:
                    self.writer.write(encode_ws_frame("", opcode=0x9))
                    await self.writer.drain()
                except Exception:
                    self.is_open = False
                    return None
            except Exception:
                self.is_open = False
                return None

        return None

    def close(self):
        """关闭连接"""
        self.is_open = False
        try:
            self.writer.close()
        except Exception:
            pass


# ============ 连接管理器 ============

class ConnectionManager:
    """管理所有 WebSocket 连接"""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocketConnection]] = {}

    def add(self, session_id: str, conn: WebSocketConnection):
        if session_id not in self._connections:
            self._connections[session_id] = set()
        self._connections[session_id].add(conn)

    def remove(self, session_id: str, conn: WebSocketConnection):
        if session_id in self._connections:
            self._connections[session_id].discard(conn)
            if not self._connections[session_id]:
                del self._connections[session_id]

    async def broadcast(self, session_id: str, event: Dict[str, Any]):
        if session_id not in self._connections:
            return
        msg = json.dumps(event, ensure_ascii=False)
        dead = set()
        for conn in self._connections[session_id]:
            try:
                await conn.send(msg)
            except Exception:
                dead.add(conn)
        for conn in dead:
            self._connections[session_id].discard(conn)


# ============ 会话状态 ============

class SessionState:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = time.time()
        self.messages: List[Dict[str, Any]] = []
        self.current_plan: Optional[TaskPlan] = None
        self.execution_results: List[Dict[str, Any]] = []
        self.status: str = "idle"


# ============ 主服务器 ============

class TeamServer:
    """团队协作 Web 服务器"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080, llm=None, model_config=None):
        self.host = host
        self.port = port
        self.manager = ConnectionManager()
        self.sessions: Dict[str, SessionState] = {}
        self.leader = LeaderAgent(llm=llm)
        self.executor = TeamExecutor(llm=llm, model_config=model_config)

    async def start(self):
        """启动服务器"""
        server = await asyncio.start_server(
            self._handle_connection, self.host, self.port
        )
        print(f"🚀 Team Collaboration Server running at http://{self.host}:{self.port}")
        print(f"   Open in browser: http://localhost:{self.port}")
        async with server:
            await server.serve_forever()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理新连接"""
        try:
            # 读取 HTTP 请求
            request_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not request_line:
                writer.close()
                return

            request_str = request_line.decode("utf-8").strip()
            method, path, _ = request_str.split(" ", 2)

            # 读取头部
            headers = {}
            while True:
                line = await reader.readline()
                if line == b"\r\n" or line == b"\n" or not line:
                    break
                key, _, value = line.decode("utf-8").strip().partition(":")
                headers[key.strip().lower()] = value.strip()

            # 读取 body
            body = b""
            content_length = int(headers.get("content-length", 0))
            if content_length > 0:
                body = await reader.readexactly(content_length)

            # 路由
            parsed = urlparse(path)
            route = parsed.path

            # WebSocket 升级
            if headers.get("upgrade", "").lower() == "websocket":
                await self._handle_websocket_upgrade(reader, writer, headers, route)
                return

            # HTTP 路由
            await self._handle_http(method, route, headers, body, writer)

        except Exception as e:
            logger.error(f"Connection error: {e}")
            try:
                await self._send_response(writer, 500, {"error": str(e)})
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_http(self, method: str, path: str, headers: dict, body: bytes, writer):
        """处理 HTTP 请求"""

        if path == "/" or path == "/index.html":
            from agent.web.frontend import get_html
            html = get_html()
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: text/html; charset=utf-8\r\n"
                f"Content-Length: {len(html.encode('utf-8'))}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            )
            writer.write(response.encode("utf-8"))
            writer.write(html.encode("utf-8"))
            await writer.drain()
            return

        if path == "/api/health":
            await self._send_response(writer, 200, {"status": "healthy", "sessions": len(self.sessions)})
            return

        if path == "/api/sessions" and method == "POST":
            session_id = str(uuid.uuid4())[:8]
            self.sessions[session_id] = SessionState(session_id)
            await self._send_response(writer, 200, {"session_id": session_id, "status": "created"})
            return

        if path == "/api/sessions" and method == "GET":
            data = {
                "sessions": [
                    {"session_id": s.session_id, "status": s.status, "messages": len(s.messages)}
                    for s in self.sessions.values()
                ]
            }
            await self._send_response(writer, 200, data)
            return

        if path.startswith("/api/sessions/") and method == "GET":
            session_id = path.split("/")[-1]
            if session_id in self.sessions:
                state = self.sessions[session_id]
                await self._send_response(writer, 200, {
                    "session_id": state.session_id,
                    "status": state.status,
                    "messages": state.messages,
                })
            else:
                await self._send_response(writer, 404, {"error": "Session not found"})
            return

        if path == "/api/team/members":
            await self._send_response(writer, 200, {"members": self.executor.get_members_info()})
            return

        if path == "/api/workflows":
            await self._send_response(writer, 200, {
                "workflows": [
                    {"id": "standard", "name": "标准开发"},
                    {"id": "quick_fix", "name": "快速修复"},
                    {"id": "full_stack", "name": "全栈开发"},
                ]
            })
            return

        # 404
        await self._send_response(writer, 404, {"error": "Not found"})

    async def _send_response(self, writer, status: int, data: dict):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        status_text = {200: "OK", 201: "Created", 400: "Bad Request", 404: "Not Found", 500: "Internal Server Error"}
        response = (
            f"HTTP/1.1 {status} {status_text.get(status, 'OK')}\r\n"
            f"Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Access-Control-Allow-Origin: *\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        )
        writer.write(response.encode("utf-8"))
        writer.write(body)
        await writer.drain()

    async def _handle_websocket_upgrade(self, reader, writer, headers, path):
        """处理 WebSocket 升级"""
        ws_key = headers.get("sec-websocket-key", "")
        accept_key = compute_accept_key(ws_key)

        # 从路径提取 session_id: /ws/{session_id}
        parts = path.strip("/").split("/")
        session_id = parts[1] if len(parts) > 1 else str(uuid.uuid4())[:8]

        # 确保会话存在
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionState(session_id)

        # 发送升级响应
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n"
            "\r\n"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()

        # 创建 WebSocket 连接
        conn = WebSocketConnection(reader, writer)
        self.manager.add(session_id, conn)

        try:
            # 发送连接确认
            state = self.sessions[session_id]
            await conn.send_json({
                "type": "connected",
                "session_id": session_id,
                "status": state.status,
                "messages": state.messages,
                "plan": state.current_plan.to_dict() if state.current_plan else None,
            })

            # 消息循环
            while conn.is_open:
                msg_str = await conn.receive()
                if msg_str is None:
                    break

                try:
                    msg = json.loads(msg_str)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "message":
                    content = msg.get("content", "")
                    if content:
                        state.messages.append({
                            "role": "user",
                            "content": content,
                            "timestamp": time.time(),
                        })
                        # 触发工作流
                        asyncio.create_task(self._execute_workflow(session_id, content))

                elif msg.get("type") == "cancel":
                    state.status = "cancelled"
                    await self.manager.broadcast(session_id, {
                        "type": "cancelled",
                        "message": "执行已取消",
                    })

                elif msg.get("type") == "ping":
                    await conn.send_json({"type": "pong"})

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.manager.remove(session_id, conn)
            conn.close()

    async def _execute_workflow(self, session_id: str, user_message: str):
        """执行完整工作流"""
        state = self.sessions[session_id]

        try:
            # 阶段1: Leader 分解
            state.status = "planning"
            await self.manager.broadcast(session_id, {
                "type": "status",
                "status": "planning",
                "message": "🎯 Leader 正在分析任务...",
            })

            plan = await self.leader.decompose(user_message)
            state.current_plan = plan

            await self.manager.broadcast(session_id, {
                "type": "plan",
                "plan": plan.to_dict(),
                "message": f"任务已分解为 {len(plan.subtasks)} 个子任务",
            })

            state.messages.append({
                "role": "leader",
                "content": plan.summary,
                "timestamp": time.time(),
            })

            await asyncio.sleep(0.5)

            # 阶段2: 执行子任务
            state.status = "executing"
            await self.manager.broadcast(session_id, {
                "type": "status",
                "status": "executing",
                "message": "开始执行子任务...",
            })

            async for event in self.executor.execute(plan):
                if state.status == "cancelled":
                    break
                await self.manager.broadcast(session_id, event.to_dict())

                if event.type == EventType.TASK_COMPLETED:
                    state.execution_results.append(event.to_dict())

            # 阶段3: 完成
            if state.status != "cancelled":
                state.status = "completed"
                await self.manager.broadcast(session_id, {
                    "type": "status",
                    "status": "completed",
                    "message": "✅ 所有任务已完成",
                })

        except Exception as e:
            state.status = "error"
            logger.error(f"Workflow error: {e}", exc_info=True)
            await self.manager.broadcast(session_id, {
                "type": "error",
                "message": f"执行出错: {str(e)}",
            })


def run_team_server(host="0.0.0.0", port=8080, llm=None, model_config=None):
    """启动服务器"""
    server = TeamServer(host=host, port=port, llm=llm, model_config=model_config)
    asyncio.run(server.start())
