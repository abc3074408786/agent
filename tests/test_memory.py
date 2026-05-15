"""测试 memory 模块"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage

from agent.memory import (
    InMemoryBackend,
    SessionManager,
    SessionMetadata,
    AgentChatMessageHistory,
)


class TestInMemoryBackend:
    def test_save_and_load(self):
        backend = InMemoryBackend()
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        backend.save_messages("s1", messages)
        loaded = backend.load_messages("s1")
        assert len(loaded) == 2
        assert loaded[0].content == "Hello"

    def test_add_message(self):
        backend = InMemoryBackend()
        backend.add_message("s1", HumanMessage(content="First"))
        backend.add_message("s1", AIMessage(content="Second"))
        loaded = backend.load_messages("s1")
        assert len(loaded) == 2

    def test_clear_messages(self):
        backend = InMemoryBackend()
        backend.add_message("s1", HumanMessage(content="Test"))
        backend.clear_messages("s1")
        assert backend.load_messages("s1") == []

    def test_session_metadata(self):
        backend = InMemoryBackend()
        meta = SessionMetadata(session_id="s1", title="Test Session")
        backend.save_session_metadata(meta)
        loaded = backend.get_session_metadata("s1")
        assert loaded is not None
        assert loaded.title == "Test Session"

    def test_delete_session(self):
        backend = InMemoryBackend()
        backend.add_message("s1", HumanMessage(content="Hi"))
        backend.save_session_metadata(SessionMetadata(session_id="s1"))
        assert backend.delete_session("s1") is True
        assert backend.session_exists("s1") is False

    def test_list_sessions(self):
        backend = InMemoryBackend()
        backend.save_session_metadata(SessionMetadata(session_id="s1"))
        backend.save_session_metadata(SessionMetadata(session_id="s2"))
        sessions = backend.list_sessions()
        assert len(sessions) == 2


class TestSessionManager:
    def test_create_session(self):
        manager = SessionManager()
        sid = manager.create_session(title="Test")
        assert sid is not None
        session = manager.get_session(sid)
        assert session.title == "Test"

    def test_add_and_get_messages(self):
        manager = SessionManager()
        sid = manager.create_session()
        manager.add_message(sid, HumanMessage(content="Hello"))
        manager.add_message(sid, AIMessage(content="Hi"))
        messages = manager.get_messages(sid)
        assert len(messages) == 2

    def test_clear_messages(self):
        manager = SessionManager()
        sid = manager.create_session()
        manager.add_message(sid, HumanMessage(content="Hi"))
        manager.clear_messages(sid)
        assert manager.get_messages(sid) == []

    def test_delete_session(self):
        manager = SessionManager()
        sid = manager.create_session()
        assert manager.delete_session(sid) is True
        assert manager.get_session(sid) is None

    def test_list_sessions(self):
        manager = SessionManager()
        manager.create_session(title="A")
        manager.create_session(title="B")
        sessions = manager.list_sessions()
        assert len(sessions) == 2

    def test_get_history(self):
        manager = SessionManager()
        sid = manager.create_session()
        history = manager.get_history(sid)
        assert isinstance(history, AgentChatMessageHistory)
        history.add_message(HumanMessage(content="Test"))
        assert len(history.messages) == 1
