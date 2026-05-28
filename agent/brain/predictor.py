"""
预测-学习循环（Predictive Loop）

模拟小脑的核心功能：
- 每次行动前，预测可能的结果
- 行动后，对比预测和实际结果
- 预测错误产生学习信号 → 更新世界模型
- 预测准确 → 强化当前模型

这是大脑最基本的学习算法：预测误差驱动学习（Predictive Coding）。

使用示例:
    loop = PredictiveLoop()

    # 行动前预测
    prediction = loop.predict("run_tests", {"file": "main.py"})
    # → Prediction(outcome="tests_pass", confidence=0.7)

    # 行动后学习
    error = loop.learn("run_tests", {"file": "main.py"}, prediction, "tests_fail: 3 errors")
    # → PredictionError(magnitude=0.8, surprise="high", lesson="main.py 经常有测试失败")

    # 下次预测会更准确
    prediction2 = loop.predict("run_tests", {"file": "main.py"})
    # → Prediction(outcome="tests_fail", confidence=0.6)
"""

import json
import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """一次预测的记录"""
    action: str                      # 要执行的动作
    context_summary: str             # 上下文摘要
    predicted_outcome: str           # 预测的结果
    confidence: float                # 预测信心 0.0-1.0
    reasoning: str                   # 预测依据
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Prediction":
        return cls(**data)


