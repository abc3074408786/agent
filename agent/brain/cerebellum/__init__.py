"""Cerebellum - Prediction-Comparison-Correction Loop"""

import time
from typing import Any, Optional


class Cerebellum:
    """
    Predicts outcomes before actions, compares with reality, learns from errors.
    
    Principles:
    - Forward model: predict action outcome BEFORE execution
    - Error signal: prediction - reality = learning signal
    - Adaptation: adjust predictions based on accumulated errors
    - Precision: gets more accurate with practice
    """

    def __init__(self):
        self.predictions: dict[str, list[dict]] = {}  # action → [{predicted, actual, error}]
        self.accuracy: dict[str, float] = {}  # action → rolling accuracy
        self.total_predictions = 0
        self.total_correct = 0

    def predict(self, action: str, context: dict = None) -> dict:
        """
        Generate prediction for an action outcome.
        Uses history of similar actions to estimate.
        """
        self.total_predictions += 1
        history = self.predictions.get(action, [])

        if not history:
            return {"predicted_outcome": "unknown", "confidence": 0.2, "basis": "no_history"}

        # Use most recent outcomes as prediction basis
        recent = history[-10:]
        outcomes = [h["actual"] for h in recent if h.get("actual")]

        if not outcomes:
            return {"predicted_outcome": "unknown", "confidence": 0.3, "basis": "no_actuals"}

        # Most common outcome = prediction
        from collections import Counter
        most_common = Counter(str(o) for o in outcomes).most_common(1)[0]
        confidence = most_common[1] / len(recent)

        return {
            "predicted_outcome": most_common[0],
            "confidence": confidence,
            "basis": f"{len(recent)} recent observations",
            "action": action,
        }

    def compare(self, action: str, predicted: Any, actual: Any) -> dict:
        """
        Compare prediction with actual result. Generate error signal.
        """
        error = 0.0 if str(predicted) == str(actual) else 1.0

        # Record
        if action not in self.predictions:
            self.predictions[action] = []
        self.predictions[action].append({
            "predicted": str(predicted),
            "actual": str(actual),
            "error": error,
            "timestamp": time.time(),
        })

        # Keep last 50 per action
        if len(self.predictions[action]) > 50:
            self.predictions[action] = self.predictions[action][-50:]

        # Update accuracy
        recent = self.predictions[action][-20:]
        correct = sum(1 for h in recent if h["error"] == 0)
        self.accuracy[action] = correct / len(recent)

        if error == 0:
            self.total_correct += 1

        return {
            "error": error,
            "accuracy": self.accuracy[action],
            "learning_signal": "positive" if error == 0 else "negative",
            "suggestion": None if error == 0 else f"预测错误: 预期 '{predicted}' 实际 '{actual}'",
        }

    def get_accuracy(self, action: str = None) -> float:
        """Get prediction accuracy for an action or overall."""
        if action:
            return self.accuracy.get(action, 0.5)
        return self.total_correct / max(self.total_predictions, 1)

    def get_unreliable_actions(self, threshold: float = 0.4) -> list[str]:
        """Actions where predictions are frequently wrong."""
        return [a for a, acc in self.accuracy.items() if acc < threshold]
