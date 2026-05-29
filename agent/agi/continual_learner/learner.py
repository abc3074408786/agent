"""
ContinualLearner: Experience → Pattern Extraction → Decision Enhancement

The agent remembers every action it takes, what happened, and whether it was good.
Periodically consolidates experiences into abstract patterns.
"""

from __future__ import annotations
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from agent.agi.base import AGIModule, Experience, Pattern


class ContinualLearner(AGIModule):
    """
    Learns from every interaction and improves over time.
    
    Architecture:
    - Experience Buffer: short-term memory of recent actions+results
    - Pattern Store: long-term extracted knowledge
    - Consolidation: periodic "sleep" that converts experiences → patterns
    - Retrieval: query relevant patterns for current situation
    """

    def name(self) -> str:
        return "ContinualLearner"

    def __init__(self, data_dir: Path, buffer_size: int = 500, consolidation_threshold: int = 20):
        super().__init__(data_dir)
        self.buffer_size = buffer_size
        self.consolidation_threshold = consolidation_threshold
        self.experiences: list[Experience] = []
        self.patterns: list[Pattern] = []
        self.interaction_count = 0
        self.last_consolidation = time.time()
        self._load()

    def _load(self):
        saved_exp = self.load_state("experiences.json", [])
        self.experiences = [Experience.from_dict(e) for e in saved_exp[-self.buffer_size:]]
        saved_pat = self.load_state("patterns.json", [])
        self.patterns = [Pattern.from_dict(p) for p in saved_pat]
        meta = self.load_state("meta.json", {})
        self.interaction_count = meta.get("interaction_count", 0)
        self.last_consolidation = meta.get("last_consolidation", time.time())

    def _save(self):
        self.save_state("experiences.json", [e.to_dict() for e in self.experiences[-self.buffer_size:]])
        self.save_state("patterns.json", [p.to_dict() for p in self.patterns])
        self.save_state("meta.json", {
            "interaction_count": self.interaction_count,
            "last_consolidation": self.last_consolidation,
        })

    # ─── Record ───

    def record(self, action: str, context: dict, result: Any, reward: float, domain: str = "", tags: list[str] | None = None) -> Experience:
        """Record a new experience."""
        exp = Experience(
            id=f"exp-{self.interaction_count}",
            action=action,
            context=context,
            result=result,
            reward=reward,
            domain=domain,
            tags=tags or [],
        )
        self.experiences.append(exp)
        self.interaction_count += 1

        # Trim buffer
        if len(self.experiences) > self.buffer_size:
            self.experiences = self.experiences[-self.buffer_size:]

        self._save()
        return exp

    # ─── Consolidation (Sleep) ───

    def should_consolidate(self) -> bool:
        """Check if it's time to consolidate experiences."""
        since_last = self.interaction_count - int(self.last_consolidation)
        time_elapsed = time.time() - self.last_consolidation
        return (since_last >= self.consolidation_threshold) or (time_elapsed > 3600)

    def consolidate(self) -> list[Pattern]:
        """
        'Sleep' phase: extract patterns from recent experiences.
        
        Strategies:
        1. Frequency: actions that consistently succeed/fail
        2. Sequence: action A before B improves outcomes
        3. Context: certain contexts predict success/failure
        """
        new_patterns = []

        # Strategy 1: Action-Outcome frequency
        action_stats = defaultdict(lambda: {"success": 0, "fail": 0, "total": 0})
        for exp in self.experiences:
            key = f"{exp.domain}:{exp.action}"
            action_stats[key]["total"] += 1
            if exp.reward > 0:
                action_stats[key]["success"] += 1
            elif exp.reward < 0:
                action_stats[key]["fail"] += 1

        for key, stats in action_stats.items():
            if stats["total"] >= 3:
                success_rate = stats["success"] / stats["total"]
                if success_rate >= 0.8:
                    pattern = Pattern(
                        id=f"freq-{key}",
                        description=f"Action '{key}' has high success rate ({success_rate:.0%})",
                        abstract_rule=f"PREFER action '{key}' (success: {success_rate:.0%} over {stats['total']} trials)",
                        source_domain=key.split(":")[0],
                        confidence=min(success_rate, stats["total"] / 10),
                        success_rate=success_rate,
                    )
                    new_patterns.append(pattern)
                elif success_rate <= 0.2 and stats["total"] >= 5:
                    pattern = Pattern(
                        id=f"avoid-{key}",
                        description=f"Action '{key}' frequently fails ({1-success_rate:.0%} failure)",
                        abstract_rule=f"AVOID action '{key}' (failure: {1-success_rate:.0%} over {stats['total']} trials)",
                        source_domain=key.split(":")[0],
                        confidence=min(1 - success_rate, stats["total"] / 10),
                        success_rate=success_rate,
                    )
                    new_patterns.append(pattern)

        # Strategy 2: Sequential patterns (A then B → better outcome)
        for i in range(len(self.experiences) - 1):
            curr = self.experiences[i]
            next_exp = self.experiences[i + 1]
            if curr.reward > 0 and next_exp.reward > 0.5:
                seq_id = f"seq-{curr.action}-{next_exp.action}"
                existing = next((p for p in self.patterns if p.id == seq_id), None)
                if existing:
                    existing.usage_count += 1
                    existing.confidence = min(1.0, existing.confidence + 0.05)
                else:
                    pattern = Pattern(
                        id=seq_id,
                        description=f"Sequence: '{curr.action}' → '{next_exp.action}' yields good results",
                        abstract_rule=f"SEQUENCE: do '{curr.action}' before '{next_exp.action}'",
                        source_domain=curr.domain or next_exp.domain,
                        confidence=0.4,
                        usage_count=1,
                    )
                    new_patterns.append(pattern)

        # Merge new patterns
        for np in new_patterns:
            existing = next((p for p in self.patterns if p.id == np.id), None)
            if existing:
                existing.confidence = max(existing.confidence, np.confidence)
                existing.usage_count += 1
            else:
                self.patterns.append(np)

        self.last_consolidation = time.time()
        self._save()
        self.log(f"Consolidation complete: {len(new_patterns)} patterns extracted")
        return new_patterns

    # ─── Retrieval ───

    def get_advice(self, action: str, context: dict, domain: str = "") -> list[Pattern]:
        """Retrieve relevant patterns for the current situation."""
        relevant = []
        action_lower = action.lower()
        context_str = str(context).lower()

        for pattern in self.patterns:
            score = 0.0
            # Match by action name
            if action_lower in pattern.abstract_rule.lower():
                score += 0.5
            # Match by domain
            if domain and (domain == pattern.source_domain or domain in pattern.applicable_domains):
                score += 0.3
            # Match by context keywords
            if any(word in context_str for word in pattern.description.lower().split()[:5]):
                score += 0.2

            if score > 0.3:
                relevant.append(pattern)

        # Sort by confidence × relevance
        relevant.sort(key=lambda p: p.confidence, reverse=True)
        return relevant[:5]

    def get_stats(self) -> dict:
        return {
            "total_experiences": len(self.experiences),
            "total_patterns": len(self.patterns),
            "interaction_count": self.interaction_count,
            "avg_reward": sum(e.reward for e in self.experiences) / max(len(self.experiences), 1),
        }