@dataclass
class PredictionError:
    """预测误差 — 学习信号"""
    action: str
    predicted: str
    actual: str
    magnitude: float        # 误差大小 0.0-1.0（0=完全正确，1=完全错误）
    surprise: str           # "none" | "low" | "medium" | "high"
    lesson: str             # 从这次错误中学到的
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass 
class WorldModelEntry:
    """世界模型中的一条规则"""
    pattern: str              # 模式："当 X 时，做 Y 通常会导致 Z"
    confidence: float         # 信心 0.0-1.0
    hit_count: int = 0        # 被验证为正确的次数
    miss_count: int = 0       # 被验证为错误的次数
    last_updated: float = field(default_factory=time.time)
    evidence: List[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        total = self.hit_count + self.miss_count
        if total == 0:
            return 0.5
        return self.hit_count / total

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldModelEntry":
        return cls(**data)


class PredictiveLoop:
    """
    预测-学习循环

    核心算法:
    1. predict(action, context) → 基于世界模型预测结果
    2. learn(action, context, prediction, actual) → 对比后更新世界模型
    3. 世界模型持续进化

    世界模型是一个 pattern → outcome 的映射表，
    每次预测错误时更新，预测正确时强化。
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: 世界模型存储路径，默认 ~/.agent/brain/world_model.json
        """
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = Path.home() / ".agent" / "brain" / "world_model.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        # 世界模型: pattern_key → WorldModelEntry
        self._world_model: Dict[str, WorldModelEntry] = {}

        # 预测历史（用于分析学习进度）
        self._prediction_history: List[Dict[str, Any]] = []
        self._max_history = 1000

        # 加载已有世界模型
        self._load()

    # ==================== 核心接口 ====================

    def predict(self, action: str, context: Dict[str, Any]) -> Prediction:
        """
        预测行动的结果

        基于世界模型中的已有规律，预测这次行动最可能的结果。
        如果没有相关经验，返回低置信度的默认预测。

        Args:
            action: 要执行的动作（如 "run_tests", "edit_file", "deploy"）
            context: 行动的上下文信息

        Returns:
            Prediction 对象
        """
        context_summary = self._summarize_context(context)
        pattern_key = self._make_pattern_key(action, context)

        # 查找世界模型中的相关条目
        entry = self._world_model.get(pattern_key)

        if entry and entry.confidence > 0.3:
            # 有经验，基于经验预测
            return Prediction(
                action=action,
                context_summary=context_summary,
                predicted_outcome=entry.pattern,
                confidence=entry.confidence,
                reasoning=f"基于 {entry.hit_count + entry.miss_count} 次历史经验，准确率 {entry.accuracy:.0%}",
            )

        # 查找类似模式（模糊匹配）
        similar = self._find_similar_patterns(action, context)
        if similar:
            best_match = similar[0]
            return Prediction(
                action=action,
                context_summary=context_summary,
                predicted_outcome=best_match.pattern,
                confidence=best_match.confidence * 0.6,  # 类似模式降低信心
                reasoning=f"基于类似经验推断（信心打折）",
            )

        # 完全没有经验
        return Prediction(
            action=action,
            context_summary=context_summary,
            predicted_outcome="unknown",
            confidence=0.1,
            reasoning="没有相关经验，无法预测",
        )

    def learn(
        self,
        action: str,
        context: Dict[str, Any],
        prediction: Prediction,
        actual_outcome: str,
    ) -> PredictionError:
        """
        从实际结果中学习

        对比预测和实际结果:
        - 如果预测正确 → 强化世界模型中的规则
        - 如果预测错误 → 产生学习信号，更新世界模型

        Args:
            action: 执行的动作
            context: 行动的上下文
            prediction: 之前的预测
            actual_outcome: 实际结果

        Returns:
            PredictionError 对象（包含学习信号）
        """
        pattern_key = self._make_pattern_key(action, context)
        magnitude = self._compute_error_magnitude(prediction.predicted_outcome, actual_outcome)
        surprise = self._classify_surprise(magnitude, prediction.confidence)

        # 生成学习教训
        lesson = self._extract_lesson(action, context, prediction, actual_outcome, magnitude)

        # 更新世界模型
        self._update_world_model(pattern_key, actual_outcome, magnitude, lesson)

        # 记录到历史
        error = PredictionError(
            action=action,
            predicted=prediction.predicted_outcome,
            actual=actual_outcome,
            magnitude=magnitude,
            surprise=surprise,
            lesson=lesson,
        )
        self._record_history(prediction, error)

        # 持久化
        self._save()

        logger.info(
            f"[Brain] 预测学习: action={action}, 预测={prediction.predicted_outcome}, "
            f"实际={actual_outcome}, 误差={magnitude:.2f}, 惊讶度={surprise}"
        )

        return error

    # ==================== 分析接口 ====================

    def get_accuracy(self, last_n: int = 50) -> float:
        """获取最近 N 次预测的准确率"""
        recent = self._prediction_history[-last_n:]
        if not recent:
            return 0.0
        correct = sum(1 for h in recent if h.get("magnitude", 1.0) < 0.3)
        return correct / len(recent)

    def get_learning_curve(self, window: int = 10) -> List[float]:
        """获取学习曲线（滑动窗口准确率）"""
        if len(self._prediction_history) < window:
            return []
        
        curve = []
        for i in range(window, len(self._prediction_history) + 1):
            batch = self._prediction_history[i - window:i]
            correct = sum(1 for h in batch if h.get("magnitude", 1.0) < 0.3)
            curve.append(correct / window)
        return curve

    def get_world_model_summary(self) -> str:
        """获取世界模型的人类可读摘要"""
        if not self._world_model:
            return "世界模型为空（尚未学习到任何规律）"

        lines = [f"世界模型包含 {len(self._world_model)} 条规律:\n"]

        # 按信心排序
        sorted_entries = sorted(
            self._world_model.items(),
            key=lambda x: x[1].confidence,
            reverse=True,
        )

        for key, entry in sorted_entries[:20]:
            lines.append(
                f"  [{entry.confidence:.0%}] {entry.pattern} "
                f"(验证 {entry.hit_count}次, 反驳 {entry.miss_count}次)"
            )

        return "\n".join(lines)

    def get_surprises(self, threshold: float = 0.7, last_n: int = 100) -> List[Dict[str, Any]]:
        """获取最近的高惊讶度事件（值得关注的意外）"""
        recent = self._prediction_history[-last_n:]
        return [h for h in recent if h.get("magnitude", 0) > threshold]

    # ==================== 内部方法 ====================

    def _make_pattern_key(self, action: str, context: Dict[str, Any]) -> str:
        """生成模式键（用于世界模型索引）"""
        # 提取关键上下文特征
        key_parts = [action]

        # 添加重要的上下文键值
        important_keys = ["file", "type", "target", "tool", "state", "error_type"]
        for k in important_keys:
            if k in context:
                key_parts.append(f"{k}={context[k]}")

        return "::".join(key_parts)

    def _summarize_context(self, context: Dict[str, Any]) -> str:
        """压缩上下文为可读摘要"""
        parts = []
        for k, v in list(context.items())[:5]:
            v_str = str(v)[:50]
            parts.append(f"{k}={v_str}")
        return ", ".join(parts) if parts else "(empty)"

    def _find_similar_patterns(self, action: str, context: Dict[str, Any]) -> List[WorldModelEntry]:
        """查找世界模型中的相似模式"""
        results = []
        for key, entry in self._world_model.items():
            if key.startswith(action + "::"):
                results.append(entry)
        # 按信心排序
        results.sort(key=lambda e: e.confidence, reverse=True)
        return results[:3]

    def _compute_error_magnitude(self, predicted: str, actual: str) -> float:
        """计算预测误差大小（0=完全正确，1=完全错误）"""
        if predicted == actual:
            return 0.0
        if predicted == "unknown":
            return 0.5  # 没有预测不算大错

        # 简单的文本相似度判断
        pred_lower = predicted.lower()
        actual_lower = actual.lower()

        # 同类结果（都是成功/失败）
        success_words = {"success", "pass", "ok", "done", "complete", "成功", "通过"}
        failure_words = {"fail", "error", "exception", "crash", "timeout", "失败", "错误"}

        pred_is_success = any(w in pred_lower for w in success_words)
        pred_is_failure = any(w in pred_lower for w in failure_words)
        actual_is_success = any(w in actual_lower for w in success_words)
        actual_is_failure = any(w in actual_lower for w in failure_words)

        if pred_is_success and actual_is_success:
            return 0.1  # 细节不同但方向正确
        if pred_is_failure and actual_is_failure:
            return 0.2  # 都失败了，细节不同

        if (pred_is_success and actual_is_failure) or (pred_is_failure and actual_is_success):
            return 0.9  # 方向完全相反

        # 默认中等误差
        return 0.5

    def _classify_surprise(self, magnitude: float, confidence: float) -> str:
        """分类惊讶程度"""
        # 高信心 + 大误差 = 非常惊讶
        surprise_score = magnitude * confidence
        if surprise_score > 0.7:
            return "high"
        elif surprise_score > 0.4:
            return "medium"
        elif surprise_score > 0.1:
            return "low"
        return "none"

    def _extract_lesson(
        self,
        action: str,
        context: Dict[str, Any],
        prediction: Prediction,
        actual: str,
        magnitude: float,
    ) -> str:
        """从一次经验中提取教训"""
        if magnitude < 0.2:
            return f"验证：{action} 在此条件下表现符合预期"

        context_str = self._summarize_context(context)
        return (
            f"当 context=[{context_str}] 时，执行 {action} "
            f"预期 '{prediction.predicted_outcome}' 但实际是 '{actual}'"
        )

    def _update_world_model(
        self,
        pattern_key: str,
        actual_outcome: str,
        magnitude: float,
        lesson: str,
    ) -> None:
        """更新世界模型"""
        if pattern_key in self._world_model:
            entry = self._world_model[pattern_key]

            if magnitude < 0.3:
                # 预测基本正确 → 强化
                entry.hit_count += 1
                entry.confidence = min(0.99, entry.confidence + 0.05 * (1 - entry.confidence))
            else:
                # 预测错误 → 削弱旧规则，更新为新结果
                entry.miss_count += 1
                entry.confidence = max(0.1, entry.confidence - 0.1)

                # 如果错误次数超过正确次数，更新模式
                if entry.miss_count > entry.hit_count:
                    entry.pattern = actual_outcome
                    entry.hit_count = 1
                    entry.miss_count = 0
                    entry.confidence = 0.4

            entry.last_updated = time.time()
            entry.evidence.append(lesson)
            if len(entry.evidence) > 5:
                entry.evidence = entry.evidence[-5:]
        else:
            # 新模式
            self._world_model[pattern_key] = WorldModelEntry(
                pattern=actual_outcome,
                confidence=0.4,  # 初始信心不高（一次不够）
                hit_count=1,
                miss_count=0,
                evidence=[lesson],
            )

    def _record_history(self, prediction: Prediction, error: PredictionError) -> None:
        """记录到预测历史"""
        self._prediction_history.append({
            "action": prediction.action,
            "predicted": prediction.predicted_outcome,
            "actual": error.actual,
            "magnitude": error.magnitude,
            "confidence": prediction.confidence,
            "surprise": error.surprise,
            "timestamp": time.time(),
        })

        # 限制历史大小
        if len(self._prediction_history) > self._max_history:
            self._prediction_history = self._prediction_history[-self._max_history:]

    # ==================== 持久化 ====================

    def _save(self) -> None:
        """保存世界模型到文件"""
        try:
            data = {
                "world_model": {k: v.to_dict() for k, v in self._world_model.items()},
                "prediction_history": self._prediction_history[-200:],  # 只保存最近200条
                "saved_at": datetime.now().isoformat(),
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存世界模型失败: {e}")

    def _load(self) -> None:
        """从文件加载世界模型"""
        if not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._world_model = {
                k: WorldModelEntry.from_dict(v)
                for k, v in data.get("world_model", {}).items()
            }
            self._prediction_history = data.get("prediction_history", [])
            logger.info(f"加载世界模型: {len(self._world_model)} 条规律")
        except Exception as e:
            logger.error(f"加载世界模型失败: {e}")
