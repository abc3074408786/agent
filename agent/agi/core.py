"""
AGI Core: Unified orchestrator that integrates all 6 cognitive modules
into the main Agent execution loop.

Usage:
    agi = AGICore(project_dir="/path/to/project")
    
    # Before any action
    advice = agi.pre_action("write_code", {"file": "main.py"})
    
    # After action completes
    agi.post_action("write_code", {"file": "main.py"}, result, success=True)
    
    # Autonomous goal generation
    goals = agi.think()  # observe → goals → prioritize
    
    # Full autonomous cycle
    agi.autonomous_cycle()  # think → plan → act → evaluate → learn
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Optional

from agent.agi.base import Goal, Experience, EvaluationResult
from agent.agi.goal_engine import GoalEngine
from agent.agi.continual_learner import ContinualLearner
from agent.agi.transfer_engine import TransferEngine
from agent.agi.self_evaluator import SelfEvaluator
from agent.agi.world_model import WorldModel
from agent.agi.embodied import EmbodiedAgent


class AGICore:
    """
    Central orchestrator for all AGI cognitive modules.
    
    Integrates into the LangGraph ReAct loop:
    
        User Input → [pre_action] → LLM → Tool Call → [post_action] → Response
                          ↑                                    ↓
                    Goal Engine                         Continual Learner
                    World Model                        Self Evaluator
                    Transfer Engine                    World Model Update
    """

    def __init__(self, project_dir: str = ".", data_dir: str | None = None):
        self.project_dir = Path(project_dir)
        self.data_dir = Path(data_dir) if data_dir else self.project_dir / ".agi"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize all modules
        self.goal_engine = GoalEngine(self.data_dir / "goals")
        self.learner = ContinualLearner(self.data_dir / "learner")
        self.transfer = TransferEngine(self.data_dir / "transfer")
        self.evaluator = SelfEvaluator(self.data_dir / "evaluator")
        self.world_model = WorldModel(self.data_dir / "world_model")
        self.embodied = EmbodiedAgent(self.data_dir / "embodied", workspace=str(self.project_dir))

        self._cycle_count = 0

    # ─── Pre-Action Hook ───

    def pre_action(self, action: str, context: dict, domain: str = "") -> dict:
        """
        Called BEFORE the agent executes an action.
        Returns advice from all modules.
        """
        advice = {
            "action": action,
            "predictions": [],
            "patterns": [],
            "transfer_advice": [],
            "confidence": self.evaluator.get_confidence(domain),
            "should_ask_human": False,
            "warnings": [],
        }

        # 1. World Model: predict outcome
        predictions = self.world_model.predict(action, context)
        advice["predictions"] = predictions[:3]
        if predictions and predictions[0]["confidence"] < 0.3:
            advice["warnings"].append(f"低信心预测: {predictions[0]['effect']}")

        # 2. Learner: retrieve relevant patterns
        patterns = self.learner.get_advice(action, context, domain)
        advice["patterns"] = [{"rule": p.abstract_rule, "confidence": p.confidence} for p in patterns]

        # Check for "AVOID" patterns
        avoid_patterns = [p for p in patterns if "AVOID" in p.abstract_rule]
        if avoid_patterns:
            advice["warnings"].append(f"历史数据建议避免此操作: {avoid_patterns[0].description}")

        # 3. Transfer: cross-domain advice
        if domain:
            transfer_patterns = self.transfer.find_applicable_patterns(domain)
            advice["transfer_advice"] = [
                self.transfer.transfer(p, domain) for p in transfer_patterns[:2]
            ]

        # 4. Confidence check
        advice["should_ask_human"] = self.evaluator.should_ask_human(domain)

        return advice

    # ─── Post-Action Hook ───

    def post_action(self, action: str, context: dict, result: Any, success: bool = True, domain: str = "") -> dict:
        """
        Called AFTER the agent executes an action.
        Learns from the result and updates all modules.
        """
        reward = 1.0 if success else -0.5
        report = {"action": action, "learned": False, "evaluation": None}

        # 1. Record experience
        self.learner.record(
            action=action,
            context=context,
            result=result,
            reward=reward,
            domain=domain,
        )

        # 2. Update world model
        effect = "success" if success else "failure"
        self.world_model.observe(action, context, effect, domain=domain)

        # 3. Self-evaluate
        eval_result = self.evaluator.evaluate(action, context, result, domain=domain)
        report["evaluation"] = {
            "score": eval_result.score,
            "confidence": eval_result.confidence,
            "suggestions": eval_result.suggestions,
        }

        # 4. Consolidate if needed
        if self.learner.should_consolidate():
            new_patterns = self.learner.consolidate()
            report["learned"] = True
            report["new_patterns"] = len(new_patterns)

            # Try to abstract and transfer
            for pattern in new_patterns:
                self.transfer.abstract_from_experience(pattern)

        return report

    # ─── Autonomous Thinking ───

    def think(self) -> list[Goal]:
        """
        Autonomous thinking: observe environment and generate goals.
        Called periodically without human input.
        """
        return self.goal_engine.generate_goals()

    def get_next_goal(self) -> Optional[Goal]:
        """Get the highest priority goal to work on."""
        return self.goal_engine.get_next_goal()

    # ─── Full Autonomous Cycle ───

    def autonomous_cycle(self) -> dict:
        """
        One full autonomous cycle:
        1. Think (generate goals)
        2. Plan (simulate in world model)
        3. Act (execute via embodied agent)
        4. Evaluate (self-assess)
        5. Learn (update all modules)
        """
        self._cycle_count += 1
        cycle_report = {"cycle": self._cycle_count, "goals_generated": 0, "actions_taken": 0}

        # 1. Think
        new_goals = self.think()
        cycle_report["goals_generated"] = len(new_goals)

        # 2. Get next goal
        goal = self.get_next_goal()
        if not goal:
            cycle_report["status"] = "no_goals"
            return cycle_report

        cycle_report["active_goal"] = goal.description

        # 3. Simulate (plan check)
        plan = [{"action": "work_on_goal", "context": goal.context}]
        simulation = self.world_model.simulate_plan(plan)
        cycle_report["simulation"] = simulation

        if simulation["success_probability"] < 0.2:
            cycle_report["status"] = "too_risky"
            cycle_report["risks"] = simulation["risks"]
            return cycle_report

        # 4. The actual execution would be delegated to the main Agent loop
        # This is the integration point with LangGraph
        cycle_report["status"] = "goal_ready"
        cycle_report["goal"] = goal.to_dict()

        return cycle_report

    # ─── Stats & Diagnostics ───

    def stats(self) -> dict:
        """Get stats from all modules."""
        return {
            "goals": self.goal_engine.stats(),
            "learner": self.learner.get_stats(),
            "world_model": self.world_model.get_graph_stats(),
            "evaluator": {
                "confidence": self.evaluator.confidence,
                "domain_confidence": self.evaluator.domain_confidence,
            },
            "transfer": {"patterns": len(self.transfer.abstract_patterns)},
            "cycles": self._cycle_count,
        }
