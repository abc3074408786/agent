"""
WorldModel: Causal graph + simulation + counterfactual reasoning.

Not "A usually comes before B" but "A causes B because of C".
Can simulate plans before execution to predict outcomes.
"""

from __future__ import annotations
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from agent.agi.base import AGIModule, CausalLink


class WorldModel(AGIModule):
    """
    Maintains a causal graph of action-effect relationships.
    Supports:
    - Learning causality from observations
    - Predicting effects of actions
    - Simulating entire plans before execution
    - Counterfactual reasoning ("what if I had done X instead?")
    """

    def name(self) -> str:
        return "WorldModel"

    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.causal_links: list[CausalLink] = []
        self.state: dict[str, Any] = {}  # current world state
        self._load()

    def _load(self):
        saved = self.load_state("causal_graph.json", [])
        self.causal_links = [CausalLink.from_dict(c) for c in saved]
        self.state = self.load_state("world_state.json", {})

    def _save(self):
        self.save_state("causal_graph.json", [c.to_dict() for c in self.causal_links])
        self.save_state("world_state.json", self.state)

    # ─── Learn Causality ───

    def observe(self, action: str, context: dict, effect: str, conditions: list[str] | None = None, domain: str = "") -> CausalLink:
        """Record an observed cause-effect relationship."""
        # Find existing link or create new
        existing = self._find_link(action, effect)
        if existing:
            existing.observations += 1
            existing.confidence = min(1.0, existing.confidence + 0.05)
            existing.last_observed = __import__("time").time()
            if conditions:
                existing.conditions = list(set(existing.conditions + conditions))
        else:
            link = CausalLink(
                cause=action,
                effect=effect,
                confidence=0.3,  # start low, grow with observations
                observations=1,
                conditions=conditions or [],
                domain=domain,
            )
            self.causal_links.append(link)
            existing = link

        self._save()
        return existing

    def observe_no_effect(self, action: str, expected_effect: str) -> None:
        """Record that an expected effect did NOT happen (weakens link)."""
        link = self._find_link(action, expected_effect)
        if link:
            link.confidence = max(0.0, link.confidence - 0.1)
            self._save()

    # ─── Predict ───

    def predict(self, action: str, context: dict | None = None) -> list[dict]:
        """Predict effects of an action given context."""
        predictions = []
        for link in self.causal_links:
            if link.cause == action and link.confidence > 0.2:
                # Check conditions
                conditions_met = True
                if link.conditions and context:
                    conditions_met = all(
                        c.lower() in str(context).lower() for c in link.conditions
                    )
                if conditions_met:
                    predictions.append({
                        "effect": link.effect,
                        "confidence": link.confidence,
                        "conditions": link.conditions,
                        "observations": link.observations,
                    })

        predictions.sort(key=lambda p: p["confidence"], reverse=True)
        return predictions

    def simulate_plan(self, plan: list[dict]) -> dict:
        """
        Simulate a multi-step plan in the world model.
        
        Args:
            plan: [{"action": "...", "context": {...}}, ...]
        
        Returns:
            {"success_probability": float, "predicted_effects": [...], "risks": [...]}
        """
        simulated_state = dict(self.state)
        all_effects = []
        risks = []
        total_confidence = 1.0

        for step in plan:
            action = step.get("action", "")
            context = {**simulated_state, **step.get("context", {})}

            predictions = self.predict(action, context)
            if not predictions:
                risks.append(f"Step '{action}': 无历史数据，结果不可预测")
                total_confidence *= 0.5
            else:
                best = predictions[0]
                all_effects.append({"action": action, "effect": best["effect"], "confidence": best["confidence"]})
                total_confidence *= best["confidence"]

                # Check for negative effects
                negative = [p for p in predictions if "fail" in p["effect"].lower() or "error" in p["effect"].lower()]
                if negative:
                    risks.append(f"Step '{action}': 可能导致 {negative[0]['effect']} (概率 {negative[0]['confidence']:.0%})")

                # Update simulated state
                simulated_state[f"step_{action}_result"] = best["effect"]

        return {
            "success_probability": total_confidence,
            "predicted_effects": all_effects,
            "risks": risks,
            "steps": len(plan),
        }

    def counterfactual(self, actual_action: str, alternative_action: str, context: dict) -> dict:
        """
        Counterfactual reasoning: "What if I had done X instead of Y?"
        """
        actual_predictions = self.predict(actual_action, context)
        alternative_predictions = self.predict(alternative_action, context)

        return {
            "actual": {"action": actual_action, "predictions": actual_predictions[:3]},
            "alternative": {"action": alternative_action, "predictions": alternative_predictions[:3]},
            "recommendation": (
                f"选择 '{alternative_action}'" if alternative_predictions and actual_predictions and
                alternative_predictions[0]["confidence"] > actual_predictions[0]["confidence"]
                else f"保持 '{actual_action}'"
            ),
        }

    # ─── State ───

    def update_state(self, key: str, value: Any) -> None:
        """Update current world state."""
        self.state[key] = value
        self._save()

    def get_state(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)

    # ─── Query ───

    def get_causes_of(self, effect: str) -> list[CausalLink]:
        """What causes this effect?"""
        return [l for l in self.causal_links if l.effect == effect and l.confidence > 0.2]

    def get_effects_of(self, cause: str) -> list[CausalLink]:
        """What does this action cause?"""
        return [l for l in self.causal_links if l.cause == cause and l.confidence > 0.2]

    def get_graph_stats(self) -> dict:
        return {
            "total_links": len(self.causal_links),
            "high_confidence": len([l for l in self.causal_links if l.confidence > 0.7]),
            "unique_causes": len(set(l.cause for l in self.causal_links)),
            "unique_effects": len(set(l.effect for l in self.causal_links)),
        }

    # ─── Internal ───

    def _find_link(self, cause: str, effect: str) -> Optional[CausalLink]:
        for link in self.causal_links:
            if link.cause == cause and link.effect == effect:
                return link
        return None
