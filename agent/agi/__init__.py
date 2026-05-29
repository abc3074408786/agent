"""
AGI Core Modules - Towards Artificial General Intelligence

Six cognitive modules that give the Agent abilities beyond simple tool calling:

1. GoalEngine      - Autonomous goal generation (self-directed behavior)
2. ContinualLearner - Learning from experience (never starts from zero)
3. TransferEngine  - Cross-domain knowledge transfer (generalization)
4. SelfEvaluator   - Self-assessment without human feedback
5. WorldModel      - Causal understanding (not just pattern matching)
6. EmbodiedAgent   - Perception-action loops in real environments

Usage:
    from agent.agi import AGICore
    
    agi = AGICore(project_dir="/path/to/project")
    
    # Before action: get advice from all modules
    advice = agi.pre_action(action="write_code", context={...})
    
    # After action: learn from result
    agi.post_action(action="write_code", context={...}, result={...})
    
    # Autonomous: generate goals without human input
    goals = agi.generate_goals()
"""

from agent.agi.core import AGICore
from agent.agi.base import AGIModule, Experience, Goal, CausalLink

__all__ = ["AGICore", "AGIModule", "Experience", "Goal", "CausalLink"]
