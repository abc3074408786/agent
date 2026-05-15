"""
优先级消息队列 - 参考 Claude Code 的 messageQueueManager.ts

特性:
- 3 级优先级: now > next > later
- 同级别 FIFO
- 批量出队 (同 mode 的命令合并)
- 过滤器出队 (按条件选择性消费)
- 订阅/通知机制
"""

import asyncio
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass, field
from enum import IntEnum
from collections import deque
from threading import Lock
from datetime import datetime, timezone

from agent.observability import get_logger

logger = get_logger("priority_queue")

T = TypeVar("T")


class Priority(IntEnum):
    """优先级 (数字越小优先级越高)"""
    NOW = 0      # 立即处理 (用户中断)
    NEXT = 1     # 下一个处理 (用户输入)
    LATER = 2    # 稍后处理 (系统通知, 任务通知)


@dataclass
class QueueItem(Generic[T]):
    """队列项"""
    value: T
    priority: Priority = Priority.NEXT
    mode: str = "default"        # 消息模式 (prompt, bash, notification)
    agent_id: Optional[str] = None  # 所属 agent (None = 主线程)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


class PriorityMessageQueue(Generic[T]):
    """
    优先级消息队列
    
    参考 Claude Code 的实现:
    - 3 级优先级 FIFO
    - 支持过滤器出队
    - 批量出队相同 mode 的项
    - 订阅者通知
    """

    def __init__(self):
        self._queue: List[QueueItem[T]] = []
        self._lock = Lock()
        self._subscribers: List[Callable[[], None]] = []
        self._event = asyncio.Event()

    # ============ 读操作 ============

    @property
    def length(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    def peek(
        self, filter_fn: Optional[Callable[[QueueItem[T]], bool]] = None
    ) -> Optional[QueueItem[T]]:
        """查看最高优先级的项 (不移除)"""
        with self._lock:
            best: Optional[QueueItem[T]] = None
            best_priority = Priority.LATER + 1

            for item in self._queue:
                if filter_fn and not filter_fn(item):
                    continue
                if item.priority < best_priority:
                    best = item
                    best_priority = item.priority

            return best

    def get_all(self) -> List[QueueItem[T]]:
        """获取队列副本"""
        with self._lock:
            return list(self._queue)

    # ============ 写操作 ============

    def enqueue(
        self,
        value: T,
        priority: Priority = Priority.NEXT,
        mode: str = "default",
        agent_id: Optional[str] = None,
        **metadata,
    ) -> None:
        """入队"""
        item = QueueItem(
            value=value,
            priority=priority,
            mode=mode,
            agent_id=agent_id,
            metadata=metadata,
        )
        with self._lock:
            self._queue.append(item)
        self._notify()
        logger.debug(f"Enqueued item", priority=priority.name, mode=mode)

    def enqueue_notification(self, value: T, **metadata) -> None:
        """入队通知 (默认 LATER 优先级，不饿死用户输入)"""
        self.enqueue(value, priority=Priority.LATER, mode="notification", **metadata)

    def dequeue(
        self, filter_fn: Optional[Callable[[QueueItem[T]], bool]] = None
    ) -> Optional[QueueItem[T]]:
        """
        出队最高优先级项
        
        参考 Claude Code: 线性扫描找最高优先级，同级别 FIFO
        """
        with self._lock:
            best_idx = -1
            best_priority = Priority.LATER + 1

            for i, item in enumerate(self._queue):
                if filter_fn and not filter_fn(item):
                    continue
                if item.priority < best_priority:
                    best_idx = i
                    best_priority = item.priority

            if best_idx == -1:
                return None

            item = self._queue.pop(best_idx)

        self._notify()
        return item

    def dequeue_all_matching(
        self, filter_fn: Callable[[QueueItem[T]], bool]
    ) -> List[QueueItem[T]]:
        """
        批量出队所有匹配的项
        
        参考 Claude Code: dequeueAllMatching()
        用于将相同 mode 的命令合并处理
        """
        with self._lock:
            matching = []
            remaining = []

            for item in self._queue:
                if filter_fn(item):
                    matching.append(item)
                else:
                    remaining.append(item)

            self._queue = remaining

        if matching:
            self._notify()

        return matching

    def remove(
        self, filter_fn: Callable[[QueueItem[T]], bool]
    ) -> List[QueueItem[T]]:
        """移除匹配项"""
        return self.dequeue_all_matching(filter_fn)

    def clear(self) -> int:
        """清空队列"""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
        self._notify()
        return count

    # ============ 批量处理 ============

    def dequeue_batch_by_mode(
        self,
        main_thread_only: bool = True,
    ) -> List[QueueItem[T]]:
        """
        按模式批量出队
        
        参考 Claude Code 的 processQueueIfReady():
        - 找到最高优先级的项
        - 出队所有相同 mode 的项
        """
        # 先 peek 最高优先级
        def is_main(item: QueueItem[T]) -> bool:
            return item.agent_id is None if main_thread_only else True

        next_item = self.peek(is_main)
        if not next_item:
            return []

        target_mode = next_item.mode

        # 出队所有同模式的项
        return self.dequeue_all_matching(
            lambda item: is_main(item) and item.mode == target_mode
        )

    # ============ 异步等待 ============

    async def wait_for_item(self, timeout: Optional[float] = None) -> bool:
        """等待新项入队"""
        self._event.clear()
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    # ============ 订阅 ============

    def subscribe(self, callback: Callable[[], None]) -> Callable[[], None]:
        """订阅队列变化"""
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def _notify(self) -> None:
        """通知所有订阅者"""
        self._event.set()
        for cb in self._subscribers:
            try:
                cb()
            except Exception:
                pass


__all__ = [
    "Priority",
    "QueueItem",
    "PriorityMessageQueue",
]
