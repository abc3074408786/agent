"""
GoalEngine - Autonomous Goal Generation

The Agent doesn't wait for instructions. It observes the environment,
identifies gaps between current state and ideal state, and generates
prioritized goals autonomously.

Flow:
    observe_environment() → detect_gaps() → generate_goals() → prioritize() → execute()
"""

from agent.agi.goal_engine.engine import GoalEngine

__all__ = ["GoalEngine"]
