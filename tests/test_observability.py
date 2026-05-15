"""测试 observability 模块"""
import pytest
from agent.observability import (
    AgentLogger,
    Tracer,
    Span,
    get_trace_id,
    get_span_id,
    set_trace_context,
    generate_trace_id,
    generate_span_id,
)


class TestTraceContext:
    def test_generate_trace_id(self):
        tid = generate_trace_id()
        assert len(tid) == 36  # UUID format

    def test_generate_span_id(self):
        sid = generate_span_id()
        assert len(sid) == 16

    def test_set_and_get(self):
        set_trace_context(trace_id="test-trace", session_id="test-session")
        assert get_trace_id() == "test-trace"


class TestSpan:
    def test_span_context_manager(self):
        span = Span(name="test_span")
        with span:
            span.set_attribute("key", "value")
        assert span.status == "OK"
        assert span.end_time is not None
        assert span.attributes["key"] == "value"

    def test_span_error(self):
        span = Span(name="error_span")
        try:
            with span:
                raise ValueError("test error")
        except ValueError:
            pass
        assert span.status == "ERROR"

    def test_span_add_event(self):
        span = Span(name="event_span")
        span.add_event("checkpoint", {"step": 1})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"


class TestTracer:
    def test_trace_decorator_sync(self):
        tracer = Tracer(service_name="test")

        @tracer.trace("my_func")
        def my_func(x):
            return x * 2

        result = my_func(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_trace_decorator_async(self):
        tracer = Tracer(service_name="test")

        @tracer.trace("my_async")
        async def my_async(x):
            return x + 1

        result = await my_async(5)
        assert result == 6


class TestAgentLogger:
    def test_create_logger(self):
        logger = AgentLogger(name="test", json_output=False)
        # Should not raise
        logger.info("test message", key="value")
        logger.error("error message")
        logger.warning("warning")
