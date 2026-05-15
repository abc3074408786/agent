"""测试 algorithms/advanced_retry.py"""
import pytest
from agent.algorithms.advanced_retry import (
    calculate_backoff_delay,
    calculate_persistent_delay,
    parse_retry_after_header,
    parse_context_overflow,
    is_overloaded_error,
    is_rate_limited,
    BASE_DELAY_MS,
    MAX_529_RETRIES,
)


class TestCalculateBackoffDelay:
    def test_first_attempt(self):
        delay = calculate_backoff_delay(1, jitter_factor=0)
        assert delay == BASE_DELAY_MS

    def test_exponential_growth(self):
        d1 = calculate_backoff_delay(1, jitter_factor=0)
        d2 = calculate_backoff_delay(2, jitter_factor=0)
        d3 = calculate_backoff_delay(3, jitter_factor=0)
        assert d2 == d1 * 2
        assert d3 == d1 * 4

    def test_max_cap(self):
        delay = calculate_backoff_delay(100, max_delay_ms=32000, jitter_factor=0)
        assert delay == 32000

    def test_jitter_adds_randomness(self):
        delays = [calculate_backoff_delay(3, jitter_factor=0.25) for _ in range(10)]
        # 有抖动时，延迟应该不完全相同
        assert len(set(delays)) > 1


class TestCalculatePersistentDelay:
    def test_grows_exponentially(self):
        import time
        start = time.time()
        d1 = calculate_persistent_delay(1, start)
        d2 = calculate_persistent_delay(2, start)
        assert d2 > d1

    def test_capped_at_5min(self):
        import time
        start = time.time()
        delay = calculate_persistent_delay(20, start)
        assert delay <= 5 * 60 * 1000


class TestParseRetryAfterHeader:
    def test_parses_seconds(self):
        error = Exception("retry-after: 30")
        result = parse_retry_after_header(error)
        assert result == 30000  # 30s in ms

    def test_no_header(self):
        error = Exception("some random error")
        result = parse_retry_after_header(error)
        assert result is None


class TestParseContextOverflow:
    def test_parses_overflow(self):
        error = Exception("input tokens: 150000, context limit: 128000")
        result = parse_context_overflow(error)
        assert result is not None
        assert result["input_tokens"] == 150000
        assert result["context_limit"] == 128000

    def test_no_overflow(self):
        error = Exception("something else went wrong")
        result = parse_context_overflow(error)
        assert result is None


class TestErrorClassification:
    def test_is_overloaded(self):
        assert is_overloaded_error(Exception("529 overloaded"))
        assert is_overloaded_error(Exception("API overloaded"))
        assert not is_overloaded_error(Exception("404 not found"))

    def test_is_rate_limited(self):
        assert is_rate_limited(Exception("429 too many requests"))
        assert not is_rate_limited(Exception("500 server error"))
