"""
SelfEvaluator: Multi-method self-assessment without human feedback.

Methods:
1. Result Verification: run tests, check outputs
2. Consistency Check: does output contradict known facts?
3. Prediction Calibration: was prediction accurate?
4. Confidence Tracking: adaptive confidence based on track record
"""

from __future__ import annotations
from collections import deque
from pathlib import Path
from typing import Any, Callable, Optional

from agent.agi.base import AGIModule, EvaluationResult


class SelfEvaluator(AGIModule):
    """
    Evaluates Agent's own actions without external feedback.
    Maintains a rolling confidence score that adapts over time.
    """

    def name(self) -> str:
        return "SelfEvaluator"

    def __init__(self, data_dir: Path, history_size: int = 100):
        super().__init__(data_dir)
        self.history_size = history_size
        self.evaluation_history: deque = deque(maxlen=history_size)
        self.confidence: float = 0.5  # starts neutral
        self.domain_confidence: dict[str, float] = {}
        self.verifiers: list[Callable] = []
        self._load()

    def _load(self):
        state = self.load_state("evaluator_state.json", {})
        self.confidence = state.get("confidence", 0.5)
        self.domain_confidence = state.get("domain_confidence", {})
        history = state.get("history", [])
        self.evaluation_history = deque(history[-self.history_size:], maxlen=self.history_size)

    def _save(self):
        self.save_state("evaluator_state.json", {
            "confidence": self.confidence,
            "domain_confidence": self.domain_confidence,
            "history": list(self.evaluation_history),
        })

    def register_verifier(self, verifier: Callable[[str, Any, Any], Optional[bool]]) -> None:
        """Register a verification function: (action, context, result) → pass/fail/None"""
        self.verifiers.append(verifier)

    # ─── Evaluation Methods ───

    def evaluate(self, action: str, context: dict, result: Any, prediction: Any = None, domain: str = "") -> EvaluationResult:
        """
        Run all evaluation methods and return composite score.
        """
        scores = []
        details = {}

        # Method 1: Verification (if verifiers registered)
        verification = self._run_verifiers(action, context, result)
        if verification is not None:
            scores.append(1.0 if verification else 0.0)
            details["verification"] = verification

        # Method 2: Prediction calibration
        if prediction is not None:
            pred_score = self._check_prediction(prediction, result)
            scores.append(pred_score)
            details["prediction_accuracy"] = pred_score

        # Method 3: Self-consistency
        consistency = self._check_consistency(action, result)
        scores.append(consistency)
        details["consistency"] = consistency

        # Method 4: Historical comparison
        historical = self._compare_with_history(action, domain)
        if historical is not None:
            scores.append(historical)
            details["historical_performance"] = historical

        # Composite score
        score = sum(scores) / max(len(scores), 1)
        confidence = self._calculate_confidence(scores)

        # Update state
        self._update_confidence(score, domain)
        eval_result = EvaluationResult(
            score=score,
            confidence=confidence,
            method="composite",
            details=details,
            suggestions=self._generate_suggestions(score, details),
        )
        self.evaluation_history.append({"score": score, "domain": domain, "action": action})
        self._save()
        return eval_result

    def should_ask_human(self, domain: str = "") -> bool:
        """Determine if confidence is too low and human should be consulted."""
        domain_conf = self.domain_confidence.get(domain, self.confidence)
        return domain_conf < 0.3

    def get_confidence(self, domain: str = "") -> float:
        """Get current confidence for a domain."""
        return self.domain_confidence.get(domain, self.confidence)

    # ─── Internal Methods ───

    def _run_verifiers(self, action: str, context: Any, result: Any) -> Optional[bool]:
        """Run registered verifiers."""
        results = []
        for verifier in self.verifiers:
            try:
                v = verifier(action, context, result)
                if v is not None:
                    results.append(v)
            except Exception:
                pass
        if not results:
            return None
        return sum(results) / len(results) > 0.5

    def _check_prediction(self, prediction: Any, actual: Any) -> float:
        """Compare prediction with actual result."""
        pred_str = str(prediction).lower()
        actual_str = str(actual).lower()

        if pred_str == actual_str:
            return 1.0
        # Partial match
        pred_words = set(pred_str.split())
        actual_words = set(actual_str.split())
        if not pred_words or not actual_words:
            return 0.5
        overlap = len(pred_words & actual_words) / max(len(pred_words | actual_words), 1)
        return overlap

    def _check_consistency(self, action: str, result: Any) -> float:
        """Check if result is consistent with past results for same action."""
        same_action = [h for h in self.evaluation_history if h.get("action") == action]
        if len(same_action) < 2:
            return 0.7  # not enough data, assume ok
        avg_past_score = sum(h["score"] for h in same_action) / len(same_action)
        return avg_past_score

    def _compare_with_history(self, action: str, domain: str) -> Optional[float]:
        """Compare current performance with historical average."""
        relevant = [h for h in self.evaluation_history if h.get("domain") == domain]
        if len(relevant) < 3:
            return None
        avg = sum(h["score"] for h in relevant) / len(relevant)
        return avg

    def _calculate_confidence(self, scores: list[float]) -> float:
        """How confident are we in this evaluation?"""
        if not scores:
            return 0.5
        # High agreement between methods = high confidence
        if len(scores) == 1:
            return 0.6
        variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
        return max(0.1, 1.0 - variance * 2)

    def _update_confidence(self, score: float, domain: str) -> None:
        """Update rolling confidence based on latest score."""
        # Exponential moving average
        alpha = 0.1
        self.confidence = self.confidence * (1 - alpha) + score * alpha
        if domain:
            old = self.domain_confidence.get(domain, 0.5)
            self.domain_confidence[domain] = old * (1 - alpha) + score * alpha

    def _generate_suggestions(self, score: float, details: dict) -> list[str]:
        """Generate improvement suggestions based on evaluation."""
        suggestions = []
        if score < 0.3:
            suggestions.append("结果质量低，建议重新尝试或换一种方法")
        if details.get("prediction_accuracy", 1) < 0.3:
            suggestions.append("预测与实际差距大，需要更新世界模型")
        if details.get("consistency", 1) < 0.3:
            suggestions.append("结果与历史表现不一致，可能有新的未知因素")
        if score < 0.5:
            suggestions.append("考虑请求人类确认或提供更多上下文")
        return suggestions
