"""
GoalEngine: Autonomous goal discovery and management.

Observes the environment (code, logs, metrics), identifies problems,
and generates goals without human input.
"""

from __future__ import annotations
import hashlib
import time
from pathlib import Path
from typing import Any, Callable, Optional

from agent.agi.base import AGIModule, Goal, Priority


class Observation:
    """An observation about the environment."""
    def __init__(self, source: str, category: str, data: Any, severity: float = 0.5):
        self.source = source          # e.g., "file_system", "git", "tests", "metrics"
        self.category = category      # e.g., "error", "warning", "opportunity", "drift"
        self.data = data
        self.severity = severity      # 0.0 (trivial) to 1.0 (critical)
        self.timestamp = time.time()

    def __repr__(self):
        return f"Observation({self.source}/{self.category}: severity={self.severity:.2f})"


class GoalEngine(AGIModule):
    """
    Autonomous goal generation engine.
    
    Capabilities:
    - Register environment observers (file changes, test failures, etc.)
    - Detect gaps between current state and ideal state
    - Generate and prioritize goals
    - Track goal lifecycle (pending → active → completed/failed)
    - Decompose high-level goals into sub-goals
    """

    def name(self) -> str:
        return "GoalEngine"

    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.goals: list[Goal] = []
        self.observers: list[Callable[[], list[Observation]]] = []
        self.ideal_state_rules: list[dict] = []
        self._load()

    def _load(self):
        """Load persisted goals."""
        saved = self.load_state("goals.json", [])
        self.goals = [Goal.from_dict(g) for g in saved]
        self.ideal_state_rules = self.load_state("ideal_state.json", self._default_ideal_state())

    def _save(self):
        """Persist goals."""
        self.save_state("goals.json", [g.to_dict() for g in self.goals])

    def _default_ideal_state(self) -> list[dict]:
        """Default rules for what 'ideal' looks like."""
        return [
            {"rule": "all_tests_pass", "description": "所有测试通过", "priority": "high"},
            {"rule": "no_security_vulnerabilities", "description": "无安全漏洞", "priority": "critical"},
            {"rule": "code_coverage_above_80", "description": "测试覆盖率>80%", "priority": "medium"},
            {"rule": "no_todo_comments", "description": "无遗留 TODO 注释", "priority": "low"},
            {"rule": "documentation_up_to_date", "description": "文档与代码同步", "priority": "medium"},
            {"rule": "no_deprecated_dependencies", "description": "无废弃依赖", "priority": "medium"},
            {"rule": "performance_within_bounds", "description": "性能指标在合理范围", "priority": "high"},
        ]

    # ─── Observer Management ───

    def register_observer(self, observer: Callable[[], list[Observation]]) -> None:
        """Register an environment observer function."""
        self.observers.append(observer)

    def observe_environment(self) -> list[Observation]:
        """Run all observers and collect observations."""
        all_observations = []
        for observer in self.observers:
            try:
                obs = observer()
                all_observations.extend(obs)
            except Exception as e:
                self.log(f"Observer error: {e}")
        return all_observations

    # ─── Goal Generation ───

    def detect_gaps(self, observations: list[Observation]) -> list[dict]:
        """Compare observations against ideal state to find gaps."""
        gaps = []
        for obs in observations:
            if obs.severity >= 0.3:  # threshold
                gap = {
                    "observation": obs,
                    "related_rules": [
                        r for r in self.ideal_state_rules
                        if self._rule_matches_observation(r, obs)
                    ],
                    "severity": obs.severity,
                }
                gaps.append(gap)
        return sorted(gaps, key=lambda g: g["severity"], reverse=True)

    def generate_goals(self, observations: Optional[list[Observation]] = None) -> list[Goal]:
        """Main entry: observe → detect gaps → create goals."""
        if observations is None:
            observations = self.observe_environment()

        gaps = self.detect_gaps(observations)
        new_goals = []

        for gap in gaps:
            obs = gap["observation"]
            # Avoid duplicate goals
            goal_hash = hashlib.md5(f"{obs.source}:{obs.category}:{obs.data}".encode()).hexdigest()[:8]
            if any(g.id == goal_hash and g.status in ("pending", "active") for g in self.goals):
                continue

            priority = self._severity_to_priority(obs.severity)
            goal = Goal(
                id=goal_hash,
                description=self._format_goal_description(obs),
                priority=priority,
                source="goal_engine",
                context={"observation_source": obs.source, "category": obs.category, "data": str(obs.data)[:500]},
            )
            new_goals.append(goal)
            self.goals.append(goal)

        self._save()
        return new_goals

    def get_next_goal(self) -> Optional[Goal]:
        """Get highest priority pending goal."""
        pending = [g for g in self.goals if g.status == "pending"]
        if not pending:
            return None
        pending.sort(key=lambda g: g.priority.value, reverse=True)
        return pending[0]

    def complete_goal(self, goal_id: str, success: bool = True) -> None:
        """Mark a goal as completed or failed."""
        for g in self.goals:
            if g.id == goal_id:
                g.status = "completed" if success else "failed"
                break
        self._save()

    def decompose_goal(self, goal: Goal, sub_descriptions: list[str]) -> list[Goal]:
        """Break a high-level goal into sub-goals."""
        sub_goals = []
        for i, desc in enumerate(sub_descriptions):
            sub = Goal(
                id=f"{goal.id}-sub{i}",
                description=desc,
                priority=goal.priority,
                source="goal_engine",
                context=goal.context,
                parent_goal=goal.id,
            )
            sub_goals.append(sub)
            self.goals.append(sub)
            goal.sub_goals.append(sub.id)
        self._save()
        return sub_goals

    # ─── Helpers ───

    def _rule_matches_observation(self, rule: dict, obs: Observation) -> bool:
        """Heuristic: does this ideal-state rule relate to this observation?"""
        rule_name = rule["rule"].lower()
        obs_text = f"{obs.source} {obs.category} {obs.data}".lower()

        keywords_map = {
            "all_tests_pass": ["test", "fail", "error", "assert"],
            "no_security_vulnerabilities": ["security", "vuln", "inject", "xss", "csrf"],
            "code_coverage_above_80": ["coverage", "uncovered", "untested"],
            "no_todo_comments": ["todo", "fixme", "hack", "xxx"],
            "documentation_up_to_date": ["doc", "readme", "outdated"],
            "no_deprecated_dependencies": ["deprecated", "outdated", "upgrade"],
            "performance_within_bounds": ["slow", "timeout", "memory", "cpu", "latency"],
        }

        keywords = keywords_map.get(rule_name, [])
        return any(kw in obs_text for kw in keywords)

    def _severity_to_priority(self, severity: float) -> Priority:
        if severity >= 0.9:
            return Priority.CRITICAL
        elif severity >= 0.7:
            return Priority.HIGH
        elif severity >= 0.4:
            return Priority.MEDIUM
        else:
            return Priority.LOW

    def _format_goal_description(self, obs: Observation) -> str:
        """Generate a human-readable goal description from observation."""
        templates = {
            "error": f"修复 {obs.source} 中发现的错误: {str(obs.data)[:100]}",
            "warning": f"处理 {obs.source} 警告: {str(obs.data)[:100]}",
            "opportunity": f"利用机会改进: {str(obs.data)[:100]}",
            "drift": f"{obs.source} 状态漂移，需要对齐: {str(obs.data)[:100]}",
        }
        return templates.get(obs.category, f"处理 {obs.source}/{obs.category}: {str(obs.data)[:100]}")

    # ─── Stats ───

    def stats(self) -> dict:
        """Get goal statistics."""
        return {
            "total": len(self.goals),
            "pending": len([g for g in self.goals if g.status == "pending"]),
            "active": len([g for g in self.goals if g.status == "active"]),
            "completed": len([g for g in self.goals if g.status == "completed"]),
            "failed": len([g for g in self.goals if g.status == "failed"]),
        }
