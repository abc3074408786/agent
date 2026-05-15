"""
高级缓存策略 - 参考 Claude Code 的 memoize.ts

实现:
- Stale-While-Revalidate (SWR): 返回旧值，后台刷新
- LRU 缓存: 有界缓存，防止内存无限增长
- Cold-miss 去重: 并发请求时只执行一次
- TTL 缓存: 基于时间的过期
"""

import asyncio
import time
import hashlib
import json
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Optional,
    TypeVar,
    Awaitable,
    Tuple,
)
from dataclasses import dataclass, field
from collections import OrderedDict
from functools import wraps
from threading import Lock

import logging; logger = logging.getLogger(__name__)



T = TypeVar("T")
K = TypeVar("K")


# ============ TTL + Stale-While-Revalidate 缓存 ============

@dataclass
class CacheEntry(Generic[T]):
    """缓存条目"""
    value: T
    timestamp: float
    refreshing: bool = False


class SWRCache(Generic[T]):
    """
    Stale-While-Revalidate 缓存
    
    参考 Claude Code: memoizeWithTTL()
    
    行为:
    - 缓存未命中: 同步计算并缓存
    - 缓存新鲜: 直接返回
    - 缓存过期: 立即返回旧值，后台异步刷新
    
    这确保用户永远不会因缓存刷新而等待
    """

    def __init__(self, ttl_seconds: float = 300.0):
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(
        self,
        key: str,
        compute_fn: Callable[[], T],
    ) -> T:
        """
        获取缓存值 (同步版本)
        
        如果缓存过期，返回旧值并后台刷新
        """
        now = time.time()

        with self._lock:
            entry = self._cache.get(key)

        # 缓存未命中
        if entry is None:
            value = compute_fn()
            with self._lock:
                self._cache[key] = CacheEntry(value=value, timestamp=now)
            return value

        # 缓存过期且未在刷新中
        if now - entry.timestamp > self._ttl and not entry.refreshing:
            entry.refreshing = True

            # 后台刷新 (非阻塞)
            import threading
            def _refresh():
                try:
                    new_value = compute_fn()
                    with self._lock:
                        # Identity guard: 确保条目未被 clear
                        if self._cache.get(key) is entry:
                            self._cache[key] = CacheEntry(
                                value=new_value, timestamp=time.time()
                            )
                except Exception as e:
                    logger.error(f"SWR cache refresh failed: {e}")
                    with self._lock:
                        if self._cache.get(key) is entry:
                            del self._cache[key]

            threading.Thread(target=_refresh, daemon=True).start()

            # 返回旧值
            return entry.value

        return entry.value

    async def aget(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[T]],
    ) -> T:
        """
        获取缓存值 (异步版本)
        
        参考 Claude Code: memoizeWithTTLAsync()
        """
        now = time.time()
        entry = self._cache.get(key)

        # 缓存未命中 + Cold-miss 去重
        if entry is None:
            value = await compute_fn()
            self._cache[key] = CacheEntry(value=value, timestamp=now)
            return value

        # 缓存过期且未在刷新中
        if now - entry.timestamp > self._ttl and not entry.refreshing:
            entry.refreshing = True

            # 后台异步刷新
            async def _refresh():
                try:
                    new_value = await compute_fn()
                    if self._cache.get(key) is entry:
                        self._cache[key] = CacheEntry(
                            value=new_value, timestamp=time.time()
                        )
                except Exception as e:
                    logger.error(f"SWR async cache refresh failed: {e}")
                    if self._cache.get(key) is entry:
                        del self._cache[key]

            asyncio.create_task(_refresh())

            # 返回旧值
            return entry.value

        return entry.value

    def invalidate(self, key: str) -> None:
        """使缓存条目失效"""
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """清除所有缓存"""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# ============ LRU 缓存 ============

class LRUCache(Generic[T]):
    """
    LRU (Least Recently Used) 缓存
    
    参考 Claude Code: memoizeWithLRU()
    
    防止无限内存增长，驱逐最近最少使用的条目
    """

    def __init__(self, max_size: int = 100):
        self._max_size = max_size
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[T]:
        """获取值 (更新访问顺序)"""
        with self._lock:
            if key in self._cache:
                # 移到末尾 (最近使用)
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def peek(self, key: str) -> Optional[T]:
        """获取值 (不更新访问顺序)"""
        with self._lock:
            return self._cache.get(key)

    def put(self, key: str, value: T) -> None:
        """放入值"""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                if len(self._cache) >= self._max_size:
                    # 驱逐最老的 (第一个)
                    self._cache.popitem(last=False)
                self._cache[key] = value

    def get_or_compute(self, key: str, compute_fn: Callable[[], T]) -> T:
        """获取或计算"""
        result = self.get(key)
        if result is not None:
            return result
        value = compute_fn()
        self.put(key, value)
        return value

    def delete(self, key: str) -> bool:
        """删除"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def has(self, key: str) -> bool:
        """检查是否存在"""
        return key in self._cache

    def clear(self) -> None:
        """清除"""
        with self._lock:
            self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# ============ Cold-Miss 去重异步缓存 ============

class AsyncDeduplicatedCache(Generic[T]):
    """
    异步去重缓存
    
    参考 Claude Code: memoizeWithTTLAsync 的 inFlight 机制
    
    当多个协程同时请求同一个 key 时，只执行一次计算
    """

    def __init__(self, ttl_seconds: float = 300.0):
        self._cache: Dict[str, CacheEntry[T]] = {}
        self._in_flight: Dict[str, asyncio.Future] = {}
        self._ttl = ttl_seconds

    async def get(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[T]],
    ) -> T:
        """获取值，并发请求自动去重"""
        now = time.time()
        entry = self._cache.get(key)

        # 缓存命中且新鲜
        if entry and now - entry.timestamp <= self._ttl:
            return entry.value

        # 检查是否有正在进行的请求
        if key in self._in_flight:
            return await self._in_flight[key]

        # 创建新请求
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        self._in_flight[key] = future

        try:
            value = await compute_fn()
            self._cache[key] = CacheEntry(value=value, timestamp=now)
            future.set_result(value)
            return value
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            self._in_flight.pop(key, None)

    def clear(self) -> None:
        self._cache.clear()
        self._in_flight.clear()


# ============ 装饰器 ============

def swr_cached(ttl_seconds: float = 300.0, key_fn: Optional[Callable] = None):
    """
    SWR 缓存装饰器

    Example:
        @swr_cached(ttl_seconds=60)
        def get_model_config(name: str) -> dict:
            ...
    """
    cache = SWRCache(ttl_seconds=ttl_seconds)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = hashlib.md5(
                    json.dumps((args, sorted(kwargs.items())), default=str).encode()
                ).hexdigest()
            return cache.get(key, lambda: func(*args, **kwargs))

        wrapper.cache = cache
        return wrapper

    return decorator


def lru_cached(max_size: int = 100, key_fn: Optional[Callable] = None):
    """
    LRU 缓存装饰器

    Example:
        @lru_cached(max_size=200)
        def process_message(msg_id: str) -> dict:
            ...
    """
    cache = LRUCache(max_size=max_size)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_fn:
                key = key_fn(*args, **kwargs)
            else:
                key = hashlib.md5(
                    json.dumps((args, sorted(kwargs.items())), default=str).encode()
                ).hexdigest()
            return cache.get_or_compute(key, lambda: func(*args, **kwargs))

        wrapper.cache = cache
        return wrapper

    return decorator


__all__ = [
    "CacheEntry",
    "SWRCache",
    "LRUCache",
    "AsyncDeduplicatedCache",
    "swr_cached",
    "lru_cached",
]
