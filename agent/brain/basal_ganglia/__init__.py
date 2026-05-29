"""Basal Ganglia - Habit Formation + Reward Learning"""

import time
from collections import defaultdict
from typing import Optional


class BasalGanglia:
    """
    Habit formation through reinforcement.
    
    Principles:
    - Reward prediction: expect reward, learn when surprised
    - Habit loop: cue → routine → reward (gets automatic over time)
    - Dopamine signal: positive surprise = strengthen, negative = weaken
    - Automaticity: high-confidence habits bypass conscious planning
    """

    def __init__(self):
        self.habits: dict[str, dict] = {}  # cue → {routine, reward_avg, count, strength}
        self.reward_history: list[dict] = []

    def record_reward(self, cue: str, routine: str, reward: float) -> dict:
        """
        Record a cue-routine-reward triple.
        Reward: -1.0 (bad) to +1.0 (great)
        """
        key = f"{cue}→{routine}"

        if key not in self.habits:
            self.habits[key] = {
                "cue": cue,
                "routine": routine,
                "reward_avg": 0.0,
                "count": 0,
                "strength": 0.0,
                "last_used": time.time(),
            }

        habit = self.habits[key]

        # Dopamine signal: surprise = actual - expected
        surprise = reward - habit["reward_avg"]

        # Update running average (exponential)
        alpha = 0.2
        habit["reward_avg"] = habit["reward_avg"] * (1 - alpha) + reward * alpha
        habit["count"] += 1
        habit["last_used"] = time.time()

        # Strengthen/weaken based on reward
        if reward > 0:
            habit["strength"] = min(1.0, habit["strength"] + 0.1 * reward)
        else:
            habit["strength"] = max(0.0, habit["strength"] + 0.1 * reward)

        self.reward_history.append({
            "cue": cue, "routine": routine, "reward": reward,
            "surprise": surprise, "timestamp": time.time()
        })

        return {
            "habit_strength": habit["strength"],
            "surprise": surprise,
            "is_automatic": habit["strength"] > 0.8,
        }

    def suggest_routine(self, cue: str) -> Optional[dict]:
        """
        Given a cue, suggest the best habitual routine.
        Only suggests if habit is strong enough.
        """
        matching = [(k, h) for k, h in self.habits.items() if h["cue"] == cue]
        if not matching:
            return None

        # Pick strongest habit
        matching.sort(key=lambda x: x[1]["strength"], reverse=True)
        best_key, best_habit = matching[0]

        if best_habit["strength"] < 0.3:
            return None  # not habituated enough

        return {
            "routine": best_habit["routine"],
            "strength": best_habit["strength"],
            "reward_expected": best_habit["reward_avg"],
            "is_automatic": best_habit["strength"] > 0.8,
            "times_used": best_habit["count"],
        }

    def get_strong_habits(self, min_strength: float = 0.6) -> list[dict]:
        """Get all well-formed habits."""
        return [h for h in self.habits.values() if h["strength"] >= min_strength]

    def decay_unused(self, days_threshold: int = 30) -> int:
        """Decay habits not used recently."""
        now = time.time()
        decayed = 0
        for key, habit in list(self.habits.items()):
            age_days = (now - habit["last_used"]) / 86400
            if age_days > days_threshold:
                habit["strength"] *= 0.9
                if habit["strength"] < 0.05:
                    del self.habits[key]
                decayed += 1
        return decayed
