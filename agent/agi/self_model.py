"""
SelfModel: Agent's understanding of itself.

Two layers:
1. Auto-stats (bottom): pure computation, updates every post_tool, zero cost
2. Reflection (top): periodic deep self-analysis via Skill/LLM

Provides: strengths, weaknesses, personality, state, growth trends.
Injected into LLM context so Agent naturally adjusts behavior.
"""

from __future__ import annotations
import json
import time
from pathlib import Path


class SelfModel:
    def __init__(self, data_dir: str = ".agi/self_model"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.domain_stats: dict[str, dict] = {}
        self.behavior_patterns: dict[str, int] = {}
        self.current_state: str = "neutral"
        self.consecutive_success: int = 0
        self.consecutive_fail: int = 0
        self.total_actions: int = 0
        self._load()

    def _load(self):
        path = self.data_dir / "self_model.json"
        if path.exists():
            d = json.loads(path.read_text())
            self.domain_stats = d.get("domain_stats", {})
            self.behavior_patterns = d.get("behavior_patterns", {})
            self.current_state = d.get("current_state", "neutral")
            self.consecutive_success = d.get("consecutive_success", 0)
            self.consecutive_fail = d.get("consecutive_fail", 0)
            self.total_actions = d.get("total_actions", 0)

    def _save(self):
        (self.data_dir / "self_model.json").write_text(json.dumps({
            "domain_stats": self.domain_stats, "behavior_patterns": self.behavior_patterns,
            "current_state": self.current_state, "consecutive_success": self.consecutive_success,
            "consecutive_fail": self.consecutive_fail, "total_actions": self.total_actions,
        }, ensure_ascii=False, indent=2))

    def record_action(self, domain: str, action: str, success: bool) -> None:
        self.total_actions += 1
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {"success": 0, "fail": 0, "total": 0, "recent": []}
        s = self.domain_stats[domain]
        s["total"] += 1
        s["success" if success else "fail"] += 1
        s["recent"].append(success)
        if len(s["recent"]) > 20:
            s["recent"] = s["recent"][-20:]
        if success:
            self.consecutive_success += 1; self.consecutive_fail = 0
        else:
            self.consecutive_fail += 1; self.consecutive_success = 0
        self._update_state()
        self.behavior_patterns[action] = self.behavior_patterns.get(action, 0) + 1
        self._save()

    def _update_state(self):
        if self.consecutive_success >= 5: self.current_state = "confident"
        elif self.consecutive_success >= 3: self.current_state = "positive"
        elif self.consecutive_fail >= 3: self.current_state = "cautious"
        elif self.consecutive_fail >= 5: self.current_state = "uncertain"
        else: self.current_state = "neutral"

    def get_strengths(self) -> list[dict]:
        return [{"domain": d, "rate": s["success"]/s["total"]} for d, s in self.domain_stats.items() if s["total"] >= 5 and s["success"]/s["total"] >= 0.75]

    def get_weaknesses(self) -> list[dict]:
        return [{"domain": d, "rate": s["success"]/s["total"]} for d, s in self.domain_stats.items() if s["total"] >= 3 and s["success"]/s["total"] <= 0.5]

    def get_confidence(self, domain: str = "") -> float:
        if domain and domain in self.domain_stats:
            s = self.domain_stats[domain]
            return s["success"] / max(s["total"], 1)
        return {"confident": 0.9, "positive": 0.75, "cautious": 0.4, "uncertain": 0.25}.get(self.current_state, 0.6)

    def to_context_string(self) -> str:
        parts = []
        strengths = self.get_strengths()
        if strengths:
            parts.append("擅长: " + ", ".join(f"{s['domain']}({s['rate']:.0%})" for s in strengths[:3]))
        weaknesses = self.get_weaknesses()
        if weaknesses:
            parts.append("不擅长: " + ", ".join(f"{w['domain']}({w['rate']:.0%})" for w in weaknesses[:2]))
        states = {"confident": "自信", "positive": "积极", "neutral": "正常", "cautious": "谨慎", "uncertain": "不确定"}
        parts.append(f"状态: {states.get(self.current_state, self.current_state)}")
        parts.append(f"经验: {self.total_actions}次")
        return " | ".join(parts)
