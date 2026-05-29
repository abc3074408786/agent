"""
BrainOS Core - Orchestrates all brain modules into a unified cognitive system.

Usage:
    brain = BrainOS(project_id="my_project")
    decision = brain.process(input="写认证模块", context={})
    brain.feedback(action="write_code", result="ok", reward=1.0)
    insights = brain.daydream()
"""

from pathlib import Path
from typing import Any, Optional

from agent.brain.thalamus import Thalamus
from agent.brain.prefrontal import PrefrontalCortex
from agent.brain.hippocampus import Hippocampus
from agent.brain.cerebellum import Cerebellum
from agent.brain.basal_ganglia import BasalGanglia
from agent.brain.amygdala import Amygdala
from agent.brain.default_network import DefaultNetwork
from agent.brain.mirror_system import MirrorSystem


class BrainOS:
    """Unified brain: routes input through all modules, returns decision."""

    def __init__(self, project_id: str = "default", data_dir: str = ".brain"):
        base = Path(data_dir) / project_id
        self.thalamus = Thalamus()
        self.prefrontal = PrefrontalCortex()
        self.hippocampus = Hippocampus(data_dir=base / "hippocampus")
        self.cerebellum = Cerebellum()
        self.basal_ganglia = BasalGanglia()
        self.amygdala = Amygdala()
        self.default_network = DefaultNetwork()
        self.mirror_system = MirrorSystem()

    def process(self, input: str, context: dict = None) -> dict:
        """
        Full cognitive processing pipeline:
        Thalamus → Amygdala → Prefrontal → Hippocampus → Cerebellum → Basal Ganglia
        """
        context = context or {}
        result = {"input": input, "decisions": []}

        # 1. Thalamus: route and filter
        signal = self.thalamus.route("user", input, priority=0.7, tags=["input"])
        if not signal:
            return {**result, "filtered": True}

        # 2. Amygdala: quick risk check (fast path)
        risk = self.amygdala.assess_risk(input, str(context))
        result["risk"] = risk
        if risk["should_interrupt"]:
            result["blocked"] = True
            result["reason"] = risk["reasons"]
            return result

        # 3. Prefrontal: add to working memory + check current goal
        self.prefrontal.attend("current_input", input, importance=0.8)
        result["current_goal"] = self.prefrontal.current_goal()
        result["working_memory"] = len(self.prefrontal.working_memory)

        # 4. Hippocampus: recall relevant memories
        memories = self.hippocampus.recall(input, top_k=3)
        result["memories"] = [m["event"] for m in memories]
        for m in memories:
            self.prefrontal.attend(f"mem-{m['id']}", m["event"], importance=0.4)

        # 5. Cerebellum: predict outcome
        prediction = self.cerebellum.predict(input, context)
        result["prediction"] = prediction

        # 6. Basal Ganglia: check for habitual response
        habit = self.basal_ganglia.suggest_routine(input)
        result["habit"] = habit

        # 7. Mirror System: check for imitable behaviors
        imitations = self.mirror_system.suggest_imitation(input)
        result["imitations"] = imitations

        # 8. Default Network: feed concept pool
        self.default_network.add_concept(input)

        return result

    def feedback(self, action: str, result: Any, reward: float = 0.0) -> dict:
        """
        Post-action feedback. Updates all learning modules.
        """
        report = {}

        # Cerebellum: compare prediction with reality
        pred = self.cerebellum.predict(action)
        comparison = self.cerebellum.compare(action, pred.get("predicted_outcome"), str(result))
        report["prediction_error"] = comparison

        # Basal Ganglia: reinforce or weaken habit
        habit_result = self.basal_ganglia.record_reward(action, str(result)[:50], reward)
        report["habit_update"] = habit_result

        # Hippocampus: encode as episodic memory
        self.hippocampus.encode(
            event=f"{action} → {str(result)[:100]}",
            emotion=reward,
            tags=[action.split("_")[0]] if "_" in action else [action],
        )

        # Amygdala: learn from negative outcomes
        if reward < -0.5:
            keywords = action.lower().split("_") + str(result)[:50].lower().split()[:3]
            self.amygdala.learn_fear(action, keywords, risk=abs(reward))

        # Mirror System: record own behavior for future reference
        self.mirror_system.observe("self", action, {}, str(result)[:100], reward > 0)

        return report

    def daydream(self) -> dict:
        """
        Idle-time processing: consolidate + create.
        Call this during downtime.
        """
        # Hippocampus sleep
        consolidation = self.hippocampus.sleep()
        # Default network associations
        associations = self.default_network.daydream()
        # Basal ganglia decay
        decayed = self.basal_ganglia.decay_unused()
        # Thalamus reset
        self.thalamus.reset_habituation()

        return {
            "consolidation": consolidation,
            "creative_associations": associations,
            "habits_decayed": decayed,
        }

    def stats(self) -> dict:
        return {
            "working_memory": len(self.prefrontal.working_memory),
            "goal_stack": len(self.prefrontal.goal_stack),
            "memories": self.hippocampus.stats(),
            "prediction_accuracy": self.cerebellum.get_accuracy(),
            "strong_habits": len(self.basal_ganglia.get_strong_habits()),
            "risk_sensitivity": self.amygdala.get_sensitivity(),
            "concepts": len(self.default_network.concept_pool),
        }
