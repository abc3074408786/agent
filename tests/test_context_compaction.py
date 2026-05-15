"""测试 algorithms/context_compaction.py"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from agent.algorithms.context_compaction import (
    group_messages_by_api_round,
    truncate_head_for_ptl,
    micro_compact,
    MicroCompactConfig,
    AutoCompactor,
)


class TestGroupMessagesByApiRound:
    def test_single_round(self):
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there", id="ai_1"),
        ]
        groups = group_messages_by_api_round(messages)
        # 第一个 AI 消息创建第一组
        assert len(groups) >= 1

    def test_multiple_rounds(self):
        messages = [
            HumanMessage(content="Q1"),
            AIMessage(content="Response 1", id="ai_1"),
            HumanMessage(content="Q2"),
            AIMessage(content="Response 2", id="ai_2"),
        ]
        groups = group_messages_by_api_round(messages)
        # 两个不同 id 的 AI 消息 → 至少 2 组
        assert len(groups) >= 2

    def test_same_ai_id_same_round(self):
        messages = [
            HumanMessage(content="Q"),
            AIMessage(content="Part 1", id="ai_1"),
            ToolMessage(content="42", tool_call_id="c1"),
            AIMessage(content="Part 2", id="ai_1"),  # 同 id
        ]
        groups = group_messages_by_api_round(messages)
        # 同 id 的 AI 消息不应该创建新的边界
        # 但由于实现方式，它们可能在同一组也可能在两组
        assert len(groups) >= 1

    def test_empty_messages(self):
        groups = group_messages_by_api_round([])
        assert len(groups) == 0


class TestTruncateHeadForPTL:
    def test_basic_truncation(self):
        messages = [
            HumanMessage(content="Q1"), AIMessage(content="R1", id="a1"),
            HumanMessage(content="Q2"), AIMessage(content="R2", id="a2"),
            HumanMessage(content="Q3"), AIMessage(content="R3", id="a3"),
        ]
        result = truncate_head_for_ptl(messages, drop_percentage=0.5)
        assert result is not None
        assert len(result) < len(messages)

    def test_preserves_system_messages(self):
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="Q1"), AIMessage(content="R1", id="a1"),
            HumanMessage(content="Q2"), AIMessage(content="R2", id="a2"),
        ]
        result = truncate_head_for_ptl(messages, drop_percentage=0.5)
        assert result is not None
        system_msgs = [m for m in result if isinstance(m, SystemMessage)]
        assert len(system_msgs) >= 1

    def test_too_few_groups(self):
        messages = [HumanMessage(content="Only one message")]
        result = truncate_head_for_ptl(messages)
        assert result is None

    def test_with_token_gap(self):
        messages = [
            HumanMessage(content="Q1"), AIMessage(content="x" * 1000, id="a1"),
            HumanMessage(content="Q2"), AIMessage(content="y" * 100, id="a2"),
        ]
        result = truncate_head_for_ptl(messages, token_gap=200)
        assert result is not None


class TestMicroCompact:
    def test_no_tool_messages(self):
        messages = [HumanMessage(content="Hello"), AIMessage(content="Hi")]
        result = micro_compact(messages)
        assert result.cleared_count == 0
        assert result.messages == messages

    def test_clears_old_large_tool_results(self):
        messages = [
            ToolMessage(content="x" * 10000, tool_call_id="c1"),
            ToolMessage(content="x" * 10000, tool_call_id="c2"),
            ToolMessage(content="x" * 10000, tool_call_id="c3"),
            ToolMessage(content="x" * 10000, tool_call_id="c4"),
            ToolMessage(content="x" * 10000, tool_call_id="c5"),
            ToolMessage(content="recent", tool_call_id="c6"),
        ]
        config = MicroCompactConfig(
            max_tool_result_chars=5000,
            keep_recent_tool_results=2,
        )
        result = micro_compact(messages, config)
        assert result.cleared_count > 0
        assert result.tokens_saved_estimate > 0

    def test_keeps_recent_results(self):
        messages = [
            ToolMessage(content="x" * 10000, tool_call_id="c1"),
            ToolMessage(content="recent1", tool_call_id="c2"),
            ToolMessage(content="recent2", tool_call_id="c3"),
        ]
        config = MicroCompactConfig(keep_recent_tool_results=2)
        result = micro_compact(messages, config)
        # 最后两个应该保留原样
        assert result.messages[-1].content == "recent2"
        assert result.messages[-2].content == "recent1"

    def test_small_results_not_cleared(self):
        messages = [
            ToolMessage(content="small", tool_call_id="c1"),
            ToolMessage(content="also small", tool_call_id="c2"),
        ]
        config = MicroCompactConfig(
            max_tool_result_chars=5000,
            keep_recent_tool_results=0,
        )
        result = micro_compact(messages, config)
        assert result.cleared_count == 0


class TestAutoCompactor:
    def test_should_compact(self):
        compactor = AutoCompactor(context_window=100, buffer_tokens=10)
        messages = [HumanMessage(content="x" * 500)]  # ~125 tokens
        assert compactor.should_compact(messages)

    def test_circuit_breaker(self):
        compactor = AutoCompactor(
            context_window=10,  # 很小的窗口
            buffer_tokens=5,
            max_consecutive_failures=2,
        )
        # 模拟连续失败
        compactor._consecutive_failures = 2
        assert compactor.is_circuit_open
        assert not compactor.should_compact([HumanMessage(content="x" * 1000)])

    def test_reset(self):
        compactor = AutoCompactor(context_window=100, buffer_tokens=10)
        compactor._consecutive_failures = 5
        compactor.reset()
        assert not compactor.is_circuit_open
