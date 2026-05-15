"""测试 algorithms/token_estimator.py"""
import pytest
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

from agent.algorithms.token_estimator import (
    rough_token_count,
    rough_token_count_for_file,
    bytes_per_token_for_file_type,
    estimate_message_tokens,
    estimate_messages_tokens,
    parse_token_budget,
    HybridTokenEstimator,
    FILE_TYPE_BYTES_PER_TOKEN,
    DEFAULT_BYTES_PER_TOKEN,
)


class TestRoughTokenCount:
    def test_empty_string(self):
        assert rough_token_count("") == 0

    def test_english_text(self):
        text = "Hello world this is a test"
        tokens = rough_token_count(text)
        assert 5 <= tokens <= 10  # ~26 chars / 4 ≈ 6-7

    def test_chinese_text(self):
        text = "你好世界"
        tokens = rough_token_count(text)
        # 4 中文字符 / 1.5 ≈ 2-3
        assert 2 <= tokens <= 4

    def test_mixed_text(self):
        text = "Hello 你好世界 world"
        tokens = rough_token_count(text)
        assert tokens > 0

    def test_long_text(self):
        text = "a" * 4000
        tokens = rough_token_count(text)
        assert 900 <= tokens <= 1100  # 4000/4 = 1000

    def test_custom_bytes_per_token(self):
        text = '{"key": "value"}'
        tokens_json = rough_token_count(text, bytes_per_token=2.0)
        tokens_code = rough_token_count(text, bytes_per_token=4.0)
        assert tokens_json > tokens_code  # JSON 估算更多 token


class TestBytesPerTokenForFileType:
    def test_json_files(self):
        assert bytes_per_token_for_file_type("json") == 2.0
        assert bytes_per_token_for_file_type("jsonl") == 2.0

    def test_code_files(self):
        assert bytes_per_token_for_file_type("py") == 3.5
        assert bytes_per_token_for_file_type("ts") == 3.5

    def test_unknown_extension(self):
        assert bytes_per_token_for_file_type("xyz") == DEFAULT_BYTES_PER_TOKEN

    def test_leading_dot(self):
        assert bytes_per_token_for_file_type(".json") == 2.0


class TestRoughTokenCountForFile:
    def test_json_file(self):
        content = '{"users": [{"name": "Alice"}, {"name": "Bob"}]}'
        tokens = rough_token_count_for_file(content, "data.json")
        # JSON 用 bytes_per_token=2, 所以 token 数更多
        tokens_generic = rough_token_count(content)
        assert tokens > tokens_generic

    def test_python_file(self):
        content = "def hello():\n    print('world')\n"
        tokens = rough_token_count_for_file(content, "main.py")
        assert tokens > 0

    def test_minified_js(self):
        content = "var a=1;var b=2;function c(){return a+b}"
        tokens = rough_token_count_for_file(content, "app.min.js")
        assert tokens > 0


class TestEstimateMessageTokens:
    def test_simple_message(self):
        msg = HumanMessage(content="Hello")
        tokens = estimate_message_tokens(msg)
        assert tokens >= 5  # overhead + content

    def test_empty_message(self):
        msg = HumanMessage(content="")
        tokens = estimate_message_tokens(msg)
        assert tokens >= 4  # at least overhead

    def test_tool_message(self):
        msg = ToolMessage(content="Result: 42", tool_call_id="call_123")
        tokens = estimate_message_tokens(msg)
        assert tokens > estimate_message_tokens(HumanMessage(content="Result: 42"))

    def test_ai_message_with_tool_calls(self):
        msg = AIMessage(
            content="",
            tool_calls=[{"name": "calculator", "args": {"expr": "2+2"}, "id": "c1"}]
        )
        tokens = estimate_message_tokens(msg)
        assert tokens > 10  # overhead + tool call


class TestEstimateMessagesTokens:
    def test_single_message(self):
        messages = [HumanMessage(content="Hi")]
        total = estimate_messages_tokens(messages)
        assert total > estimate_message_tokens(messages[0])  # includes conversation overhead

    def test_multiple_messages(self, sample_messages):
        total = estimate_messages_tokens(sample_messages)
        individual_sum = sum(estimate_message_tokens(m) for m in sample_messages)
        assert total == individual_sum + 3  # +3 conversation overhead


class TestParseTokenBudget:
    def test_shorthand_start(self):
        assert parse_token_budget("+500k") == 500_000
        assert parse_token_budget("+2m") == 2_000_000
        assert parse_token_budget("+1.5m") == 1_500_000

    def test_shorthand_end(self):
        assert parse_token_budget("Fix the bug +500k") == 500_000
        assert parse_token_budget("Implement feature +1m.") == 1_000_000

    def test_verbose(self):
        assert parse_token_budget("use 500k tokens") == 500_000
        assert parse_token_budget("spend 2m tokens") == 2_000_000

    def test_no_budget(self):
        assert parse_token_budget("just fix the bug") is None
        assert parse_token_budget("hello world") is None

    def test_case_insensitive(self):
        assert parse_token_budget("+500K") == 500_000
        assert parse_token_budget("use 2M TOKENS") == 2_000_000


class TestHybridTokenEstimator:
    def test_basic_estimation(self, sample_messages):
        estimator = HybridTokenEstimator(context_window=100000)
        tokens = estimator.estimate_current_tokens(sample_messages)
        assert tokens > 0

    def test_with_usage_update(self, sample_messages):
        estimator = HybridTokenEstimator(context_window=100000)
        
        # 模拟 API 返回
        estimator.update_usage(
            {"input_tokens": 100, "output_tokens": 50},
            message_index=2,  # 到第3条消息
        )
        
        tokens = estimator.estimate_current_tokens(sample_messages)
        # 应该是 API 的 150 + 剩余消息的估算
        assert tokens >= 150

    def test_usage_ratio(self, sample_messages):
        estimator = HybridTokenEstimator(context_window=1000)
        ratio = estimator.get_usage_ratio(sample_messages)
        assert 0 < ratio < 1

    def test_should_compact(self, long_messages):
        estimator = HybridTokenEstimator(context_window=500)
        assert estimator.should_compact(long_messages, buffer_tokens=100)

    def test_warning_state(self):
        estimator = HybridTokenEstimator(context_window=100)
        messages = [HumanMessage(content="x" * 400)]  # ~100 tokens
        state = estimator.get_warning_state(messages, warning_buffer=50)
        assert state in ("warning", "critical")
