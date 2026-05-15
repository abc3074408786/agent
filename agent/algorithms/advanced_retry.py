"""
高级重试策略 - 参考 Claude Code 的 withRetry.ts

特性:
- 持久重试模式 (无人值守会话)
- 模型降级 (连续 529 后切换 fallback)
- Fast mode 冷却 (短延迟保缓存, 长延迟降级)
- 上下文溢出动态恢复
- 心跳信号 (长等待时保活)
- 前台/后台查询区分
"""

import asyncio
import time
import random
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum

from agent.observability import get_logger, get_tracer
from agent.retry import (
    ErrorCategory,
    categorize_error,
    RetryConfig,
)

logger = get_logger("advanced_retry")
tracer = get_tracer("advanced_retry")

T = TypeVar("T")


# ============ 常量 (参考 Claude Code) ============

BASE_DELAY_MS = 500
DEFAULT_MAX_RETRIES = 10
MAX_529_RETRIES = 3
FLOOR_OUTPUT_TOKENS = 3000
SHORT_RETRY_THRESHOLD_MS = 20_000  # Fast mode: 20s 以下保持缓存
DEFAULT_COOLDOWN_MS = 30 * 60 * 1000  # 默认冷却 30 分钟
MIN_COOLDOWN_MS = 10 * 60 * 1000  # 最小冷却 10 分钟

# 持久重试模式常量
PERSISTENT_MAX_BACKOFF_MS = 5 * 60 * 1000  # 5 分钟
PERSISTENT_RESET_CAP_MS = 6 * 60 * 60 * 1000  # 6 小时
HEARTBEAT_INTERVAL_MS = 30_000  # 30 秒心跳


class RetryMode(str, Enum):
    """重试模式"""
    STANDARD = "standard"       # 标准: 有限次数重试
    PERSISTENT = "persistent"   # 持久: 无限重试 (无人值守)


class QuerySource(str, Enum):
    """查询来源 - 决定是否重试 529"""
    FOREGROUND = "foreground"   # 前台 (用户等待)
    BACKGROUND = "background"   # 后台 (摘要/分类器)
    AGENT = "agent"             # Agent 子任务


# 前台来源才重试 529
FOREGROUND_SOURCES: Set[QuerySource] = {
    QuerySource.FOREGROUND,
    QuerySource.AGENT,
}


@dataclass
class RetryState:
    """重试状态 (跨尝试共享)"""
    model: str = ""
    fallback_model: Optional[str] = None
    max_tokens_override: Optional[int] = None
    consecutive_529: int = 0
    total_attempts: int = 0
    fast_mode_active: bool = False
    fast_mode_cooldown_until: float = 0.0
    # 心跳
    last_heartbeat: float = 0.0
    # 持久模式
    persistent_start_time: float = 0.0


@dataclass
class RetryDecision:
    """重试决策"""
    should_retry: bool
    delay_ms: float = 0.0
    action: str = ""  # "retry", "fallback", "cooldown", "abort"
    new_model: Optional[str] = None
    max_tokens_override: Optional[int] = None


# ============ 延迟计算 ============

def calculate_backoff_delay(
    attempt: int,
    base_delay_ms: float = BASE_DELAY_MS,
    max_delay_ms: float = 32_000,
    jitter_factor: float = 0.25,
) -> float:
    """
    指数退避延迟计算
    
    delay = base * 2^(attempt-1), capped at max
    jitter = delay * random() * jitter_factor
    
    参考 Claude Code: BASE_DELAY_MS * 2^(attempt-1)
    """
    delay = base_delay_ms * (2 ** (attempt - 1))
    delay = min(delay, max_delay_ms)

    # 添加抖动
    jitter = delay * random.random() * jitter_factor
    return delay + jitter


def calculate_persistent_delay(
    attempt: int,
    start_time: float,
) -> float:
    """
    持久模式延迟
    
    参考 Claude Code: PERSISTENT_MAX_BACKOFF_MS = 5min, RESET_CAP = 6hr
    """
    elapsed = (time.time() - start_time) * 1000

    # 超过 6 小时重置
    if elapsed > PERSISTENT_RESET_CAP_MS:
        return BASE_DELAY_MS

    # 指数退避，上限 5 分钟
    delay = BASE_DELAY_MS * (2 ** min(attempt - 1, 12))
    return min(delay, PERSISTENT_MAX_BACKOFF_MS)


# ============ 错误分析 ============

def parse_retry_after_header(error: Exception) -> Optional[float]:
    """从错误中解析 retry-after (毫秒)"""
    error_str = str(error)

    # 尝试从错误信息中提取 retry-after 秒数
    import re
    match = re.search(r'retry.?after[:\s]*(\d+(?:\.\d+)?)', error_str, re.IGNORECASE)
    if match:
        seconds = float(match.group(1))
        return seconds * 1000

    return None


