"""
ContinualLearner - Never Start From Zero

Records every experience, extracts patterns during "sleep" consolidation,
and uses learned knowledge to improve future decisions.
"""
from agent.agi.continual_learner.learner import ContinualLearner

__all__ = ["ContinualLearner"]
