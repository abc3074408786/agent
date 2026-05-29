"""
Base classes and shared types for all AGI modules.
"""

from __future__ import annotations
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Priority(Enum):
    CRITICAL = 4
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    IDLE = 0


@dataclass
class Goal:
    """A self-generated goal with priority and context."""
    id: str
    description: str
    priority: Priority = Priority.MEDIUM
    source: str = ""  # which module generated this goal
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None  # optional deadline timestamp
    status: str = "pending"  # pending | active | completed | failed | abandoned
    sub_goals: list[str] = field(default_factory=list)
    parent_goal: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        data["priority"] = Priority(data.get("priority", 2))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Experience:
    """A recorded experience (action + context + result + reward)."""
    id: str
    action: str
    context: dict = field(default_factory=dict)
    result: Any = None
    reward: float = 0.0  # -1.0 to 1.0
    timestamp: float = field(default_factory=time.time)
    domain: str = ""  # e.g., "python", "frontend", "devops"
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Experience":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class CausalLink:
    """A cause-effect relationship with confidence."""
    cause: str
    effect: str
    confidence: float = 0.5  # 0.0 to 1.0
    observations: int = 0
    conditions: list[str] = field(default_factory=list)  # preconditions
    domain: str = ""
    last_observed: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CausalLink":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Pattern:
    """An abstracted pattern extracted from experiences."""
    id: str
    description: str
    abstract_rule: str  # generalized rule
    source_domain: str  # domain where it was learned
    applicable_domains: list[str] = field(default_factory=list)
    confidence: float = 0.5
    usage_count: int = 0
    success_rate: float = 0.0
    examples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class EvaluationResult:
    """Result of self-evaluation."""
    score: float  # 0.0 to 1.0
    confidence: float  # how confident the evaluator is
    method: str  # which evaluation method was used
    details: dict = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)


class AGIModule(ABC):
    """Base class for all AGI cognitive modules."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def name(self) -> str:
        """Module name for identification."""
        ...

    def save_state(self, filename: str, data: Any) -> None:
        """Persist module state to disk."""
        filepath = self.data_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def load_state(self, filename: str, default: Any = None) -> Any:
        """Load module state from disk."""
        filepath = self.data_dir / filename
        if not filepath.exists():
            return default if default is not None else {}
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    def log(self, message: str) -> None:
        """Simple logging."""
        print(f"[{self.name()}] {message}")
