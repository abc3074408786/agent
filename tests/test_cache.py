"""测试 algorithms/cache.py"""
import pytest
import asyncio
import time
from agent.algorithms.cache import (
    SWRCache,
    LRUCache,
    AsyncDeduplicatedCache,
    swr_cached,
    lru_cached,
)


class TestLRUCache:
    def test_basic_put_get(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.get("a") == 1
        assert cache.get("b") == 2

    def test_eviction(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)  # 驱逐 "a"
        assert cache.get("a") is None
        assert cache.get("b") == 2
        assert cache.get("c") == 3

    def test_access_updates_order(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")  # 更新 "a" 为最近使用
        cache.put("c", 3)  # 驱逐 "b" (最少使用)
        assert cache.get("a") == 1
        assert cache.get("b") is None
        assert cache.get("c") == 3

    def test_peek_no_update(self):
        cache = LRUCache(max_size=2)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.peek("a")  # peek 不更新顺序
        cache.put("c", 3)  # 应该驱逐 "a"
        assert cache.peek("a") is None

    def test_get_or_compute(self):
        cache = LRUCache(max_size=3)
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return 42

        result1 = cache.get_or_compute("key", compute)
        result2 = cache.get_or_compute("key", compute)
        assert result1 == 42
        assert result2 == 42
        assert call_count == 1  # 只计算一次

    def test_delete(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        assert cache.delete("a") is True
        assert cache.get("a") is None
        assert cache.delete("nonexistent") is False

    def test_clear(self):
        cache = LRUCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_size(self):
        cache = LRUCache(max_size=5)
        assert cache.size == 0
        cache.put("a", 1)
        cache.put("b", 2)
        assert cache.size == 2


class TestSWRCache:
    def test_basic_get(self):
        cache = SWRCache(ttl_seconds=60)
        result = cache.get("key", lambda: 42)
        assert result == 42

    def test_cache_hit(self):
        cache = SWRCache(ttl_seconds=60)
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return "value"

        cache.get("key", compute)
        cache.get("key", compute)
        assert call_count == 1

    def test_invalidate(self):
        cache = SWRCache(ttl_seconds=60)
        cache.get("key", lambda: "v1")
        cache.invalidate("key")
        result = cache.get("key", lambda: "v2")
        assert result == "v2"

    def test_clear(self):
        cache = SWRCache(ttl_seconds=60)
        cache.get("a", lambda: 1)
        cache.get("b", lambda: 2)
        cache.clear()
        assert cache.size == 0


class TestAsyncDeduplicatedCache:
    @pytest.mark.asyncio
    async def test_basic_get(self):
        cache = AsyncDeduplicatedCache(ttl_seconds=60)
        result = await cache.get("key", lambda: asyncio.coroutine(lambda: 42)())
        assert result == 42

    @pytest.mark.asyncio
    async def test_deduplication(self):
        cache = AsyncDeduplicatedCache(ttl_seconds=60)
        call_count = 0

        async def slow_compute():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return "result"

        # 并发请求同一个 key
        results = await asyncio.gather(
            cache.get("key", slow_compute),
            cache.get("key", slow_compute),
            cache.get("key", slow_compute),
        )
        assert all(r == "result" for r in results)
        assert call_count == 1  # 只执行一次


class TestDecorators:
    def test_lru_cached_decorator(self):
        call_count = 0

        @lru_cached(max_size=2)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(1) == 2
        assert compute(1) == 2  # cached
        assert call_count == 1

        assert compute(2) == 4
        assert compute(3) == 6  # evicts 1
        assert call_count == 3

    def test_swr_cached_decorator(self):
        call_count = 0

        @swr_cached(ttl_seconds=60)
        def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert compute(5) == 10
        assert compute(5) == 10  # cached
        assert call_count == 1
