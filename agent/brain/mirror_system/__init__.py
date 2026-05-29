"""Mirror System - Observation Learning + Behavior Imitation"""

import time
from typing import Any


class MirrorSystem:
    """
    Learn by observing others (or past successful behaviors).
    
    Principles:
    - Observation: record what successful agents do
    - Imitation: replicate observed behavior patterns
    - Adaptation: modify imitated behavior to fit context
    """

    def __init__(self):
        self.observed_behaviors: list[dict] = []
        self.max_observations = 100

    def observe(self, actor: str, action: str, context: dict, outcome: str, success: bool) -> None:
        """Record an observed behavior."""
        self.observed_behaviors.append({
            "actor": actor,
            "action": action,
            "context": context,
            "outcome": outcome,
            "success": success,
            "timestamp": time.time(),
        })
        if len(self.observed_behaviors) > self.max_observations:
            self.observed_behaviors = self.observed_behaviors[-self.max_observations:]

    def suggest_imitation(self, current_context: str) -> list[dict]:
        """Suggest behaviors to imitate based on current context."""
        context_words = set(current_context.lower().split())
        suggestions = []
        for obs in self.observed_behaviors:
            if not obs["success"]:
                continue
            obs_words = set(f"{obs['action']} {str(obs['context'])}".lower().split())
            overlap = len(context_words & obs_words)
            if overlap > 0:
                suggestions.append({
                    "action": obs["action"],
                    "from": obs["actor"],
                    "relevance": overlap / max(len(context_words), 1),
                })
        suggestions.sort(key=lambda s: s["relevance"], reverse=True)
        return suggestions[:3]
