"""
Brain Core - 类脑认知系统的统一入口

将预测循环、工作记忆、记忆整合三个模块统一起来，
提供简单的 API 给 Agent 的主循环使用。

使用方式:

    from agent.brain import Brain

    # 初始化
    brain = Brain(project_id="my_project")

    # ===== 在 Agent 执行任务的主循环中 =====

    # 1. 任务开始：推入工作记忆
    brain.focus("用户要求修复 login.py 的 bug")
    brain.focus("错误信息: NoneType has no attribute 'email'")

    # 2. 执行前：预测结果
    prediction = brain.predict(
        action="edit_file",
        context={"file": "login.py", "change": "add null check"}
    )
    # → "基于历史经验，这次修改 70% 会成功"

    # 3. 获取相关建议
    advice = brain.get_advice("edit_file", {"file": "login.py"})
    # → "历史经验：login.py 修改后 60% 需要同时修改 test_login.py"

    # 4. 执行后：反馈学习
    lesson = brain.learn(
        action="edit_file",
        context={"file": "login.py", "change": "add null check"},
        prediction=prediction,
        actual_outcome="success: tests pass",
        importance=0.7,
    )

    # 5. 定期整合（每 N 次交互 or 定时触发）
    if brain.should_consolidate():
        insights = brain.sleep()
        # → 发现规律："login.py 修改后通常需要运行 auth tests"

    # 6. 获取当前思维状态
    state = brain.get_state()
"""

import time
import logging
from typing import Any, Dict, List, Optional

from agent.brain.predictor import PredictiveLoop, Prediction, PredictionError
from agent.brain.working_memory import WorkingMemory, MemoryChunk
from agent.brain.consolidation import MemoryConsolidation, Insight, ExperienceRecord

logger = logging.getLogger(__name__)


