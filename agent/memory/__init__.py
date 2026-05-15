"""
Memory Module - 会话管理和消息持久化

提供:
- 内存存储后端
- Redis 存储后端
- 会话管理器
- 消息历史管理
- LangChain 兼容的 ChatMessageHistory
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
from dataclasses import dataclass, field
import uuid

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
    messages_from_dict,
    messages_to_dict,
)
from langchain_core.chat_history import BaseChatMessageHistory

from agent.observability import get_logger, get_tracer, set_trace_context

logger = get_logger("memory")
tracer = get_tracer("memory")


@dataclass
class SessionMetadata:
    """会话元数据"""
    session_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title": self.title,
            "metadata": self.metadata,
            "message_count": self.message_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        return cls(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            title=data.get("title"),
            metadata=data.get("metadata", {}),
            message_count=data.get("message_count", 0),
        )


class BaseMemoryBackend(ABC):
    """内存存储后端抽象基类"""

    @abstractmethod
    def save_messages(self, session_id: str, messages: List[BaseMessage]) -> None:
        """保存消息列表"""
        pass

    @abstractmethod
    def load_messages(self, session_id: str) -> List[BaseMessage]:
        """加载消息列表"""
        pass

    @abstractmethod
    def add_message(self, session_id: str, message: BaseMessage) -> None:
        """添加单条消息"""
        pass

    @abstractmethod
    def clear_messages(self, session_id: str) -> None:
        """清除会话消息"""
        pass

    @abstractmethod
    def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """获取会话元数据"""
        pass

    @abstractmethod
    def save_session_metadata(self, metadata: SessionMetadata) -> None:
        """保存会话元数据"""
        pass

    @abstractmethod
    def list_sessions(self, limit: int = 100, offset: int = 0) -> List[SessionMetadata]:
        """列出所有会话"""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        pass

    @abstractmethod
    def session_exists(self, session_id: str) -> bool:
        """检查会话是否存在"""
        pass


class InMemoryBackend(BaseMemoryBackend):
    """内存存储后端 - 适用于开发和测试"""

    def __init__(self):
        self._messages: Dict[str, List[Dict[str, Any]]] = {}
        self._metadata: Dict[str, SessionMetadata] = {}

    @tracer.trace("memory.save_messages")
    def save_messages(self, session_id: str, messages: List[BaseMessage]) -> None:
        self._messages[session_id] = messages_to_dict(messages)
        self._update_metadata(session_id, len(messages))
        logger.debug(f"Saved {len(messages)} messages", session_id=session_id)

    @tracer.trace("memory.load_messages")
    def load_messages(self, session_id: str) -> List[BaseMessage]:
        message_dicts = self._messages.get(session_id, [])
        messages = messages_from_dict(message_dicts)
        logger.debug(f"Loaded {len(messages)} messages", session_id=session_id)
        return messages

    @tracer.trace("memory.add_message")
    def add_message(self, session_id: str, message: BaseMessage) -> None:
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(messages_to_dict([message])[0])
        self._update_metadata(session_id, len(self._messages[session_id]))
        logger.debug(
            f"Added message",
            session_id=session_id,
            message_type=message.__class__.__name__,
        )

    def clear_messages(self, session_id: str) -> None:
        if session_id in self._messages:
            self._messages[session_id] = []
            self._update_metadata(session_id, 0)
        logger.debug(f"Cleared messages", session_id=session_id)

    def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        return self._metadata.get(session_id)

    def save_session_metadata(self, metadata: SessionMetadata) -> None:
        self._metadata[metadata.session_id] = metadata

    def list_sessions(self, limit: int = 100, offset: int = 0) -> List[SessionMetadata]:
        sessions = sorted(
            self._metadata.values(),
            key=lambda x: x.updated_at,
            reverse=True,
        )
        return sessions[offset : offset + limit]

    def delete_session(self, session_id: str) -> bool:
        deleted = False
        if session_id in self._messages:
            del self._messages[session_id]
            deleted = True
        if session_id in self._metadata:
            del self._metadata[session_id]
            deleted = True
        logger.info(f"Deleted session", session_id=session_id, deleted=deleted)
        return deleted

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._metadata

    def _update_metadata(self, session_id: str, message_count: int) -> None:
        if session_id not in self._metadata:
            self._metadata[session_id] = SessionMetadata(session_id=session_id)
        self._metadata[session_id].updated_at = datetime.now(timezone.utc)
        self._metadata[session_id].message_count = message_count


class RedisBackend(BaseMemoryBackend):
    """Redis 存储后端 - 适用于生产环境"""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "agent:memory:",
        ttl: Optional[int] = None,  # 过期时间（秒），None 表示不过期
    ):
        try:
            import redis
        except ImportError:
            raise ImportError(
                "redis is required for Redis backend. "
                "Install it with: pip install redis"
            )

        self._client = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix
        self._ttl = ttl
        logger.info(f"Initialized Redis backend", redis_url=redis_url, prefix=prefix)

    def _messages_key(self, session_id: str) -> str:
        return f"{self._prefix}messages:{session_id}"

    def _metadata_key(self, session_id: str) -> str:
        return f"{self._prefix}metadata:{session_id}"

    def _sessions_key(self) -> str:
        return f"{self._prefix}sessions"

    @tracer.trace("redis.save_messages")
    def save_messages(self, session_id: str, messages: List[BaseMessage]) -> None:
        key = self._messages_key(session_id)
        data = json.dumps(messages_to_dict(messages))
        
        if self._ttl:
            self._client.setex(key, self._ttl, data)
        else:
            self._client.set(key, data)
        
        self._update_metadata(session_id, len(messages))
        logger.debug(f"Saved {len(messages)} messages to Redis", session_id=session_id)

    @tracer.trace("redis.load_messages")
    def load_messages(self, session_id: str) -> List[BaseMessage]:
        key = self._messages_key(session_id)
        data = self._client.get(key)
        
        if not data:
            return []
        
        message_dicts = json.loads(data)
        messages = messages_from_dict(message_dicts)
        logger.debug(f"Loaded {len(messages)} messages from Redis", session_id=session_id)
        return messages

    @tracer.trace("redis.add_message")
    def add_message(self, session_id: str, message: BaseMessage) -> None:
        messages = self.load_messages(session_id)
        messages.append(message)
        self.save_messages(session_id, messages)

    def clear_messages(self, session_id: str) -> None:
        key = self._messages_key(session_id)
        self._client.delete(key)
        self._update_metadata(session_id, 0)
        logger.debug(f"Cleared messages in Redis", session_id=session_id)

    def get_session_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        key = self._metadata_key(session_id)
        data = self._client.get(key)
        
        if not data:
            return None
        
        return SessionMetadata.from_dict(json.loads(data))

    def save_session_metadata(self, metadata: SessionMetadata) -> None:
        key = self._metadata_key(metadata.session_id)
        data = json.dumps(metadata.to_dict())
        
        if self._ttl:
            self._client.setex(key, self._ttl, data)
        else:
            self._client.set(key, data)
        
        # 添加到会话索引
        self._client.zadd(
            self._sessions_key(),
            {metadata.session_id: metadata.updated_at.timestamp()},
        )

    def list_sessions(self, limit: int = 100, offset: int = 0) -> List[SessionMetadata]:
        session_ids = self._client.zrevrange(
            self._sessions_key(),
            offset,
            offset + limit - 1,
        )
        
        sessions = []
        for session_id in session_ids:
            metadata = self.get_session_metadata(session_id)
            if metadata:
                sessions.append(metadata)
        
        return sessions

    def delete_session(self, session_id: str) -> bool:
        messages_key = self._messages_key(session_id)
        metadata_key = self._metadata_key(session_id)
        
        deleted = self._client.delete(messages_key, metadata_key)
        self._client.zrem(self._sessions_key(), session_id)
        
        logger.info(f"Deleted session from Redis", session_id=session_id)
        return deleted > 0

    def session_exists(self, session_id: str) -> bool:
        return self._client.exists(self._metadata_key(session_id)) > 0

    def _update_metadata(self, session_id: str, message_count: int) -> None:
        metadata = self.get_session_metadata(session_id)
        if not metadata:
            metadata = SessionMetadata(session_id=session_id)
        
        metadata.updated_at = datetime.now(timezone.utc)
        metadata.message_count = message_count
        self.save_session_metadata(metadata)


class AgentChatMessageHistory(BaseChatMessageHistory):
    """
    LangChain 兼容的聊天消息历史
    
    可直接用于 LangChain 的 RunnableWithMessageHistory
    """

    def __init__(
        self,
        session_id: str,
        backend: Optional[BaseMemoryBackend] = None,
    ):
        self.session_id = session_id
        self._backend = backend or InMemoryBackend()

    @property
    def messages(self) -> List[BaseMessage]:
        """获取所有消息"""
        return self._backend.load_messages(self.session_id)

    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        self._backend.add_message(self.session_id, message)

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """批量添加消息"""
        existing = self._backend.load_messages(self.session_id)
        self._backend.save_messages(self.session_id, existing + messages)

    def clear(self) -> None:
        """清除消息"""
        self._backend.clear_messages(self.session_id)


class SessionManager:
    """
    会话管理器
    
    提供完整的会话生命周期管理
    """

    def __init__(self, backend: Optional[BaseMemoryBackend] = None):
        self._backend = backend or InMemoryBackend()

    @tracer.trace("session.create")
    def create_session(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建新会话"""
        session_id = session_id or str(uuid.uuid4())
        
        session_metadata = SessionMetadata(
            session_id=session_id,
            title=title,
            metadata=metadata or {},
        )
        
        self._backend.save_session_metadata(session_metadata)
        
        # 设置追踪上下文
        set_trace_context(session_id=session_id)
        
        logger.info(f"Created session", session_id=session_id, title=title)
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionMetadata]:
        """获取会话元数据"""
        return self._backend.get_session_metadata(session_id)

    def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """更新会话"""
        existing = self._backend.get_session_metadata(session_id)
        if not existing:
            return False
        
        if title is not None:
            existing.title = title
        if metadata is not None:
            existing.metadata.update(metadata)
        
        existing.updated_at = datetime.now(timezone.utc)
        self._backend.save_session_metadata(existing)
        
        logger.info(f"Updated session", session_id=session_id)
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        return self._backend.delete_session(session_id)

    def list_sessions(self, limit: int = 100, offset: int = 0) -> List[SessionMetadata]:
        """列出会话"""
        return self._backend.list_sessions(limit=limit, offset=offset)

    def get_history(self, session_id: str) -> AgentChatMessageHistory:
        """获取会话的消息历史对象"""
        return AgentChatMessageHistory(session_id, self._backend)

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """获取会话消息"""
        return self._backend.load_messages(session_id)

    def add_message(self, session_id: str, message: BaseMessage) -> None:
        """添加消息到会话"""
        # 确保会话存在
        if not self._backend.session_exists(session_id):
            self.create_session(session_id)
        
        self._backend.add_message(session_id, message)

    def clear_messages(self, session_id: str) -> None:
        """清除会话消息"""
        self._backend.clear_messages(session_id)


# 便捷函数
def get_session_manager(
    backend: Optional[str] = None,
    **kwargs,
) -> SessionManager:
    """
    获取会话管理器
    
    Args:
        backend: 后端类型 ("memory" 或 "redis")
        **kwargs: 后端配置参数
        
    Returns:
        SessionManager 实例
    """
    if backend == "redis":
        memory_backend = RedisBackend(**kwargs)
    else:
        memory_backend = InMemoryBackend()
    
    return SessionManager(memory_backend)


# 全局默认会话管理器
default_session_manager = SessionManager()


__all__ = [
    # 数据类
    "SessionMetadata",
    # 后端
    "BaseMemoryBackend",
    "InMemoryBackend",
    "RedisBackend",
    # 历史
    "AgentChatMessageHistory",
    # 管理器
    "SessionManager",
    # 便捷函数
    "get_session_manager",
    # 全局实例
    "default_session_manager",
]
