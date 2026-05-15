"""
Retry & Resilience - 错误恢复和重试机制

提供:
- 指数退避重试
- 断路器模式
- 降级策略
- 超时管理
- 错误分类
"""

import asyncio
import time
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Set, Type, TypeVar, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone, timedelta
from functools import wraps

from agent.observability import get_logger, get_tracer

logger = get_logger("retry")
tracer = get_tracer("retry")

T = TypeVar("T")


# ============ 错误分类 ============

class ErrorCategory(str, Enum):
    """错误分类"""
    TRANSIENT = "transient"           # 临时错误 (网络超时等) - 可重试
    RATE_LIMITED = "rate_limited"     # 被限流 - 等待后重试
    AUTHENTICATION = "authentication"  # 认证失败 - 不可重试
    INVALID_REQUEST = "invalid_request"  # 请求无效 - 不可重试
    SERVER_ERROR = "server_error"     # 服务器错误 - 可能可重试
    OVERLOADED = "overloaded"         # 过载 - 等待后重试
    CONTEXT_TOO_LONG = "context_too_long"  # 上下文太长 - 需要压缩
    UNKNOWN = "unknown"              # 未知错误


def categorize_error(error: Exception) -> ErrorCategory:
    """对错误进行分类"""
    error_str = str(error).lower()
    error_type = type(error).__name__

    # 网络/超时错误
    if any(k in error_type.lower() for k in ["timeout", "connection", "network"]):
        return ErrorCategory.TRANSIENT

    # HTTP 状态码相关
    if "429" in error_str or "rate limit" in error_str:
        return ErrorCategory.RATE_LIMITED
    if "401" in error_str or "403" in error_str or "unauthorized" in error_str:
        return ErrorCategory.AUTHENTICATION
    if "400" in error_str or "invalid" in error_str:
        return ErrorCategory.INVALID_REQUEST
    if "500" in error_str or "502" in error_str or "503" in error_str:
        return ErrorCategory.SERVER_ERROR
    if "529" in error_str or "overloaded" in error_str:
        return ErrorCategory.OVERLOADED
    if "too long" in error_str or "token" in error_str and "limit" in error_str:
        return ErrorCategory.CONTEXT_TOO_LONG

    return ErrorCategory.UNKNOWN


RETRYABLE_CATEGORIES: Set[ErrorCategory] = {
    ErrorCategory.TRANSIENT,
    ErrorCategory.RATE_LIMITED,
    ErrorCategory.SERVER_ERROR,
    ErrorCategory.OVERLOADED,
}


def is_retryable(error: Exception) -> bool:
    """判断错误是否可重试"""
    return categorize_error(error) in RETRYABLE_CATEGORIES


# ============ 重试配置 ============

@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    initial_delay: float = 1.0          # 初始延迟（秒）
    max_delay: float = 60.0             # 最大延迟（秒）
    exponential_base: float = 2.0       # 指数基数
    jitter: bool = True                 # 是否添加抖动
    retryable_exceptions: Optional[Set[Type[Exception]]] = None
    retryable_categories: Set[ErrorCategory] = field(
        default_factory=lambda: RETRYABLE_CATEGORIES.copy()
    )

    def get_delay(self, attempt: int) -> float:
        """计算第 N 次重试的延迟"""
        delay = self.initial_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


# ============ 重试执行器 ============

