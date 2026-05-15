"""测试 algorithms/priority_queue.py"""
import pytest
from agent.algorithms.priority_queue import (
    Priority,
    QueueItem,
    PriorityMessageQueue,
)


class TestPriorityQueue:
    def test_basic_enqueue_dequeue(self):
        q = PriorityMessageQueue()
        q.enqueue("hello")
        item = q.dequeue()
        assert item is not None
        assert item.value == "hello"

    def test_empty_dequeue(self):
        q = PriorityMessageQueue()
        assert q.dequeue() is None

    def test_priority_ordering(self):
        q = PriorityMessageQueue()
        q.enqueue("later", priority=Priority.LATER)
        q.enqueue("now", priority=Priority.NOW)
        q.enqueue("next", priority=Priority.NEXT)

        assert q.dequeue().value == "now"
        assert q.dequeue().value == "next"
        assert q.dequeue().value == "later"

    def test_fifo_same_priority(self):
        q = PriorityMessageQueue()
        q.enqueue("first", priority=Priority.NEXT)
        q.enqueue("second", priority=Priority.NEXT)
        q.enqueue("third", priority=Priority.NEXT)

        assert q.dequeue().value == "first"
        assert q.dequeue().value == "second"
        assert q.dequeue().value == "third"

    def test_filter_dequeue(self):
        q = PriorityMessageQueue()
        q.enqueue("agent_msg", agent_id="agent-1")
        q.enqueue("main_msg", agent_id=None)

        # 只出队主线程消息
        item = q.dequeue(filter_fn=lambda i: i.agent_id is None)
        assert item.value == "main_msg"
        assert q.length == 1

    def test_dequeue_all_matching(self):
        q = PriorityMessageQueue()
        q.enqueue("a", mode="prompt")
        q.enqueue("b", mode="prompt")
        q.enqueue("c", mode="notification")

        matched = q.dequeue_all_matching(lambda i: i.mode == "prompt")
        assert len(matched) == 2
        assert q.length == 1

    def test_batch_by_mode(self):
        q = PriorityMessageQueue()
        q.enqueue("m1", mode="prompt", priority=Priority.NEXT)
        q.enqueue("m2", mode="prompt", priority=Priority.NEXT)
        q.enqueue("n1", mode="notification", priority=Priority.LATER)

        batch = q.dequeue_batch_by_mode(main_thread_only=False)
        assert len(batch) == 2
        assert all(i.mode == "prompt" for i in batch)

    def test_peek(self):
        q = PriorityMessageQueue()
        q.enqueue("hello", priority=Priority.NOW)
        
        item = q.peek()
        assert item is not None
        assert item.value == "hello"
        assert q.length == 1  # 没有移除

    def test_clear(self):
        q = PriorityMessageQueue()
        q.enqueue("a")
        q.enqueue("b")
        count = q.clear()
        assert count == 2
        assert q.is_empty

    def test_notification_priority(self):
        q = PriorityMessageQueue()
        q.enqueue_notification("system msg")
        q.enqueue("user msg", priority=Priority.NEXT)

        # 用户消息先出队
        assert q.dequeue().value == "user msg"
        assert q.dequeue().value == "system msg"

    def test_subscribe(self):
        q = PriorityMessageQueue()
        notifications = []
        q.subscribe(lambda: notifications.append(1))
        
        q.enqueue("hello")
        assert len(notifications) == 1
