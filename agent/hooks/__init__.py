"""
Hooks System - 生命周期钩子

提供可扩展的事件钩子系统:
- pre_query: 查询前
- post_query: 查询后
- pre_tool_use: 工具调用前
- post_tool_use: 工具调用后
- on_error: 错误时
- on_stream_event: 流事件
- on_compact: 上下文压缩时
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field

from agent.observability import get_logger

logger = get_logger("hooks")


class HookEvent(str, Enum):
    """钩子事件类型"""
    PRE_QUERY = "pre_query"
    POST_QUERY = "post_query"
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    ON_ERROR = "on_error"
    ON_STREAM_EVENT = "on_stream_event"
    ON_COMPACT = "on_compact"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"
    ON_PERMISSION_CHECK = "on_permission_check"


@dataclass
class HookContext:
    """钩子上下文"""
    event: HookEvent
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    # 控制标志
    cancelled: bool = False
    modified_data: Optional[Dict[str, Any]] = None


# 钩子函数类型
HookFn = Callable[[HookContext], Any]
AsyncHookFn = Callable[[HookContext], Any]


@dataclass
class HookRegistration:
    """钩子注册信息"""
    event: HookEvent
    handler: Union[HookFn, AsyncHookFn]
    name: str = ""
    priority: int = 100
    is_async: bool = False


class HookManager:
    """
    钩子管理器

    管理生命周期钩子的注册和触发
    """

    def __init__(self):
        self._hooks: Dict[HookEvent, List[HookRegistration]] = {
            event: [] for event in HookEvent
        }

    def register(
        self,
        event: HookEvent,
        handler: Union[HookFn, AsyncHookFn],
        name: Optional[str] = None,
        priority: int = 100,
    ) -> None:
        """注册钩子"""
        is_async = asyncio.iscoroutinefunction(handler)
        registration = HookRegistration(
            event=event,
            handler=handler,
            name=name or handler.__name__,
            priority=priority,
            is_async=is_async,
        )
        self._hooks[event].append(registration)
        self._hooks[event].sort(key=lambda h: h.priority)
        logger.debug(f"Registered hook: {registration.name} for {event.value}")

    def unregister(self, event: HookEvent, name: str) -> bool:
        """注销钩子"""
        before = len(self._hooks[event])
        self._hooks[event] = [h for h in self._hooks[event] if h.name != name]
        return len(self._hooks[event]) < before

    async def trigger(self, event: HookEvent, data: Optional[Dict[str, Any]] = None, **kwargs) -> HookContext:
        """
        触发钩子

        Args:
            event: 事件类型
            data: 事件数据
            **kwargs: 额外的上下文参数

        Returns:
            HookContext (可能被修改)
        """
        context = HookContext(
            event=event,
            data=data or {},
            **kwargs,
        )

        for registration in self._hooks[event]:
            if context.cancelled:
                break
            try:
                if registration.is_async:
                    await registration.handler(context)
                else:
                    registration.handler(context)
            except Exception as e:
                logger.error(
                    f"Hook error: {registration.name}",
                    event=event.value,
                    error=str(e),
                )

        return context

    def on(self, event: HookEvent, priority: int = 100):
        """装饰器方式注册钩子"""
        def decorator(func):
            self.register(event, func, priority=priority)
            return func
        return decorator

    def clear(self, event: Optional[HookEvent] = None) -> None:
        """清除钩子"""
        if event:
            self._hooks[event].clear()
        else:
            for e in HookEvent:
                self._hooks[e].clear()


# 全局钩子管理器
hook_manager = HookManager()


# 便捷装饰器
def on_pre_query(priority: int = 100):
    return hook_manager.on(HookEvent.PRE_QUERY, priority)

def on_post_query(priority: int = 100):
    return hook_manager.on(HookEvent.POST_QUERY, priority)

def on_pre_tool_use(priority: int = 100):
    return hook_manager.on(HookEvent.PRE_TOOL_USE, priority)

def on_post_tool_use(priority: int = 100):
    return hook_manager.on(HookEvent.POST_TOOL_USE, priority)

def on_error(priority: int = 100):
    return hook_manager.on(HookEvent.ON_ERROR, priority)


__all__ = [
    "HookEvent",
    "HookContext",
    "HookRegistration",
    "HookManager",
    "hook_manager",
    # 装饰器
    "on_pre_query",
    "on_post_query",
    "on_pre_tool_use",
    "on_post_tool_use",
    "on_error",
]