@dataclass
class RetryAttempt:
    """重试尝试记录"""
    attempt: int
    error: Exception
    category: ErrorCategory
    delay: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RetryExecutor:
    """
    重试执行器

    支持:
    - 指数退避
    - 抖动
    - 错误分类判断
    - 重试回调
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self._config = config or RetryConfig()
        self._attempts: List[RetryAttempt] = []

    @property
    def attempts(self) -> List[RetryAttempt]:
        return self._attempts.copy()

    @property
    def total_attempts(self) -> int:
        return len(self._attempts)

    @tracer.trace("retry.execute")
    async def execute(
        self,
        func: Callable[..., Any],
        *args,
        on_retry: Optional[Callable[[RetryAttempt], None]] = None,
        **kwargs,
    ) -> Any:
        """
        执行带重试的异步操作

        Args:
            func: 要执行的异步函数
            on_retry: 重试时的回调
        """
        self._attempts.clear()
        last_error: Optional[Exception] = None

        for attempt in range(self._config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_error = e
                category = categorize_error(e)

                # 检查是否可重试
                if not self._should_retry(e, category, attempt):
                    logger.warning(
                        f"Non-retryable error",
                        error=str(e),
                        category=category.value,
                        attempt=attempt,
                    )
                    raise

                # 计算延迟
                delay = self._config.get_delay(attempt)

                # 记录尝试
                retry_attempt = RetryAttempt(
                    attempt=attempt,
                    error=e,
                    category=category,
                    delay=delay,
                )
                self._attempts.append(retry_attempt)

                logger.info(
                    f"Retrying after error",
                    error=str(e),
                    category=category.value,
                    attempt=attempt + 1,
                    max_retries=self._config.max_retries,
                    delay=round(delay, 2),
                )

                # 回调
                if on_retry:
                    on_retry(retry_attempt)

                # 等待
                await asyncio.sleep(delay)

        # 所有重试都失败了
        raise last_error  # type: ignore

    def _should_retry(
        self, error: Exception, category: ErrorCategory, attempt: int
    ) -> bool:
        """判断是否应该重试"""
        if attempt >= self._config.max_retries:
            return False

        # 按类型检查
        if self._config.retryable_exceptions:
            if type(error) in self._config.retryable_exceptions:
                return True

        # 按分类检查
        return category in self._config.retryable_categories


# ============ 断路器 ============

class CircuitState(str, Enum):
    """断路器状态"""
    CLOSED = "closed"       # 正常 - 请求通过
    OPEN = "open"           # 断开 - 请求被拒绝
    HALF_OPEN = "half_open"  # 半开 - 允许试探性请求


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5         # 失败阈值
    recovery_timeout: float = 30.0     # 恢复超时（秒）
    success_threshold: int = 3         # 半开状态下成功阈值
    half_open_max_calls: int = 1       # 半开状态最大并发


class CircuitBreaker:
    """
    断路器

    状态转换:
    CLOSED → (failures >= threshold) → OPEN
    OPEN → (timeout elapsed) → HALF_OPEN
    HALF_OPEN → (successes >= threshold) → CLOSED
    HALF_OPEN → (any failure) → OPEN
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

    @property
    def state(self) -> CircuitState:
        # 检查是否应该转为半开
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self._config.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                self._success_count = 0
                logger.info(f"Circuit breaker {self.name}: OPEN → HALF_OPEN")
        return self._state

    @tracer.trace("circuit_breaker.call")
    async def call(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """通过断路器执行调用"""
        state = self.state

        if state == CircuitState.OPEN:
            raise CircuitBreakerOpen(
                f"Circuit breaker '{self.name}' is OPEN",
                recovery_time=self._config.recovery_timeout,
            )

        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls >= self._config.half_open_max_calls:
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is HALF_OPEN (max calls reached)"
                )
            self._half_open_calls += 1

        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """成功时的处理"""
        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                logger.info(f"Circuit breaker {self.name}: HALF_OPEN → CLOSED")
        else:
            self._failure_count = max(0, self._failure_count - 1)

    def _on_failure(self) -> None:
        """失败时的处理"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name}: HALF_OPEN → OPEN")
        elif self._failure_count >= self._config.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker {self.name}: CLOSED → OPEN",
                failures=self._failure_count,
            )

    def reset(self) -> None:
        """重置断路器"""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None


class CircuitBreakerOpen(Exception):
    """断路器打开异常"""
    def __init__(self, message: str, recovery_time: float = 0):
        super().__init__(message)
        self.recovery_time = recovery_time


# ============ 降级策略 ============

class FallbackStrategy(ABC):
    """降级策略基类"""

    @abstractmethod
    async def execute(self, error: Exception, *args, **kwargs) -> Any:
        """执行降级逻辑"""
        pass


class ModelFallback(FallbackStrategy):
    """模型降级 - 切换到备用模型"""

    def __init__(self, fallback_models: List[str]):
        self._fallback_models = fallback_models
        self._current_index = 0

    async def execute(self, error: Exception, *args, **kwargs) -> Any:
        if self._current_index < len(self._fallback_models):
            model = self._fallback_models[self._current_index]
            self._current_index += 1
            logger.info(f"Falling back to model: {model}")
            return {"fallback_model": model}
        raise error


class CachedResponseFallback(FallbackStrategy):
    """缓存响应降级"""

    def __init__(self, cache: Dict[str, Any]):
        self._cache = cache

    async def execute(self, error: Exception, *args, **kwargs) -> Any:
        key = str(args) if args else "default"
        if key in self._cache:
            return self._cache[key]
        raise error


# ============ 带重试的装饰器 ============

def with_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Optional[Set[Type[Exception]]] = None,
):
    """
    重试装饰器

    Example:
        @with_retry(max_retries=3, initial_delay=1.0)
        async def call_api():
            ...
    """
    config = RetryConfig(
        max_retries=max_retries,
        initial_delay=initial_delay,
        max_delay=max_delay,
        retryable_exceptions=retryable_exceptions,
    )

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            executor = RetryExecutor(config)
            return await executor.execute(func, *args, **kwargs)
        return wrapper

    return decorator


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
):
    """
    断路器装饰器

    Example:
        @with_circuit_breaker("llm_api", failure_threshold=5)
        async def call_llm():
            ...
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
    )
    breaker = CircuitBreaker(name, config)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)

        wrapper._circuit_breaker = breaker  # type: ignore
        return wrapper

    return decorator


def with_timeout(seconds: float):
    """
    超时装饰器

    Example:
        @with_timeout(30.0)
        async def slow_operation():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds,
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"{func.__name__} timed out after {seconds}s")
        return wrapper
    return decorator


__all__ = [
    # 错误分类
    "ErrorCategory",
    "categorize_error",
    "is_retryable",
    "RETRYABLE_CATEGORIES",
    # 配置
    "RetryConfig",
    "CircuitBreakerConfig",
    # 重试
    "RetryAttempt",
    "RetryExecutor",
    # 断路器
    "CircuitState",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    # 降级
    "FallbackStrategy",
    "ModelFallback",
    "CachedResponseFallback",
    # 装饰器
    "with_retry",
    "with_circuit_breaker",
    "with_timeout",
]
