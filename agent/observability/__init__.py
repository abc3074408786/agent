"""
Observability Module - 结构化日志和请求追踪

提供:
- 结构化 JSON 日志
- 请求追踪 (trace_id, span_id)
- 上下文管理器用于追踪
- 装饰器用于函数追踪
"""

import logging
import json
import uuid
import time
import functools
from typing import Any, Optional, Dict, Callable
from contextvars import ContextVar
from datetime import datetime, timezone

# 上下文变量用于存储追踪信息
_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_session_id: ContextVar[Optional[str]] = ContextVar("session_id", default=None)


def get_trace_id() -> Optional[str]:
    """获取当前追踪 ID"""
    return _trace_id.get()


def get_span_id() -> Optional[str]:
    """获取当前 Span ID"""
    return _span_id.get()


def get_session_id() -> Optional[str]:
    """获取当前会话 ID"""
    return _session_id.get()


def set_trace_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """设置追踪上下文"""
    if trace_id:
        _trace_id.set(trace_id)
    if span_id:
        _span_id.set(span_id)
    if session_id:
        _session_id.set(session_id)


def generate_trace_id() -> str:
    """生成新的追踪 ID"""
    return str(uuid.uuid4())


def generate_span_id() -> str:
    """生成新的 Span ID"""
    return str(uuid.uuid4())[:16]


class StructuredFormatter(logging.Formatter):
    """结构化 JSON 日志格式化器"""

    def __init__(
        self,
        service_name: str = "agent",
        include_trace: bool = True,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.service_name = service_name
        self.include_trace = include_trace

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }

        # 添加追踪信息
        if self.include_trace:
            trace_id = get_trace_id()
            span_id = get_span_id()
            session_id = get_session_id()
            
            if trace_id:
                log_data["trace_id"] = trace_id
            if span_id:
                log_data["span_id"] = span_id
            if session_id:
                log_data["session_id"] = session_id

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data["extra"] = record.extra_fields

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加代码位置
        log_data["location"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        return json.dumps(log_data, ensure_ascii=False, default=str)


class AgentLogger:
    """Agent 专用日志器"""

    def __init__(
        self,
        name: str = "agent",
        level: int = logging.INFO,
        service_name: str = "agent",
        json_output: bool = True,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers = []  # 清除已有处理器

        handler = logging.StreamHandler()
        
        if json_output:
            formatter = StructuredFormatter(service_name=service_name)
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def _log(
        self,
        level: int,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False,
    ) -> None:
        """内部日志方法"""
        record = self.logger.makeRecord(
            self.logger.name,
            level,
            "(unknown)",
            0,
            message,
            (),
            None if not exc_info else True,
        )
        if extra:
            record.extra_fields = extra
        self.logger.handle(record)

    def debug(self, message: str, **extra) -> None:
        """调试日志"""
        self._log(logging.DEBUG, message, extra if extra else None)

    def info(self, message: str, **extra) -> None:
        """信息日志"""
        self._log(logging.INFO, message, extra if extra else None)

    def warning(self, message: str, **extra) -> None:
        """警告日志"""
        self._log(logging.WARNING, message, extra if extra else None)

    def error(self, message: str, exc_info: bool = False, **extra) -> None:
        """错误日志"""
        self._log(logging.ERROR, message, extra if extra else None, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False, **extra) -> None:
        """严重错误日志"""
        self._log(logging.CRITICAL, message, extra if extra else None, exc_info=exc_info)


class Span:
    """追踪 Span"""

    def __init__(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        logger: Optional[AgentLogger] = None,
    ):
        self.name = name
        self.trace_id = trace_id or get_trace_id() or generate_trace_id()
        self.span_id = generate_span_id()
        self.parent_span_id = parent_span_id or get_span_id()
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.attributes: Dict[str, Any] = {}
        self.events: list = []
        self.status: str = "UNSET"
        self.logger = logger or AgentLogger()
        self._token_trace: Optional[Any] = None
        self._token_span: Optional[Any] = None

    def set_attribute(self, key: str, value: Any) -> "Span":
        """设置属性"""
        self.attributes[key] = value
        return self

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> "Span":
        """添加事件"""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })
        return self

    def set_status(self, status: str, description: Optional[str] = None) -> "Span":
        """设置状态 (OK, ERROR, UNSET)"""
        self.status = status
        if description:
            self.attributes["status_description"] = description
        return self

    def __enter__(self) -> "Span":
        self.start_time = time.perf_counter()
        self._token_trace = _trace_id.set(self.trace_id)
        self._token_span = _span_id.set(self.span_id)
        
        self.logger.debug(
            f"Span started: {self.name}",
            span_name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = time.perf_counter()
        duration_ms = (self.end_time - self.start_time) * 1000

        if exc_type:
            self.set_status("ERROR", str(exc_val))
        elif self.status == "UNSET":
            self.set_status("OK")

        self.logger.debug(
            f"Span ended: {self.name}",
            span_name=self.name,
            trace_id=self.trace_id,
            span_id=self.span_id,
            duration_ms=round(duration_ms, 2),
            status=self.status,
            attributes=self.attributes,
        )

        # 恢复上下文
        if self._token_trace:
            _trace_id.reset(self._token_trace)
        if self._token_span:
            _span_id.reset(self._token_span)


class Tracer:
    """追踪器"""

    def __init__(
        self,
        service_name: str = "agent",
        logger: Optional[AgentLogger] = None,
    ):
        self.service_name = service_name
        self.logger = logger or AgentLogger(name=service_name, service_name=service_name)

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
    ) -> Span:
        """创建新的 Span"""
        return Span(
            name=name,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            logger=self.logger,
        )

    def trace(self, name: Optional[str] = None) -> Callable:
        """追踪装饰器"""
        def decorator(func: Callable) -> Callable:
            span_name = name or func.__name__

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.start_span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    span.set_attribute("args_count", len(args))
                    span.set_attribute("kwargs_keys", list(kwargs.keys()))
                    try:
                        result = func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status("ERROR", str(e))
                        raise

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.start_span(span_name) as span:
                    span.set_attribute("function", func.__name__)
                    span.set_attribute("args_count", len(args))
                    span.set_attribute("kwargs_keys", list(kwargs.keys()))
                    try:
                        result = await func(*args, **kwargs)
                        return result
                    except Exception as e:
                        span.set_status("ERROR", str(e))
                        raise

            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator


# 默认实例
default_logger = AgentLogger()
default_tracer = Tracer()


# 便捷函数
def get_logger(name: str = "agent", **kwargs) -> AgentLogger:
    """获取日志器"""
    return AgentLogger(name=name, **kwargs)


def get_tracer(service_name: str = "agent", **kwargs) -> Tracer:
    """获取追踪器"""
    return Tracer(service_name=service_name, **kwargs)


__all__ = [
    # 上下文函数
    "get_trace_id",
    "get_span_id",
    "get_session_id",
    "set_trace_context",
    "generate_trace_id",
    "generate_span_id",
    # 类
    "StructuredFormatter",
    "AgentLogger",
    "Span",
    "Tracer",
    # 便捷函数
    "get_logger",
    "get_tracer",
    # 默认实例
    "default_logger",
    "default_tracer",
]