class Brain:
    """
    类脑认知系统的统一接口

    整合了三个核心模块：
    - PredictiveLoop: 预测-学习循环（小脑）
    - WorkingMemory: 有限工作记忆（前额叶）
    - MemoryConsolidation: 记忆整合（海马体"睡眠"）
    """

    # 整合触发条件
    CONSOLIDATION_INTERVAL = 50      # 每 50 次交互触发一次
    CONSOLIDATION_TIME_GAP = 3600    # 或每 1 小时触发一次（秒）

    def __init__(
        self,
        project_id: str = "default",
        working_memory_capacity: int = 7,
        storage_dir: Optional[str] = None,
    ):
        """
        Args:
            project_id: 项目标识（用于隔离不同项目的经验）
            working_memory_capacity: 工作记忆容量（默认7）
            storage_dir: 数据存储目录
        """
        self._project_id = project_id
        self._interaction_count = 0

        # 初始化三个核心模块
        base_path = storage_dir or str(
            __import__("pathlib").Path.home() / ".agent" / "brain" / project_id
        )

        self._predictor = PredictiveLoop(
            storage_path=f"{base_path}/world_model.json"
        )
        self._working_memory = WorkingMemory(capacity=working_memory_capacity)
        self._consolidation = MemoryConsolidation(
            storage_path=f"{base_path}/consolidation.json"
        )

        logger.info(f"[Brain] 初始化完成 (project={project_id})")

    # ==================== 工作记忆接口 ====================

    def focus(self, content: str, importance: float = 0.5, category: str = "task") -> None:
        """
        将信息推入工作记忆（聚焦注意力）

        相当于"我现在在想这件事"。

        Args:
            content: 要关注的信息
            importance: 重要度
            category: 类别 (task/context/result/insight)
        """
        self._working_memory.push(content, importance, category)

    def get_focus(self) -> List[str]:
        """获取当前聚焦的信息"""
        chunks = self._working_memory.get_focus()
        return [c.content for c in chunks]

    def get_working_memory_context(self) -> str:
        """获取工作记忆内容（可注入到 LLM prompt）"""
        return self._working_memory.to_context_string()

    def recall(self, keyword: str) -> List[str]:
        """
        尝试回忆相关信息

        先搜索工作记忆，如果找不到则搜索存档。
        """
        # 先找工作记忆
        found = self._working_memory.search(keyword)
        if found:
            return [c.content for c in found]

        # 再找存档
        archived = self._working_memory.recall_from_archive(keyword)
        results = [c.content for c in archived]

        # 如果从存档找到了，可能值得重新激活
        if archived:
            self._working_memory.reactivate(archived[0])

        return results

    # ==================== 预测-学习接口 ====================

    def predict(self, action: str, context: Dict[str, Any]) -> Prediction:
        """
        预测行动的结果

        在执行任何操作之前调用，看看过去的经验怎么说。

        Args:
            action: 要执行的动作（如 "run_tests", "edit_file"）
            context: 上下文信息

        Returns:
            Prediction 对象
        """
        prediction = self._predictor.predict(action, context)

        # 把预测也放入工作记忆
        if prediction.confidence > 0.3:
            self._working_memory.push(
                f"[预测] {action}: {prediction.predicted_outcome} (信心:{prediction.confidence:.0%})",
                importance=0.3,
                category="prediction",
            )

        return prediction

    def learn(
        self,
        action: str,
        context: Dict[str, Any],
        prediction: Prediction,
        actual_outcome: str,
        importance: float = 0.5,
        emotional_valence: float = 0.0,
    ) -> PredictionError:
        """
        从实际结果中学习

        执行操作后调用，同时更新预测模型和经验库。

        Args:
            action: 执行的动作
            context: 上下文
            prediction: 之前的预测
            actual_outcome: 实际结果
            importance: 这次经验的重要度
            emotional_valence: 情绪色彩（-1负面 到 +1正面）

        Returns:
            PredictionError（学习信号）
        """
        self._interaction_count += 1

        # 1. 更新预测模型
        error = self._predictor.learn(action, context, prediction, actual_outcome)

        # 2. 记录到经验库
        self._consolidation.record_experience(
            action=action,
            context=context,
            outcome=actual_outcome,
            importance=importance,
            emotional_valence=emotional_valence,
            tags=[f"surprise:{error.surprise}"],
        )

        # 3. 如果很惊讶，推入工作记忆（值得注意的事件）
        if error.surprise in ("high", "medium"):
            self._working_memory.push(
                f"[意外] {error.lesson}",
                importance=0.8,
                category="insight",
            )

        # 4. 把结果放入工作记忆
        self._working_memory.push(
            f"[结果] {action}: {actual_outcome[:60]}",
            importance=importance * 0.6,
            category="result",
        )

        return error

    # ==================== 建议接口 ====================

    def get_advice(self, action: str, context: Dict[str, Any]) -> List[str]:
        """
        获取基于历史经验的建议

        在执行动作前调用，获取过去积累的智慧。

        Returns:
            建议列表
        """
        advice = []

        # 1. 来自预测模型的建议
        prediction = self._predictor.predict(action, context)
        if prediction.confidence > 0.3 and prediction.predicted_outcome != "unknown":
            advice.append(
                f"预测: {prediction.predicted_outcome} "
                f"(信心 {prediction.confidence:.0%}, {prediction.reasoning})"
            )

        # 2. 来自整合洞察的建议
        insights = self._consolidation.get_relevant_insights(action, context)
        for insight in insights[:3]:
            advice.append(f"经验: {insight.pattern} (置信 {insight.confidence:.0%})")

        return advice

    # ==================== 整合（"睡眠"）接口 ====================

    def should_consolidate(self) -> bool:
        """
        判断是否应该触发整合

        触发条件（任一满足）：
        - 交互次数超过阈值
        - 距离上次整合超过时间阈值
        """
        # 检查交互次数
        if self._interaction_count >= self.CONSOLIDATION_INTERVAL:
            return True

        # 检查时间
        last = self._consolidation._last_consolidation
        if last and (time.time() - last) > self.CONSOLIDATION_TIME_GAP:
            return True

        # 首次（从未整合过）且有足够经验
        if last is None and len(self._consolidation._experiences) >= 10:
            return True

        return False

    def sleep(self) -> List[Insight]:
        """
        触发整合（Agent 的"睡眠"）

        执行完整的记忆整合过程：
        - 回放经验
        - 提取模式
        - 发现规律
        - 选择性遗忘

        Returns:
            新发现的洞察列表
        """
        logger.info("[Brain] 开始'睡眠'整合...")
        self._interaction_count = 0  # 重置计数器

        insights = self._consolidation.consolidate()

        # 把重要的新洞察推入工作记忆
        for insight in insights[:2]:
            if insight.confidence > 0.5:
                self._working_memory.push(
                    f"[新发现] {insight.pattern}",
                    importance=0.7,
                    category="insight",
                )

        return insights

    # ==================== 状态查询 ====================

    def get_state(self) -> Dict[str, Any]:
        """
        获取大脑当前状态的完整快照

        用于调试、监控和展示。
        """
        return {
            "project_id": self._project_id,
            "interaction_count": self._interaction_count,
            "working_memory": {
                "usage": f"{self._working_memory.size}/{self._working_memory.capacity}",
                "utilization": f"{self._working_memory.utilization:.0%}",
                "compressions": self._working_memory.compression_count,
                "focus": [c.content[:50] for c in self._working_memory.get_focus()],
            },
            "predictor": {
                "accuracy": f"{self._predictor.get_accuracy():.0%}",
                "world_model_size": len(self._predictor._world_model),
            },
            "consolidation": self._consolidation.get_experience_stats(),
            "should_sleep": self.should_consolidate(),
        }

    def get_status_report(self) -> str:
        """获取人类可读的状态报告"""
        state = self.get_state()
        lines = [
            f"=== Brain 状态报告 (项目: {self._project_id}) ===",
            f"",
            f"[工作记忆] {state['working_memory']['usage']} "
            f"(利用率 {state['working_memory']['utilization']}, "
            f"压缩 {state['working_memory']['compressions']} 次)",
            f"  当前聚焦: {state['working_memory']['focus']}",
            f"",
            f"[预测模型] 准确率 {state['predictor']['accuracy']}, "
            f"世界模型 {state['predictor']['world_model_size']} 条规律",
            f"",
            f"[经验库] {state['consolidation'].get('total_experiences', 0)} 条经验, "
            f"{state['consolidation'].get('total_insights', 0)} 条洞察",
            f"",
            f"[交互] 第 {self._interaction_count} 次 "
            f"({'需要整合' if state['should_sleep'] else '暂不需要整合'})",
        ]
        return "\n".join(lines)

    # ==================== 辅助方法 ====================

    def clear_working_memory(self) -> None:
        """清空工作记忆（切换任务时调用）"""
        self._working_memory.clear()

    def boost_attention(self, keyword: str) -> None:
        """提升包含关键词的信息的注意力"""
        self._working_memory.boost(keyword)
