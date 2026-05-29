"""Prefrontal Cortex - Planning + Working Memory (Miller's 7±2 Law)"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class WorkingMemoryChunk:
    """A chunk in working memory with attention decay."""
    id: str
    content: Any
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0

    @property
    def attention_weight(self) -> float:
        """Decay over time, boosted by importance and access."""
        age = time.time() - self.last_accessed
        decay = max(0.01, 1.0 - (age / 300))  # 5 min half-life
        return decay * self.importance * (1 + 0.1 * self.access_count)


class PrefrontalCortex:
    """
    Planning + Working Memory.
    
    Principles:
    - Capacity limit: 7±2 chunks (forces abstraction)
    - Attention decay: unused items fade
    - Compression: when full, least important items get chunked together
    - Goal stack: maintains current goal hierarchy
    """

    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.working_memory: list[WorkingMemoryChunk] = []
        self.goal_stack: list[dict] = []  # [{goal, priority, progress}]
        self.plan_buffer: list[str] = []  # current multi-step plan

    def attend(self, id: str, content: Any, importance: float = 0.5) -> bool:
        """
        Add item to working memory. Returns True if added, False if filtered.
        If at capacity, compresses or evicts lowest-weight item.
        """
        # Check if already in WM
        existing = next((c for c in self.working_memory if c.id == id), None)
        if existing:
            existing.last_accessed = time.time()
            existing.access_count += 1
            existing.content = content
            return True

        # At capacity: evict or compress
        if len(self.working_memory) >= self.capacity:
            self._compress_or_evict()

        chunk = WorkingMemoryChunk(id=id, content=content, importance=importance)
        self.working_memory.append(chunk)
        return True

    def recall(self, id: str) -> Optional[Any]:
        """Retrieve from working memory (boosts attention)."""
        chunk = next((c for c in self.working_memory if c.id == id), None)
        if chunk:
            chunk.last_accessed = time.time()
            chunk.access_count += 1
            return chunk.content
        return None

    def get_active_context(self) -> list[dict]:
        """Get all active working memory items, sorted by attention weight."""
        self._decay_check()
        items = sorted(self.working_memory, key=lambda c: c.attention_weight, reverse=True)
        return [{"id": c.id, "content": c.content, "weight": c.attention_weight} for c in items]

    def push_goal(self, goal: str, priority: float = 0.5) -> None:
        """Push a goal onto the goal stack."""
        self.goal_stack.append({"goal": goal, "priority": priority, "progress": 0.0, "started": time.time()})

    def pop_goal(self) -> Optional[dict]:
        """Complete current goal."""
        return self.goal_stack.pop() if self.goal_stack else None

    def current_goal(self) -> Optional[str]:
        """What are we working on right now?"""
        return self.goal_stack[-1]["goal"] if self.goal_stack else None

    def set_plan(self, steps: list[str]) -> None:
        """Set a multi-step plan."""
        self.plan_buffer = steps

    def next_step(self) -> Optional[str]:
        """Get next step in current plan."""
        return self.plan_buffer.pop(0) if self.plan_buffer else None

    def _compress_or_evict(self) -> None:
        """When at capacity, evict lowest-weight item."""
        if not self.working_memory:
            return
        self.working_memory.sort(key=lambda c: c.attention_weight)
        evicted = self.working_memory.pop(0)
        # Could archive evicted item to long-term memory here

    def _decay_check(self) -> None:
        """Remove items that have fully decayed."""
        self.working_memory = [c for c in self.working_memory if c.attention_weight > 0.05]