def parse_context_overflow(error: Exception) -> Optional[Dict[str, int]]:
    """
    解析上下文溢出错误
    
    参考 Claude Code: parseMaxTokensContextOverflowError()
    """
    error_str = str(error)

    import re
    # "input tokens: 150000, context limit: 128000"
    input_match = re.search(r'input.?tokens?[:\s]*(\d+)', error_str, re.IGNORECASE)
    limit_match = re.search(r'context.?(?:limit|window)[:\s]*(\d+)', error_str, re.IGNORECASE)

    if input_match and limit_match:
        return {
            "input_tokens": int(input_match.group(1)),
            "context_limit": int(limit_match.group(1)),
        }

    return None


def is_overloaded_error(error: Exception) -> bool:
    """是否是 529 过载错误"""
    error_str = str(error).lower()
    return "529" in error_str or "overloaded" in error_str


def is_rate_limited(error: Exception) -> bool:
    """是否是 429 限流"""
    return "429" in str(error)


# ============ 高级重试执行器 ============

class AdvancedRetryExecutor:
    """
    高级重试执行器
    
    参考 Claude Code withRetry() 的完整逻辑:
    1. 标准指数退避重试
    2. 529 连续失败触发模型降级
    3. Fast mode 冷却管理
    4. 上下文溢出动态调整 max_tokens
    5. 持久模式无限重试
    6. 心跳保活
    """

    def __init__(
        self,
        mode: RetryMode = RetryMode.STANDARD,
        max_retries: int = DEFAULT_MAX_RETRIES,
        model: str = "",
        fallback_model: Optional[str] = None,
        query_source: QuerySource = QuerySource.FOREGROUND,
        on_heartbeat: Optional[Callable[[], None]] = None,
        on_fallback: Optional[Callable[[str], None]] = None,
    ):
        self._mode = mode
        self._max_retries = max_retries
        self._query_source = query_source
        self._on_heartbeat = on_heartbeat
        self._on_fallback = on_fallback
        self._state = RetryState(
            model=model,
            fallback_model=fallback_model,
        )

    @tracer.trace("advanced_retry.execute")
    async def execute(
        self,
        operation: Callable[..., Any],
        *args,
        **kwargs,
    ) -> Any:
        """
        执行带高级重试的操作
        """
        self._state.persistent_start_time = time.time()
        self._state.last_heartbeat = time.time()

        max_attempts = (
            self._max_retries + 1 if self._mode == RetryMode.STANDARD
            else 999999  # 持久模式
        )

        for attempt in range(1, max_attempts + 1):
            self._state.total_attempts = attempt

            try:
                # 注入可能被修改的参数
                if self._state.max_tokens_override:
                    kwargs["max_tokens"] = self._state.max_tokens_override
                if self._state.model:
                    kwargs.setdefault("model", self._state.model)

                result = await operation(*args, **kwargs)
                # 成功时重置 529 计数
                self._state.consecutive_529 = 0
                return result

            except Exception as e:
                decision = self._make_decision(e, attempt)

                logger.info(
                    f"Retry decision",
                    attempt=attempt,
                    action=decision.action,
                    delay_ms=round(decision.delay_ms),
                    error=str(e)[:100],
                )

                if not decision.should_retry:
                    raise

                # 应用决策
                if decision.new_model:
                    self._state.model = decision.new_model
                    kwargs["model"] = decision.new_model
                    if self._on_fallback:
                        self._on_fallback(decision.new_model)

                if decision.max_tokens_override:
                    self._state.max_tokens_override = decision.max_tokens_override

                # 等待 (持久模式发心跳)
                await self._wait_with_heartbeat(decision.delay_ms)

        raise RuntimeError("Max retries exceeded")

    def _make_decision(self, error: Exception, attempt: int) -> RetryDecision:
        """
        制定重试决策
        
        参考 Claude Code 的决策逻辑顺序
        """
        # 1. 不可重试的错误
        category = categorize_error(error)
        if category in (ErrorCategory.AUTHENTICATION, ErrorCategory.INVALID_REQUEST):
            return RetryDecision(should_retry=False, action="abort")

        # 2. 529 过载处理
        if is_overloaded_error(error):
            return self._handle_529(error, attempt)

        # 3. 429 限流
        if is_rate_limited(error):
            return self._handle_429(error, attempt)

        # 4. 上下文溢出
        overflow = parse_context_overflow(error)
        if overflow:
            return self._handle_context_overflow(overflow, attempt)

        # 5. 标准重试
        if self._mode == RetryMode.STANDARD and attempt > self._max_retries:
            return RetryDecision(should_retry=False, action="abort")

        delay = calculate_backoff_delay(attempt)
        return RetryDecision(should_retry=True, delay_ms=delay, action="retry")

    def _handle_529(self, error: Exception, attempt: int) -> RetryDecision:
        """处理 529 过载"""
        # 后台查询不重试 529
        if self._query_source not in FOREGROUND_SOURCES:
            return RetryDecision(should_retry=False, action="abort")

        self._state.consecutive_529 += 1

        # 连续 3 次 529 → 模型降级
        if (
            self._state.consecutive_529 >= MAX_529_RETRIES
            and self._state.fallback_model
        ):
            logger.warning(
                f"529 threshold reached, falling back",
                consecutive=self._state.consecutive_529,
                fallback=self._state.fallback_model,
            )
            self._state.consecutive_529 = 0
            return RetryDecision(
                should_retry=True,
                delay_ms=BASE_DELAY_MS,
                action="fallback",
                new_model=self._state.fallback_model,
            )

        # 正常重试
        if self._mode == RetryMode.PERSISTENT:
            delay = calculate_persistent_delay(
                attempt, self._state.persistent_start_time
            )
        else:
            delay = calculate_backoff_delay(attempt)

        return RetryDecision(should_retry=True, delay_ms=delay, action="retry")

    def _handle_429(self, error: Exception, attempt: int) -> RetryDecision:
        """处理 429 限流"""
        retry_after = parse_retry_after_header(error)

        if retry_after and retry_after < SHORT_RETRY_THRESHOLD_MS:
            # 短延迟: 直接等待
            return RetryDecision(
                should_retry=True, delay_ms=retry_after, action="retry"
            )

        # 长延迟: 降级或等待
        delay = retry_after or calculate_backoff_delay(attempt)
        return RetryDecision(should_retry=True, delay_ms=delay, action="retry")

    def _handle_context_overflow(
        self, overflow: Dict[str, int], attempt: int
    ) -> RetryDecision:
        """
        处理上下文溢出
        
        参考 Claude Code: 动态减少 max_tokens
        """
        input_tokens = overflow["input_tokens"]
        context_limit = overflow["context_limit"]

        safety_buffer = 1000
        available = max(0, context_limit - input_tokens - safety_buffer)

        if available < FLOOR_OUTPUT_TOKENS:
            return RetryDecision(should_retry=False, action="abort")

        adjusted = max(FLOOR_OUTPUT_TOKENS, available)

        logger.info(
            f"Context overflow recovery",
            input_tokens=input_tokens,
            context_limit=context_limit,
            adjusted_max_tokens=adjusted,
        )

        return RetryDecision(
            should_retry=True,
            delay_ms=0,
            action="retry",
            max_tokens_override=adjusted,
        )

    async def _wait_with_heartbeat(self, delay_ms: float) -> None:
        """等待并发送心跳"""
        delay_seconds = delay_ms / 1000
        elapsed = 0.0
        heartbeat_interval = HEARTBEAT_INTERVAL_MS / 1000

        while elapsed < delay_seconds:
            wait_time = min(heartbeat_interval, delay_seconds - elapsed)
            await asyncio.sleep(wait_time)
            elapsed += wait_time

            # 发送心跳
            if self._on_heartbeat and elapsed < delay_seconds:
                now = time.time()
                if now - self._state.last_heartbeat > heartbeat_interval:
                    self._on_heartbeat()
                    self._state.last_heartbeat = now


# ============ 便捷函数 ============

async def with_advanced_retry(
    operation: Callable[..., Any],
    *args,
    max_retries: int = 10,
    model: str = "",
    fallback_model: Optional[str] = None,
    **kwargs,
) -> Any:
    """便捷重试包装"""
    executor = AdvancedRetryExecutor(
        max_retries=max_retries,
        model=model,
        fallback_model=fallback_model,
    )
    return await executor.execute(operation, *args, **kwargs)


__all__ = [
    # 常量
    "BASE_DELAY_MS",
    "MAX_529_RETRIES",
    # 枚举
    "RetryMode",
    "QuerySource",
    # 数据类
    "RetryState",
    "RetryDecision",
    # 函数
    "calculate_backoff_delay",
    "calculate_persistent_delay",
    "parse_retry_after_header",
    "parse_context_overflow",
    "is_overloaded_error",
    "is_rate_limited",
    # 类
    "AdvancedRetryExecutor",
    # 便捷函数
    "with_advanced_retry",
]
