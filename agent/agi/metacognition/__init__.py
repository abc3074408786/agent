"""
Metacognition Module - Agent knows what it doesn't know.

7 capabilities:
1. UncertaintyDetector: detect knowledge boundaries
2. QuestionGenerator: proactively ask for missing information
3. ContextGuard: never lose critical info
4. FeasibilityChecker: assess if a task is doable
5. CourseCorrector: detect wrong path and rollback
6. PriorityRanker: rank multiple tasks by urgency
7. CompletionChecker: verify if the goal has been achieved
"""

from agent.agi.metacognition.engine import MetacognitionEngine

__all__ = ["MetacognitionEngine"]
