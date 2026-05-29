"""Thalamus - Information Router & Attention Gate"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    """A routed signal with priority and metadata."""
    source: str
    content: Any
    priority: float = 0.5  # 0-1
    timestamp: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)


class Thalamus:
    """
    Brain's relay station. Routes information to appropriate modules.
    Implements attention gating: only high-priority signals pass through.
    
    Principles:
    - Attention threshold: low-priority signals are filtered
    - Urgency boost: danger signals bypass threshold
    - Habituation: repeated identical signals get suppressed
    """

    def __init__(self, attention_threshold: float = 0.3):
        self.attention_threshold = attention_threshold
        self.recent_signals: list[Signal] = []
        self.suppressed_patterns: dict[str, int] = {}  # pattern → count
        self.max_recent = 50

    def route(self, source: str, content: Any, priority: float = 0.5, tags: list[str] | None = None) -> Signal | None:
        """
        Route a signal. Returns None if filtered by attention gate.
        """
        signal = Signal(source=source, content=content, priority=priority, tags=tags or [])

        # Urgency bypass: danger signals always pass
        if "danger" in (tags or []) or "error" in (tags or []) or priority >= 0.9:
            self._record(signal)
            return signal

        # Habituation: suppress repeated identical signals
        pattern_key = f"{source}:{str(content)[:50]}"
        self.suppressed_patterns[pattern_key] = self.suppressed_patterns.get(pattern_key, 0) + 1
        if self.suppressed_patterns[pattern_key] > 5:
            return None  # habituated, ignore

        # Attention gate
        if priority < self.attention_threshold:
            return None

        self._record(signal)
        return signal

    def get_focus(self) -> list[Signal]:
        """Get current attention focus (top signals)."""
        return sorted(self.recent_signals, key=lambda s: s.priority, reverse=True)[:5]

    def adjust_threshold(self, delta: float) -> None:
        """Adjust attention threshold (fatigue raises it, rest lowers it)."""
        self.attention_threshold = max(0.1, min(0.9, self.attention_threshold + delta))

    def reset_habituation(self) -> None:
        """Reset habituation (like waking up refreshed)."""
        self.suppressed_patterns.clear()

    def _record(self, signal: Signal) -> None:
        self.recent_signals.append(signal)
        if len(self.recent_signals) > self.max_recent:
            self.recent_signals = self.recent_signals[-self.max_recent:]
