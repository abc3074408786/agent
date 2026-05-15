"""
Middleware System - 请求/响应中间件链

提供:
- 中间件管道
- 请求拦截和修改
- 响应拦截和修改
- 认证中间件
- 限流中间件
- 日志中间件
- 错误处理中间件
"""

import time
import asyncio
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

from agent.observability import get_logger, get_tracer, generate_trace_id, set_trace_context
from agent.schemas import ChatRequest, ChatResponse

logger = get_logger("middleware")
tracer = get_tracer("middleware")


# ============ 中间件上下文 ============

@dataclass
class MiddlewareContext:
    """中间件上下文 - 在整个处理链中传递"""
    request_id: str = field(default_factory=generate_trace_id)
    trace_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 认证信息
    auth_token: Optional[str] = None
    auth_claims: Dict[str, Any] = field(default_factory=dict)
    # 控制标志
    skip_remaining: bool = False
    error: Optional[Exception] = None

    @property
    def elapsed_ms(self) -> float:
        return (time.time() - self.start_time) * 1000


# ============ 中间件基类 ============

class Middleware(ABC):
    """中间件抽象基类"""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def order(self) -> int:
        """执行顺序 (数字越小越先执行)"""
        return 100

    @abstractmethod
    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        """处理请求 (在 Agent 执行前)"""
        pass

    @abstractmethod
    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        """处理响应 (在 Agent 执行后)"""
        pass

    async def on_error(
        self, error: Exception, context: MiddlewareContext
    ) -> Optional[ChatResponse]:
        """错误处理 (可选覆盖)"""
        return None


# ============ 内置中间件 ============

class TracingMiddleware(Middleware):
    """追踪中间件 - 设置请求追踪上下文"""

    @property
    def order(self) -> int:
        return 1  # 最先执行

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        context.trace_id = context.request_id
        set_trace_context(
            trace_id=context.trace_id,
            session_id=context.session_id or request.session_id,
        )
        logger.debug(
            f"Request started",
            request_id=context.request_id,
            session_id=request.session_id,
        )
        return request

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        logger.debug(
            f"Request completed",
            request_id=context.request_id,
            elapsed_ms=context.elapsed_ms,
        )
        return response


class AuthenticationMiddleware(Middleware):
    """
    认证中间件

    支持:
    - API Key 认证
    - JWT Token 认证
    - 自定义认证逻辑
    """

    def __init__(
        self,
        api_keys: Optional[set] = None,
        jwt_secret: Optional[str] = None,
        custom_validator: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ):
        self._api_keys = api_keys or set()
        self._jwt_secret = jwt_secret
        self._custom_validator = custom_validator

    @property
    def order(self) -> int:
        return 10

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        token = context.auth_token

        if not token:
            # 无需认证的情况
            if not self._api_keys and not self._jwt_secret and not self._custom_validator:
                return request
            raise PermissionError("Authentication required")

        # API Key 验证
        if token.startswith("sk-") or token in self._api_keys:
            if token in self._api_keys:
                context.auth_claims = {"type": "api_key"}
                return request
            raise PermissionError("Invalid API key")

        # JWT 验证
        if self._jwt_secret and token.startswith("eyJ"):
            claims = self._validate_jwt(token)
            if claims:
                context.auth_claims = claims
                context.user_id = claims.get("sub")
                return request
            raise PermissionError("Invalid JWT token")

        # 自定义验证
        if self._custom_validator:
            claims = self._custom_validator(token)
            if claims:
                context.auth_claims = claims
                return request
            raise PermissionError("Authentication failed")

        raise PermissionError("Invalid credentials")

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        return response

    def _validate_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """验证 JWT (简化版)"""
        try:
            import jwt
            return jwt.decode(token, self._jwt_secret, algorithms=["HS256"])
        except ImportError:
            logger.warning("PyJWT not installed, JWT validation unavailable")
            return None
        except Exception:
            return None


