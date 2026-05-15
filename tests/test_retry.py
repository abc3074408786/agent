"""测试 retry 模块 (断路器)"""
import pytest
import asyncio
from agent.retry import (
    RetryConfig,
    RetryExecutor,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpen,
    ErrorCategory,
    categorize_error,
    is_retryable,
    with_retry,
    with_timeout,
)


class TestErrorCategorization:
    def test_rate_limited(self):
        assert categorize_error(Exception("429 rate limit")) == ErrorCategory.RATE_LIMITED

    def test_authentication(self):
        assert categorize_error(Exception("401 unauthorized")) == ErrorCategory.AUTHENTICATION

    def test_server_error(self):
        assert categorize_error(Exception("500 internal")) == ErrorCategory.SERVER_ERROR

    def test_timeout(self):
        assert categorize_error(TimeoutError("timed out")) == ErrorCategory.TRANSIENT

    def test_retryable(self):
        assert is_retryable(Exception("429 rate limit"))
        assert is_retryable(Exception("500 error"))
        assert not is_retryable(Exception("401 unauthorized"))


class TestRetryConfig:
    def test_delay_calculation(self):
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)
        assert config.get_delay(0) == 1.0
        assert config.get_delay(1) == 2.0
        assert config.get_delay(2) == 4.0

    def test_max_delay(self):
        config = RetryConfig(initial_delay=1.0, max_delay=5.0, jitter=False)
        assert config.get_delay(10) == 5.0

    def test_jitter_adds_randomness(self):
        config = RetryConfig(initial_delay=1.0, jitter=True)
        delays = [config.get_delay(2) for _ in range(10)]
        assert len(set(delays)) > 1


class TestRetryExecutor:
    @pytest.mark.asyncio
    async def test_succeeds_immediately(self):
        executor = RetryExecutor(RetryConfig(max_retries=3))
        result = await executor.execute(lambda: "success")
        assert result == "success"
        assert executor.total_attempts == 0

    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        call_count = 0

        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("500 server error")
            return "ok"

        config = RetryConfig(max_retries=5, initial_delay=0.01)
        executor = RetryExecutor(config)
        result = await executor.execute(failing_then_success)
        assert result == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self):
        config = RetryConfig(max_retries=2, initial_delay=0.01)
        executor = RetryExecutor(config)

        with pytest.raises(Exception, match="always fails"):
            await executor.execute(
                lambda: (_ for _ in ()).throw(Exception("always fails 500"))
            )


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state_passes(self):
        cb = CircuitBreaker("test")
        result = await cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=100)
        cb = CircuitBreaker("test", config)

        for _ in range(2):
            try:
                await cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self):
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=100)
        cb = CircuitBreaker("test", config)

        try:
            await cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
        except Exception:
            pass

        with pytest.raises(CircuitBreakerOpen):
            await cb.call(lambda: "should not execute")

    def test_reset(self):
        cb = CircuitBreaker("test")
        cb._failure_count = 10
        cb._state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0


class TestWithTimeout:
    @pytest.mark.asyncio
    async def test_completes_in_time(self):
        @with_timeout(1.0)
        async def fast():
            return "done"

        result = await fast()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        @with_timeout(0.05)
        async def slow():
            await asyncio.sleep(1.0)
            return "never"

        with pytest.raises(TimeoutError):
            await slow()
