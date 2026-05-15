"""
对话持久化 - 会话保存与恢复

提供:
- SessionStore 类: 会话的保存、加载和列出
- 存储格式: JSON 文件 (在 ~/.agent/sessions/ 目录)
- 保存内容: messages, metadata, timestamp, model
- CLI 命令支持: /save, /resume, /sessions
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field, asdict


# ============ 数据模型 ============

@dataclass
class SessionMessage:
    """会话消息"""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp or datetime.now().isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMessage":
        """从字典创建"""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SessionData:
    """会话数据"""
    session_id: str
    messages: List[SessionMessage] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    model: str = ""
    created_at: str = ""
    updated_at: str = ""
    title: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "metadata": self.metadata,
            "model": self.model,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionData":
        """从字典创建"""
        messages = [
            SessionMessage.from_dict(msg) for msg in data.get("messages", [])
        ]
        return cls(
            session_id=data["session_id"],
            messages=messages,
            metadata=data.get("metadata", {}),
            model=data.get("model", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            title=data.get("title", ""),
        )


# ============ SessionStore ============

class SessionStore:
    """
    会话存储管理器
    
    负责会话的持久化存储、加载和管理。
    存储位置: ~/.agent/sessions/
    文件格式: JSON
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        初始化 SessionStore
        
        Args:
            storage_dir: 存储目录路径，默认为 ~/.agent/sessions/
        """
        if storage_dir:
            self._storage_dir = Path(storage_dir)
        else:
            self._storage_dir = Path.home() / ".agent" / "sessions"
        
        # 确保目录存在
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @property
    def storage_dir(self) -> Path:
        """获取存储目录"""
        return self._storage_dir

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        # 安全处理 session_id，避免路径遍历
        safe_id = session_id.replace("/", "_").replace("\\", "_").replace("..", "_")
        return self._storage_dir / f"{safe_id}.json"

    def save_session(
        self,
        session_id: str,
        messages: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        model: str = "",
        title: str = "",
    ) -> str:
        """
        保存会话
        
        Args:
            session_id: 会话 ID（为空则自动生成）
            messages: 消息列表
            metadata: 额外元数据
            model: 使用的模型名称
            title: 会话标题
            
        Returns:
            会话 ID
        """
        if not session_id:
            session_id = str(uuid.uuid4())[:8]
        
        now = datetime.now().isoformat()
        
        # 检查是否是更新现有会话
        existing = self.load_session(session_id)
        created_at = existing.created_at if existing else now
        
        # 构建消息列表
        session_messages = []
        if messages:
            for msg in messages:
                if isinstance(msg, SessionMessage):
                    session_messages.append(msg)
                elif isinstance(msg, dict):
                    session_messages.append(SessionMessage.from_dict(msg))
        
        # 自动生成标题
        if not title and session_messages:
            # 取第一条用户消息的前 50 个字符作为标题
            for msg in session_messages:
                if msg.role == "user" and msg.content:
                    title = msg.content[:50]
                    if len(msg.content) > 50:
                        title += "..."
                    break
        
        # 构建会话数据
        session = SessionData(
            session_id=session_id,
            messages=session_messages,
            metadata=metadata or {},
            model=model,
            created_at=created_at,
            updated_at=now,
            title=title,
        )
        
        # 写入文件
        session_path = self._get_session_path(session_id)
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)
        
        return session_id

    def load_session(self, session_id: str) -> Optional[SessionData]:
        """
        加载会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            SessionData 或 None（如果不存在）
        """
        session_path = self._get_session_path(session_id)
        
        if not session_path.exists():
            return None
        
        try:
            with open(session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionData.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # 文件损坏
            return None

    def list_sessions(
        self,
        limit: int = 20,
        sort_by: str = "updated_at",
    ) -> List[Dict[str, Any]]:
        """
        列出所有会话
        
        Args:
            limit: 最大返回数量
            sort_by: 排序字段 ("updated_at" 或 "created_at")
            
        Returns:
            会话摘要列表
        """
        sessions = []
        
        for filepath in self._storage_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                sessions.append({
                    "session_id": data.get("session_id", filepath.stem),
                    "title": data.get("title", "无标题"),
                    "model": data.get("model", ""),
                    "message_count": len(data.get("messages", [])),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                })
            except (json.JSONDecodeError, OSError):
                continue
        
        # 排序
        sessions.sort(key=lambda x: x.get(sort_by, ""), reverse=True)
        
        return sessions[:limit]

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否删除成功
        """
        session_path = self._get_session_path(session_id)
        
        if session_path.exists():
            session_path.unlink()
            return True
        return False

    def search_sessions(self, query: str) -> List[Dict[str, Any]]:
        """
        搜索会话（按标题和内容）
        
        Args:
            query: 搜索关键词
            
        Returns:
            匹配的会话摘要列表
        """
        results = []
        query_lower = query.lower()
        
        for filepath in self._storage_dir.glob("*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 搜索标题
                title = data.get("title", "")
                if query_lower in title.lower():
                    results.append({
                        "session_id": data.get("session_id", filepath.stem),
                        "title": title,
                        "match_type": "title",
                        "updated_at": data.get("updated_at", ""),
                    })
                    continue
                
                # 搜索消息内容
                messages = data.get("messages", [])
                for msg in messages:
                    content = msg.get("content", "")
                    if query_lower in content.lower():
                        results.append({
                            "session_id": data.get("session_id", filepath.stem),
                            "title": title,
                            "match_type": "content",
                            "updated_at": data.get("updated_at", ""),
                        })
                        break
                        
            except (json.JSONDecodeError, OSError):
                continue
        
        results.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return results


# ============ CLI 命令处理 ============

class SessionCommands:
    """
    会话相关的 CLI 命令处理器
    
    支持命令:
    - /save [name]: 保存当前会话
    - /resume [session_id]: 恢复会话
    - /sessions: 列出所有会话
    """

    def __init__(self, store: Optional[SessionStore] = None):
        self.store = store or SessionStore()

    def handle_command(
        self,
        command: str,
        current_messages: Optional[List[Dict[str, Any]]] = None,
        current_model: str = "",
    ) -> str:
        """
        处理 CLI 命令
        
        Args:
            command: 用户输入的命令字符串
            current_messages: 当前会话消息
            current_model: 当前使用的模型
            
        Returns:
            命令执行结果的文本输出
        """
        parts = command.strip().split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        
        if cmd == "/save":
            return self._handle_save(arg, current_messages, current_model)
        elif cmd == "/resume":
            return self._handle_resume(arg)
        elif cmd == "/sessions":
            return self._handle_list()
        else:
            return f"未知命令: {cmd}。支持的命令: /save, /resume, /sessions"

    def _handle_save(
        self,
        name: str,
        messages: Optional[List[Dict[str, Any]]],
        model: str,
    ) -> str:
        """处理 /save 命令"""
        if not messages:
            return "当前没有可保存的会话内容"
        
        session_id = name if name else str(uuid.uuid4())[:8]
        
        saved_id = self.store.save_session(
            session_id=session_id,
            messages=messages,
            model=model,
        )
        
        return f"会话已保存: {saved_id}"

    def _handle_resume(self, session_id: str) -> str:
        """处理 /resume 命令"""
        if not session_id:
            return "请指定要恢复的会话 ID。使用 /sessions 查看可用会话。"
        
        session = self.store.load_session(session_id)
        if not session:
            return f"未找到会话: {session_id}"
        
        msg_count = len(session.messages)
        return (
            f"已恢复会话: {session.title or session_id}\n"
            f"  模型: {session.model or '未知'}\n"
            f"  消息数: {msg_count}\n"
            f"  创建时间: {session.created_at}\n"
            f"  更新时间: {session.updated_at}"
        )

    def _handle_list(self) -> str:
        """处理 /sessions 命令"""
        sessions = self.store.list_sessions()
        
        if not sessions:
            return "暂无保存的会话"
        
        lines = ["保存的会话列表:", ""]
        
        for s in sessions:
            title = s["title"] or "无标题"
            msg_count = s["message_count"]
            updated = s["updated_at"][:16] if s["updated_at"] else "未知"
            lines.append(
                f"  [{s['session_id']}] {title} "
                f"({msg_count} 条消息, 更新于 {updated})"
            )
        
        lines.append("")
        lines.append("使用 /resume <session_id> 恢复会话")
        
        return "\n".join(lines)


# ============ 全局实例 ============

# 默认会话存储
default_store = SessionStore()

# 默认命令处理器
session_commands = SessionCommands(default_store)


__all__ = [
    "SessionMessage",
    "SessionData",
    "SessionStore",
    "SessionCommands",
    "default_store",
    "session_commands",
]
