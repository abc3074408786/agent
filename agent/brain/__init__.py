"""
Brain Module - 类脑认知架构

模拟人脑核心机制，让 Agent 具备：
1. 预测-学习循环（小脑）：预测行动结果，从错误中学习
2. 有限工作记忆（前额叶）：强制压缩，逼出抽象能力
3. 记忆整合（海马体"睡眠"）：定期整理经验，发现规律

使用方式:
    from agent.brain import Brain

    brain = Brain(project_id="my_project")

    # 执行任务时预测结果
    prediction = await brain.predict_outcome(action, context)

    # 任务完成后反馈实际结果
    await brain.learn_from_outcome(action, context, prediction, actual_result)

    # 定期触发"睡眠"整合
    insights = await brain.consolidate()
"""

from agent.brain.predictor import PredictiveLoop, Prediction, PredictionError
from agent.brain.working_memory import WorkingMemory, MemoryChunk
from agent.brain.consolidation import MemoryConsolidation, Insight, ExperienceRecord
from agent.brain.core import Brain


__all__ = [
    "Brain",
    "PredictiveLoop",
    "Prediction",
    "PredictionError",
    "WorkingMemory",
    "MemoryChunk",
    "MemoryConsolidation",
    "Insight",
    "ExperienceRecord",
]
