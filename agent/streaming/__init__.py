"""
Streaming Engine - 流式处理引擎

参考 Claude Code 的 AsyncGenerator 模式:
- LLM 流式响应处理
- SSE 事件流生成
- 流式工具执行
- Token 计数追踪
- 中断/恢复支持
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, BaseMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk

from agent.observability import get_logger, get_tracer

logger = get_logger("streaming")
tracer = get_tracer("streaming")


# ============ 流事件类型 ============

class StreamEventType(str, Enum):
    """流事件类型"""
    # 消息事件
    MESSAGE_START = "message_start"
    CONTENT_DELTA = "content_delta"
    CONTENT_COMPLETE = "content_complete"
    MESSAGE_END = "message_end"
    # 工具事件
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    TOOL_RESULT = "tool_result"
    # 思考事件
    THINKING_START = "thinking_start"
    THINKING_DELTA = "thinking_delta"
    THINKING_END = "thinking_end"
    # 控制事件
    ERROR = "error"
    PING = "ping"
    DONE = "done"
    INTERRUPTED = "interrupted"
    # Token 统计
    USAGE_UPDATE = "usage_update"


@dataclass
class StreamEvent:
    """流事件"""
    type: StreamEventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int = 0
    trace_id: Optional[str] = None

    def to_sse(self) -> str:
        """转为 SSE 格式"""
        payload = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
        }
        if self.trace_id:
            payload["trace_id"] = self.trace_id
        return f"event: {self.type.value}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "trace_id": self.trace_id,
        }


@dataclass
class TokenUsage:
    """Token 用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    # 详细统计
    thinking_tokens: int = 0
    tool_use_tokens: int = 0
    cached_tokens: int = 0
    # 成本追踪
    estimated_cost_usd: float = 0.0

    def accumulate(self, other: "TokenUsage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.thinking_tokens += other.thinking_tokens
        self.tool_use_tokens += other.tool_use_tokens
        self.cached_tokens += other.cached_tokens
        self.estimated_cost_usd += other.estimated_cost_usd

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "thinking_tokens": self.thinking_tokens,
            "tool_use_tokens": self.tool_use_tokens,
            "cached_tokens": self.cached_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


# ============ 流式处理器 ============

class StreamProcessor(ABC):
    """流处理器抽象基类"""

    @abstractmethod
    async def process(
        self, event: StreamEvent
    ) -> Optional[StreamEvent]:
        """处理事件，返回转换后的事件或 None (过滤)"""
        pass


class TokenCounterProcessor(StreamProcessor):
    """Token 计数处理器"""

    def __init__(self):
        self.usage = TokenUsage()
        self._content_buffer = ""

    async def process(self, event: StreamEvent) -> Optional[StreamEvent]:
        if event.type == StreamEventType.CONTENT_DELTA:
            content = event.data.get("content", "")
            self._content_buffer += content
            # 粗略估算 (实际应使用 tiktoken)
            self.usage.completion_tokens += max(1, len(content) // 4)
            self.usage.total_tokens = self.usage.prompt_tokens + self.usage.completion_tokens

        elif event.type == StreamEventType.MESSAGE_END:
            # 更新最终统计
            if "usage" in event.data:
                api_usage = event.data["usage"]
                self.usage.prompt_tokens = api_usage.get("prompt_tokens", self.usage.prompt_tokens)
                self.usage.completion_tokens = api_usage.get("completion_tokens", self.usage.completion_tokens)
                self.usage.total_tokens = api_usage.get("total_tokens", self.usage.total_tokens)

        return event

    def get_usage(self) -> TokenUsage:
        return self.usage


class ContentFilterProcessor(StreamProcessor):
    """内容过滤处理器"""

    def __init__(self, filters: Optional[List[Callable[[str], bool]]] = None):
        self._filters = filters or []

    def add_filter(self, func: Callable[[str], bool]) -> None:
        self._filters.append(func)

    async def process(self, event: StreamEvent) -> Optional[StreamEvent]:
        if event.type == StreamEventType.CONTENT_DELTA:
            content = event.data.get("content", "")
            for f in self._filters:
                if not f(content):
                    return None  # 过滤掉
        return event


class RateLimitProcessor(StreamProcessor):
    """速率限制处理器 - 控制事件发送频率"""

    def __init__(self, min_interval_ms: int = 50):
        self._min_interval = min_interval_ms / 1000
        self._last_send_time = 0.0
        self._buffer: List[StreamEvent] = []

    async def process(self, event: StreamEvent) -> Optional[StreamEvent]:
        now = time.time()

        # 控制事件总是立即通过
        if event.type in (
            StreamEventType.ERROR,
            StreamEventType.DONE,
            StreamEventType.INTERRUPTED,
            StreamEventType.TOOL_CALL_START,
            StreamEventType.TOOL_RESULT,
        ):
            self._last_send_time = now
            return event

        # 速率限制内容事件
        if now - self._last_send_time < self._min_interval:
            self._buffer.append(event)
            return None

        # 合并缓冲区
        if self._buffer:
            merged_content = "".join(
                e.data.get("content", "") for e in self._buffer
            )
            event.data["content"] = merged_content + event.data.get("content", "")
            self._buffer.clear()

        self._last_send_time = now
        return event


# ============ 流式引擎 ============

class StreamEngine:
    """
    流式引擎 - 管理 LLM 响应流处理

    特性:
    - 管道式处理器链
    - 支持中断/恢复
    - 自动 Token 计数
    - SSE 输出生成
    """

    def __init__(
        self,
        processors: Optional[List[StreamProcessor]] = None,
        enable_token_counting: bool = True,
    ):
        self._processors: List[StreamProcessor] = processors or []
        self._sequence = 0
        self._is_streaming = False
        self._interrupted = False
        self._abort_event = asyncio.Event()

        # 自动添加 Token 计数器
        self._token_counter: Optional[TokenCounterProcessor] = None
        if enable_token_counting:
            self._token_counter = TokenCounterProcessor()
            self._processors.insert(0, self._token_counter)

    def add_processor(self, processor: StreamProcessor) -> "StreamEngine":
        """添加处理器"""
        self._processors.append(processor)
        return self

    @property
    def is_streaming(self) -> bool:
        return self._is_streaming

    @property
    def usage(self) -> Optional[TokenUsage]:
        if self._token_counter:
            return self._token_counter.get_usage()
        return None

    def interrupt(self) -> None:
        """中断流"""
        self._interrupted = True
        self._abort_event.set()
        logger.info("Stream interrupted")

    def reset(self) -> None:
        """重置状态"""
        self._interrupted = False
        self._abort_event.clear()
        self._sequence = 0

    @tracer.trace("stream.process")
    async def process_llm_stream(
        self,
        llm_stream: AsyncIterator[Any],
        trace_id: Optional[str] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        处理 LLM 流式响应

        将 LangChain 的 astream 输出转换为结构化的 StreamEvent
        """
        self._is_streaming = True
        self._interrupted = False

        try:
            # 发送开始事件
            yield await self._emit(StreamEvent(
                type=StreamEventType.MESSAGE_START,
                data={"model": "unknown"},
                trace_id=trace_id,
            ))

            content_buffer = ""
            tool_calls_buffer: Dict[int, Dict[str, Any]] = {}

            async for chunk in llm_stream:
                if self._interrupted:
                    yield await self._emit(StreamEvent(
                        type=StreamEventType.INTERRUPTED,
                        data={"reason": "user_interrupt", "partial_content": content_buffer},
                        trace_id=trace_id,
                    ))
                    return

                # 处理 AIMessageChunk
                if isinstance(chunk, AIMessageChunk):
                    # 文本内容
                    if chunk.content and isinstance(chunk.content, str):
                        content_buffer += chunk.content
                        event = StreamEvent(
                            type=StreamEventType.CONTENT_DELTA,
                            data={"content": chunk.content},
                            trace_id=trace_id,
                        )
                        result = await self._emit(event)
                        if result:
                            yield result

                    # 工具调用
                    if chunk.tool_call_chunks:
                        for tc_chunk in chunk.tool_call_chunks:
                            idx = tc_chunk.get("index", 0) if isinstance(tc_chunk, dict) else getattr(tc_chunk, "index", 0)

                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {"name": "", "args": ""}
                                name = tc_chunk.get("name", "") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "name", "")
                                if name:
                                    tool_calls_buffer[idx]["name"] = name
                                    yield await self._emit(StreamEvent(
                                        type=StreamEventType.TOOL_CALL_START,
                                        data={"tool_name": name, "index": idx},
                                        trace_id=trace_id,
                                    ))

                            args = tc_chunk.get("args", "") if isinstance(tc_chunk, dict) else getattr(tc_chunk, "args", "")
                            if args:
                                tool_calls_buffer[idx]["args"] += args
                                yield await self._emit(StreamEvent(
                                    type=StreamEventType.TOOL_CALL_DELTA,
                                    data={"args_delta": args, "index": idx},
                                    trace_id=trace_id,
                                ))

                # 处理其他类型的 chunk (dict from langgraph stream)
                elif isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        if isinstance(node_output, dict) and "messages" in node_output:
                            for msg in node_output["messages"]:
                                if hasattr(msg, "content") and msg.content:
                                    yield await self._emit(StreamEvent(
                                        type=StreamEventType.CONTENT_DELTA,
                                        data={
                                            "content": msg.content,
                                            "node": node_name,
                                        },
                                        trace_id=trace_id,
                                    ))

            # 完成工具调用事件
            for idx, tc in tool_calls_buffer.items():
                try:
                    args = json.loads(tc["args"]) if tc["args"] else {}
                except json.JSONDecodeError:
                    args = {"raw": tc["args"]}

                yield await self._emit(StreamEvent(
                    type=StreamEventType.TOOL_CALL_COMPLETE,
                    data={
                        "tool_name": tc["name"],
                        "arguments": args,
                        "index": idx,
                    },
                    trace_id=trace_id,
                ))

            # 完成内容事件
            if content_buffer:
                yield await self._emit(StreamEvent(
                    type=StreamEventType.CONTENT_COMPLETE,
                    data={"content": content_buffer},
                    trace_id=trace_id,
                ))

            # 结束事件
            usage_data = self._token_counter.get_usage().to_dict() if self._token_counter else {}
            yield await self._emit(StreamEvent(
                type=StreamEventType.MESSAGE_END,
                data={"usage": usage_data},
                trace_id=trace_id,
            ))

            # Done
            yield await self._emit(StreamEvent(
                type=StreamEventType.DONE,
                data={},
                trace_id=trace_id,
            ))

        except Exception as e:
            logger.error(f"Stream processing error: {e}", exc_info=True)
            yield await self._emit(StreamEvent(
                type=StreamEventType.ERROR,
                data={"error": str(e), "error_type": type(e).__name__},
                trace_id=trace_id,
            ))
        finally:
            self._is_streaming = False

    async def _emit(self, event: StreamEvent) -> Optional[StreamEvent]:
        """通过处理器链发送事件"""
        event.sequence = self._sequence
        self._sequence += 1

        current_event: Optional[StreamEvent] = event
        for processor in self._processors:
            if current_event is None:
                break
            current_event = await processor.process(current_event)

        return current_event


# ============ SSE 生成器 ============

async def generate_sse_stream(
    event_stream: AsyncGenerator[StreamEvent, None],
    include_ping: bool = True,
    ping_interval: float = 15.0,
) -> AsyncGenerator[str, None]:
    """
    将 StreamEvent 流转换为 SSE 字符串流

    Args:
        event_stream: StreamEvent 异步生成器
        include_ping: 是否发送心跳
        ping_interval: 心跳间隔（秒）
    """
    last_ping = time.time()

    async for event in event_stream:
        if event is None:
            continue

        yield event.to_sse()

        # 心跳
        if include_ping and time.time() - last_ping > ping_interval:
            ping_event = StreamEvent(type=StreamEventType.PING)
            yield ping_event.to_sse()
            last_ping = time.time()


# ============ 便捷函数 ============

def create_stream_engine(
    enable_rate_limit: bool = False,
    rate_limit_ms: int = 50,
    enable_token_counting: bool = True,
) -> StreamEngine:
    """创建流式引擎"""
    processors = []

    if enable_rate_limit:
        processors.append(RateLimitProcessor(rate_limit_ms))

    engine = StreamEngine(
        processors=processors,
        enable_token_counting=enable_token_counting,
    )
    return engine


__all__ = [
    # 类型
    "StreamEventType",
    "StreamEvent",
    "TokenUsage",
    # 处理器
    "StreamProcessor",
    "TokenCounterProcessor",
    "ContentFilterProcessor",
    "RateLimitProcessor",
    # 引擎
    "StreamEngine",
    # 便捷函数
    "create_stream_engine",
    "generate_sse_stream",
]