class RateLimitMiddleware(Middleware):
    """
    限流中间件

    基于滑动窗口的限流
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        by: str = "ip",  # "ip", "user", "session", "global"
    ):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._by = by
        self._requests: Dict[str, List[float]] = defaultdict(list)

    @property
    def order(self) -> int:
        return 20

    def _get_key(self, request: ChatRequest, context: MiddlewareContext) -> str:
        """获取限流键"""
        if self._by == "user":
            return f"user:{context.user_id or 'anonymous'}"
        elif self._by == "session":
            return f"session:{request.session_id or 'default'}"
        elif self._by == "global":
            return "global"
        else:
            return f"ip:{context.metadata.get('client_ip', 'unknown')}"

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        key = self._get_key(request, context)
        now = time.time()
        window_start = now - self._window_seconds

        # 清理过期记录
        self._requests[key] = [
            t for t in self._requests[key] if t > window_start
        ]

        # 检查限制
        if len(self._requests[key]) >= self._max_requests:
            remaining = self._window_seconds - (now - self._requests[key][0])
            raise RateLimitExceeded(
                f"Rate limit exceeded. Retry after {remaining:.0f}s",
                retry_after=remaining,
            )

        # 记录请求
        self._requests[key].append(now)
        context.metadata["rate_limit_remaining"] = (
            self._max_requests - len(self._requests[key])
        )

        return request

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        return response


class RateLimitExceeded(Exception):
    """限流异常"""
    def __init__(self, message: str, retry_after: float = 0):
        super().__init__(message)
        self.retry_after = retry_after


class LoggingMiddleware(Middleware):
    """日志中间件 - 记录请求/响应"""

    def __init__(self, log_request_body: bool = False, log_response_body: bool = False):
        self._log_request = log_request_body
        self._log_response = log_response_body

    @property
    def order(self) -> int:
        return 5

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        log_data = {
            "request_id": context.request_id,
            "session_id": request.session_id,
            "model": request.model,
        }
        if self._log_request:
            log_data["message_count"] = len(request.messages) if request.messages else 0

        logger.info("Incoming request", **log_data)
        return request

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        logger.info(
            "Outgoing response",
            request_id=context.request_id,
            elapsed_ms=round(context.elapsed_ms, 2),
            status="success" if not context.error else "error",
        )
        return response


class ErrorHandlingMiddleware(Middleware):
    """
    错误处理中间件

    捕获异常并转换为结构化错误响应
    """

    @property
    def order(self) -> int:
        return 2  # 靠前执行，捕获后续中间件的错误

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        return request

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        return response

    async def on_error(
        self, error: Exception, context: MiddlewareContext
    ) -> Optional[ChatResponse]:
        """将异常转为错误响应"""
        from agent.schemas import ChatResponse, Message, MessageRole

        error_type = type(error).__name__

        if isinstance(error, PermissionError):
            status_code = 401
        elif isinstance(error, RateLimitExceeded):
            status_code = 429
        elif isinstance(error, ValueError):
            status_code = 400
        else:
            status_code = 500
            logger.error(f"Unhandled error: {error}", exc_info=True)

        return ChatResponse(
            session_id=context.session_id or "",
            messages=[Message(
                role=MessageRole.ASSISTANT,
                content=f"Error ({error_type}): {str(error)}",
            )],
            metadata={
                "error": True,
                "error_type": error_type,
                "status_code": status_code,
                "request_id": context.request_id,
            },
        )


class InputValidationMiddleware(Middleware):
    """输入验证中间件"""

    def __init__(
        self,
        max_message_length: int = 100000,
        max_messages: int = 200,
    ):
        self._max_message_length = max_message_length
        self._max_messages = max_messages

    @property
    def order(self) -> int:
        return 15

    async def process_request(
        self, request: ChatRequest, context: MiddlewareContext
    ) -> ChatRequest:
        if request.messages:
            if len(request.messages) > self._max_messages:
                raise ValueError(
                    f"Too many messages: {len(request.messages)} > {self._max_messages}"
                )
            for msg in request.messages:
                if msg.content and len(msg.content) > self._max_message_length:
                    raise ValueError(
                        f"Message too long: {len(msg.content)} > {self._max_message_length}"
                    )
        return request

    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        return response


# ============ 中间件管道 ============

class MiddlewarePipeline:
    """
    中间件管道

    按序执行中间件链:
    Request → MW1 → MW2 → ... → Agent → ... → MW2 → MW1 → Response
    """

    def __init__(self, middlewares: Optional[List[Middleware]] = None):
        self._middlewares: List[Middleware] = []
        if middlewares:
            for mw in middlewares:
                self.add(mw)

    def add(self, middleware: Middleware) -> "MiddlewarePipeline":
        """添加中间件"""
        self._middlewares.append(middleware)
        self._middlewares.sort(key=lambda m: m.order)
        logger.debug(f"Added middleware: {middleware.name}", order=middleware.order)
        return self

    def remove(self, name: str) -> bool:
        """移除中间件"""
        before = len(self._middlewares)
        self._middlewares = [m for m in self._middlewares if m.name != name]
        return len(self._middlewares) < before

    @tracer.trace("middleware.process_request")
    async def process_request(
        self, request: ChatRequest, context: Optional[MiddlewareContext] = None
    ) -> Tuple[ChatRequest, MiddlewareContext]:
        """执行请求中间件链"""
        if context is None:
            context = MiddlewareContext()

        for mw in self._middlewares:
            if context.skip_remaining:
                break
            try:
                request = await mw.process_request(request, context)
            except Exception as e:
                context.error = e
                # 尝试错误处理
                response = await self._handle_error(e, context)
                if response:
                    raise MiddlewarePipelineError(response, e)
                raise

        return request, context

    @tracer.trace("middleware.process_response")
    async def process_response(
        self, response: ChatResponse, context: MiddlewareContext
    ) -> ChatResponse:
        """执行响应中间件链 (逆序)"""
        for mw in reversed(self._middlewares):
            try:
                response = await mw.process_response(response, context)
            except Exception as e:
                logger.error(f"Middleware response error: {mw.name}", error=str(e))
                # 响应阶段的错误不中断链

        return response

    async def _handle_error(
        self, error: Exception, context: MiddlewareContext
    ) -> Optional[ChatResponse]:
        """遍历中间件错误处理器"""
        for mw in self._middlewares:
            response = await mw.on_error(error, context)
            if response:
                return response
        return None

    @property
    def middleware_names(self) -> List[str]:
        return [m.name for m in self._middlewares]


class MiddlewarePipelineError(Exception):
    """中间件管道错误"""
    def __init__(self, response: ChatResponse, original_error: Exception):
        self.response = response
        self.original_error = original_error
        super().__init__(str(original_error))


# ============ 便捷函数 ============

def create_default_pipeline(
    api_keys: Optional[set] = None,
    rate_limit: int = 60,
    enable_auth: bool = False,
) -> MiddlewarePipeline:
    """
    创建默认中间件管道

    包含: 追踪 → 错误处理 → 日志 → (认证) → 限流 → 验证
    """
    middlewares = [
        TracingMiddleware(),
        ErrorHandlingMiddleware(),
        LoggingMiddleware(),
        RateLimitMiddleware(max_requests=rate_limit),
        InputValidationMiddleware(),
    ]

    if enable_auth and api_keys:
        middlewares.append(AuthenticationMiddleware(api_keys=api_keys))

    return MiddlewarePipeline(middlewares)


__all__ = [
    # 上下文
    "MiddlewareContext",
    # 基类
    "Middleware",
    # 内置中间件
    "TracingMiddleware",
    "AuthenticationMiddleware",
    "RateLimitMiddleware",
    "LoggingMiddleware",
    "ErrorHandlingMiddleware",
    "InputValidationMiddleware",
    # 管道
    "MiddlewarePipeline",
    "MiddlewarePipelineError",
    # 异常
    "RateLimitExceeded",
    # 便捷函数
    "create_default_pipeline",
]
