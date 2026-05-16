"""
会话管理集成测试

测试 Memory 模块的完整生命周期:
- 创建 → 添加消息 → 获取 → 删除
- 持久化和重新加载
- 多个会话互不干扰
"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from agent.memory import (
    InMemoryBackend,
    SessionManager,
    SessionMetadata,
    AgentChatMessageHistory,
)


class TestSessionLifecycle:
    """创建 → 添加消息 → 获取 → 删除"""

    def test_session_lifecycle(self):
        """完整的会话生命周期"""
        backend = InMemoryBackend()
        manager = SessionManager(backend)

        # 创建会话
        session_id = manager.create_session(title="Test Session")
        assert session_id is not None

        # 验证会话存在
        session = manager.get_session(session_id)
        assert session is not None
        assert session.title == "Test Session"

        # 添加消息
        manager.add_message(session_id, HumanMessage(content="Hello!"))
        manager.add_message(session_id, AIMessage(content="Hi there!"))

        # 获取消息
        messages = manager.get_messages(session_id)
        assert len(messages) == 2
        assert messages[0].content == "Hello!"
        assert messages[1].content == "Hi there!"

        # 验证消息计数
        session = manager.get_session(session_id)
        assert session.message_count == 2

        # 删除会话
        deleted = manager.delete_session(session_id)
        assert deleted is True

        # 验证已删除
        session = manager.get_session(session_id)
        assert session is None

    def test_session_clear_messages(self):
        """清除消息不删除会话"""
        backend = InMemoryBackend()
        manager = SessionManager(backend)

        session_id = manager.create_session(title="Clear Test")
        manager.add_message(session_id, HumanMessage(content="msg1"))
        manager.add_message(session_id, HumanMessage(content="msg2"))

        # 清除消息
        manager.clear_messages(session_id)

        # 会话仍存在
        session = manager.get_session(session_id)
        assert session is not None
        assert session.title == "Clear Test"

        # 但消息为空
        messages = manager.get_messages(session_id)
        assert len(messages) == 0

    def test_session_update(self):
        """更新会话元数据"""
        backend = InMemoryBackend()
        manager = SessionManager(backend)

        session_id = manager.create_session(title="Original")
        updated = manager.update_session(session_id, title="Updated Title")
        assert updated is True

        session = manager.get_session(session_id)
        assert session.title == "Updated Title"


class TestSessionPersistence:
    """创建 → 保存 → 重新加载 → 验证消息还在"""

    def test_session_persistence(self):
        """使用同一个 backend 实例模拟持久化"""
        # 共享的 backend 模拟持久化存储
        shared_backend = InMemoryBackend()

        # 第一个 manager 创建和填充数据
        manager1 = SessionManager(shared_backend)
        session_id = manager1.create_session(title="Persistent Session")
        manager1.add_message(session_id, SystemMessage(content="You are helpful."))
        manager1.add_message(session_id, HumanMessage(content="What is AI?"))
        manager1.add_message(session_id, AIMessage(content="AI is artificial intelligence."))

        # 第二个 manager 使用同一个 backend（模拟重新加载）
        manager2 = SessionManager(shared_backend)

        # 验证消息仍然存在
        messages = manager2.get_messages(session_id)
        assert len(messages) == 3
        assert messages[0].content == "You are helpful."
        assert messages[1].content == "What is AI?"
        assert messages[2].content == "AI is artificial intelligence."

        # 验证元数据
        session = manager2.get_session(session_id)
        assert session is not None
        assert session.title == "Persistent Session"

    def test_chat_message_history_interface(self):
        """通过 AgentChatMessageHistory 接口操作"""
        backend = InMemoryBackend()
        session_id = "test-history-session"

        # 创建 history
        history = AgentChatMessageHistory(session_id, backend)

        # 添加消息
        history.add_message(HumanMessage(content="Hello"))
        history.add_message(AIMessage(content="World"))

        # 通过 messages 属性获取
        msgs = history.messages
        assert len(msgs) == 2
        assert msgs[0].content == "Hello"
        assert msgs[1].content == "World"

        # 清除
        history.clear()
        assert len(history.messages) == 0


class TestMultipleSessions:
    """多个会话互不干扰"""

    def test_multiple_sessions(self):
        """不同会话的消息完全隔离"""
        backend = InMemoryBackend()
        manager = SessionManager(backend)

        # 创建两个会话
        session_a = manager.create_session(title="Session A")
        session_b = manager.create_session(title="Session B")

        # 向会话 A 添加消息
        manager.add_message(session_a, HumanMessage(content="Message for A"))
        manager.add_message(session_a, AIMessage(content="Reply in A"))

        # 向会话 B 添加不同的消息
        manager.add_message(session_b, HumanMessage(content="Message for B"))
        manager.add_message(session_b, AIMessage(content="Reply in B"))
        manager.add_message(session_b, HumanMessage(content="Another msg for B"))

        # 验证隔离
        msgs_a = manager.get_messages(session_a)
        msgs_b = manager.get_messages(session_b)

        assert len(msgs_a) == 2
        assert len(msgs_b) == 3

        assert msgs_a[0].content == "Message for A"
        assert msgs_b[0].content == "Message for B"

        # 删除 A 不影响 B
        manager.delete_session(session_a)
        msgs_b_after = manager.get_messages(session_b)
        assert len(msgs_b_after) == 3

    def test_list_sessions(self):
        """列出所有会话"""
        backend = InMemoryBackend()
        manager = SessionManager(backend)

        ids = []
        for i in range(5):
            sid = manager.create_session(title=f"Session {i}")
            ids.append(sid)

        sessions = manager.list_sessions()
        assert len(sessions) == 5

        # 验证分页
        page1 = manager.list_sessions(limit=2, offset=0)
        assert len(page1) == 2

        page2 = manager.list_sessions(limit=2, offset=2)
        assert len(page2) == 2
