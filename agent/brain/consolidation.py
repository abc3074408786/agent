"""
记忆整合（Memory Consolidation）— Agent 的"睡眠"

模拟海马体的记忆整合功能：
- 人类白天收集经验，晚上睡觉时大脑整合记忆
- Agent 也需要定期"离线整合"：回顾经历、提取规律、压缩存储

整合过程包括：
1. 经验回放（Experience Replay）— 回放最近的重要经历
2. 模式提取（Pattern Extraction）— 从经历中发现重复模式
3. 知识更新（Knowledge Update）— 将模式转化为长期知识
4. 选择性遗忘（Selective Forgetting）— 丢弃不重要的细节
5. 创造性联想（Creative Association）— 发现意外的跨领域联系

使用示例:
    consolidation = MemoryConsolidation()

    # 记录经验
    consolidation.record_experience(
        action="fix_bug",
        context={"file": "auth.py", "error": "NoneType"},
        outcome="success",
        importance=0.8,
    )

    # 定期触发整合（Agent 的"睡眠"）
    insights = consolidation.consolidate()
    # → [Insight(pattern="auth.py 经常出现 NoneType 错误", confidence=0.7)]
"""

import json
import time
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExperienceRecord:
    """一条经验记录"""
    action: str                    # 执行的动作
    context: Dict[str, Any]        # 上下文
    outcome: str                   # 结果
    importance: float = 0.5        # 重要度 0.0-1.0
    emotional_valence: float = 0.0 # 情绪色彩 -1(负面)到+1(正面)
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperienceRecord":
        return cls(**data)

    @property
    def age_hours(self) -> float:
        """经验的年龄（小时）"""
        return (time.time() - self.timestamp) / 3600


@dataclass
class Insight:
    """从整合中发现的洞察/规律"""
    pattern: str                   # 规律描述
    confidence: float              # 置信度 0.0-1.0
    category: str                  # 类型：pattern, rule, warning, suggestion
    evidence_count: int = 0        # 支持证据数量
    source_experiences: List[str] = field(default_factory=list)  # 来源经验摘要
    created_at: float = field(default_factory=time.time)
    is_novel: bool = False         # 是否是新发现的（创造性联想）

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Insight":
        return cls(**data)


class MemoryConsolidation:
    """
    记忆整合系统 — Agent 的"睡眠"过程

    核心功能:
    1. record_experience() — 记录日常经验
    2. consolidate() — 触发整合（发现规律）
    3. get_insights() — 获取已发现的洞察
    4. forget() — 选择性遗忘
    """

    def __init__(self, storage_path: Optional[str] = None, max_experiences: int = 500):
        """
        Args:
            storage_path: 存储路径，默认 ~/.agent/brain/experiences.json
            max_experiences: 最大经验记录数
        """
        if storage_path:
            self._storage_path = Path(storage_path)
        else:
            self._storage_path = Path.home() / ".agent" / "brain" / "consolidation.json"
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._max_experiences = max_experiences
        self._experiences: List[ExperienceRecord] = []
        self._insights: List[Insight] = []
        self._consolidation_count = 0
        self._last_consolidation: Optional[float] = None

        self._load()

    # ==================== 记录经验 ====================

    def record_experience(
        self,
        action: str,
        context: Dict[str, Any],
        outcome: str,
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        tags: Optional[List[str]] = None,
    ) -> None:
        """
        记录一条经验

        每次 Agent 执行动作后调用，记录"发生了什么"。

        Args:
            action: 执行的动作
            context: 上下文信息
            outcome: 实际结果
            importance: 重要度（失败/成功的经验更重要）
            emotional_valence: 情绪色彩（负面经验更容易被记住）
            tags: 标签
        """
        record = ExperienceRecord(
            action=action,
            context=context,
            outcome=outcome,
            importance=importance,
            emotional_valence=emotional_valence,
            tags=tags or [],
        )
        self._experiences.append(record)

        # 自动限制数量
        if len(self._experiences) > self._max_experiences:
            self._forget_least_important()

        logger.debug(
            f"[Consolidation] 记录经验: {action} → {outcome[:50]} "
            f"(重要度:{importance:.1f})"
        )

    # ==================== 核心：整合过程 ====================

    def consolidate(self) -> List[Insight]:
        """
        触发记忆整合 — Agent 的"睡眠"

        整合流程:
        1. 选择待整合的经验（最近的 + 高重要度的）
        2. 经验回放（重新审视）
        3. 模式提取（发现重复规律）
        4. 跨领域联想（发现意外联系）
        5. 选择性遗忘（清理不重要的细节）
        6. 生成洞察

        Returns:
            新发现的 Insight 列表
        """
        self._consolidation_count += 1
        self._last_consolidation = time.time()

        logger.info(f"[Consolidation] 开始第 {self._consolidation_count} 次整合...")

        new_insights: List[Insight] = []

        # 1. 选择要整合的经验
        to_consolidate = self._select_for_consolidation()
        if len(to_consolidate) < 3:
            logger.info("[Consolidation] 经验不足，跳过整合")
            return []

        # 2. 模式提取 — 找到频繁出现的 action+outcome 组合
        pattern_insights = self._extract_patterns(to_consolidate)
        new_insights.extend(pattern_insights)

        # 3. 上下文关联 — 发现什么上下文导致什么结果
        context_insights = self._extract_context_rules(to_consolidate)
        new_insights.extend(context_insights)

        # 4. 时序模式 — 发现"先做A再做B效果好"的规律
        sequence_insights = self._extract_sequences(to_consolidate)
        new_insights.extend(sequence_insights)

        # 5. 异常检测 — 发现不寻常的事件
        anomaly_insights = self._detect_anomalies(to_consolidate)
        new_insights.extend(anomaly_insights)

        # 6. 选择性遗忘
        self._selective_forget()

        # 去重并合并到已有洞察
        truly_new = self._merge_insights(new_insights)

        # 持久化
        self._save()

        logger.info(
            f"[Consolidation] 整合完成: 处理 {len(to_consolidate)} 条经验, "
            f"发现 {len(truly_new)} 条新洞察"
        )

        return truly_new

    # ==================== 查询接口 ====================

    def get_insights(
        self,
        category: Optional[str] = None,
        min_confidence: float = 0.3,
    ) -> List[Insight]:
        """获取洞察列表"""
        results = self._insights
        if category:
            results = [i for i in results if i.category == category]
        results = [i for i in results if i.confidence >= min_confidence]
        return sorted(results, key=lambda i: i.confidence, reverse=True)

    def get_relevant_insights(self, action: str, context: Dict[str, Any]) -> List[Insight]:
        """
        获取与当前行动相关的洞察

        用于在执行动作前，提供历史经验建议。
        """
        relevant = []
        action_lower = action.lower()
        context_str = json.dumps(context, ensure_ascii=False).lower()

        for insight in self._insights:
            pattern_lower = insight.pattern.lower()
            # 匹配动作
            if action_lower in pattern_lower:
                relevant.append(insight)
            # 匹配上下文关键词
            elif any(k.lower() in pattern_lower for k in context.keys()):
                relevant.append(insight)
            # 匹配上下文值
            elif any(str(v).lower() in pattern_lower for v in context.values() if v):
                relevant.append(insight)

        return sorted(relevant, key=lambda i: i.confidence, reverse=True)[:5]

    def get_experience_stats(self) -> Dict[str, Any]:
        """获取经验统计"""
        if not self._experiences:
            return {"total": 0}

        action_counts = Counter(e.action for e in self._experiences)
        outcome_counts = Counter(e.outcome.split(":")[0] for e in self._experiences)

        return {
            "total_experiences": len(self._experiences),
            "total_insights": len(self._insights),
            "consolidation_count": self._consolidation_count,
            "top_actions": action_counts.most_common(5),
            "outcome_distribution": dict(outcome_counts.most_common(5)),
            "avg_importance": sum(e.importance for e in self._experiences) / len(self._experiences),
        }

    def get_summary(self) -> str:
        """获取人类可读摘要"""
        stats = self.get_experience_stats()
        lines = [
            f"记忆整合系统状态:",
            f"  经验记录: {stats.get('total_experiences', 0)} 条",
            f"  洞察发现: {stats.get('total_insights', 0)} 条",
            f"  整合次数: {stats.get('consolidation_count', 0)} 次",
        ]

        if self._insights:
            lines.append(f"\n  最新洞察:")
            for insight in self._insights[-3:]:
                lines.append(f"    [{insight.confidence:.0%}] {insight.pattern}")

        return "\n".join(lines)

    # ==================== 内部方法：整合算法 ====================

    def _select_for_consolidation(self) -> List[ExperienceRecord]:
        """选择需要整合的经验"""
        # 优先选择：最近的 + 高重要度的 + 高情绪的
        scored = []
        for exp in self._experiences:
            recency = max(0, 1.0 - exp.age_hours / 24.0)  # 24小时内的更重要
            emotion_weight = abs(exp.emotional_valence) * 0.3
            score = exp.importance * 0.5 + recency * 0.3 + emotion_weight + 0.2
            scored.append((score, exp))

        scored.sort(key=lambda x: x[0], reverse=True)
        # 取前 50%
        n = max(10, len(scored) // 2)
        return [exp for _, exp in scored[:n]]

    def _extract_patterns(self, experiences: List[ExperienceRecord]) -> List[Insight]:
        """提取频繁模式"""
        insights = []

        # 1. 动作-结果 频率统计
        action_outcomes: Dict[str, List[str]] = defaultdict(list)
        for exp in experiences:
            action_outcomes[exp.action].append(exp.outcome)

        for action, outcomes in action_outcomes.items():
            if len(outcomes) < 2:
                continue

            outcome_counts = Counter(outcomes)
            total = len(outcomes)

            for outcome, count in outcome_counts.most_common(3):
                ratio = count / total
                if ratio > 0.5 and count >= 2:
                    insight = Insight(
                        pattern=f"执行 '{action}' 时，{ratio:.0%} 的情况结果是 '{outcome}'",
                        confidence=min(0.9, ratio * (count / 5)),
                        category="pattern",
                        evidence_count=count,
                        source_experiences=[f"{action}→{outcome}" for _ in range(min(3, count))],
                    )
                    insights.append(insight)

        return insights

    def _extract_context_rules(self, experiences: List[ExperienceRecord]) -> List[Insight]:
        """提取上下文→结果 规则"""
        insights = []

        # 找出什么上下文条件导致特定结果
        context_outcomes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for exp in experiences:
            for key, value in exp.context.items():
                ctx_feature = f"{key}={value}"
                # 简化 outcome
                simple_outcome = "success" if "success" in exp.outcome.lower() or "pass" in exp.outcome.lower() else "failure" if "fail" in exp.outcome.lower() or "error" in exp.outcome.lower() else "other"
                context_outcomes[ctx_feature][simple_outcome] += 1

        for ctx_feature, outcomes in context_outcomes.items():
            total = sum(outcomes.values())
            if total < 3:
                continue

            for outcome, count in outcomes.items():
                ratio = count / total
                if ratio > 0.6 and count >= 2:
                    insight = Insight(
                        pattern=f"当 {ctx_feature} 时，结果倾向于 '{outcome}'（{ratio:.0%}）",
                        confidence=min(0.8, ratio * 0.8),
                        category="rule",
                        evidence_count=count,
                    )
                    insights.append(insight)

        return insights

    def _extract_sequences(self, experiences: List[ExperienceRecord]) -> List[Insight]:
        """提取时序模式（A之后通常做B）"""
        insights = []

        # 按时间排序
        sorted_exps = sorted(experiences, key=lambda e: e.timestamp)

        # 找连续的动作对
        action_pairs: Dict[Tuple[str, str], int] = Counter()
        for i in range(len(sorted_exps) - 1):
            # 只看 5 分钟内的连续动作
            if sorted_exps[i + 1].timestamp - sorted_exps[i].timestamp < 300:
                pair = (sorted_exps[i].action, sorted_exps[i + 1].action)
                action_pairs[pair] += 1

        for (a1, a2), count in action_pairs.most_common(5):
            if count >= 2 and a1 != a2:
                insight = Insight(
                    pattern=f"'{a1}' 之后通常会执行 '{a2}'（观察到 {count} 次）",
                    confidence=min(0.7, count * 0.15),
                    category="sequence",
                    evidence_count=count,
                )
                insights.append(insight)

        return insights

    def _detect_anomalies(self, experiences: List[ExperienceRecord]) -> List[Insight]:
        """检测异常事件"""
        insights = []

        # 找高重要度 + 负面情绪的经验
        for exp in experiences:
            if exp.importance > 0.8 and exp.emotional_valence < -0.5:
                insight = Insight(
                    pattern=f"注意：执行 '{exp.action}' 时遇到严重问题 → {exp.outcome[:80]}",
                    confidence=0.6,
                    category="warning",
                    evidence_count=1,
                    source_experiences=[f"{exp.action} at {datetime.fromtimestamp(exp.timestamp).strftime('%H:%M')}"],
                )
                insights.append(insight)

        return insights

    def _selective_forget(self) -> None:
        """
        选择性遗忘

        遗忘规则:
        - 低重要度 + 旧的经验 → 遗忘
        - 高重要度 or 情绪强烈 → 保留
        - 已产生洞察的经验细节可以遗忘（规律已提取）
        """
        if len(self._experiences) <= self._max_experiences // 2:
            return  # 还没必要遗忘

        to_keep = []
        forgotten = 0

        for exp in self._experiences:
            # 保留条件：重要 or 新 or 情绪强
            keep_score = (
                exp.importance * 0.4
                + (1.0 - min(1.0, exp.age_hours / 72.0)) * 0.3  # 3天内的保留
                + abs(exp.emotional_valence) * 0.3
            )

            if keep_score > 0.3:
                to_keep.append(exp)
            else:
                forgotten += 1

        self._experiences = to_keep

        if forgotten > 0:
            logger.info(f"[Consolidation] 选择性遗忘 {forgotten} 条经验")

    def _forget_least_important(self) -> None:
        """当经验超出上限时，遗忘最不重要的"""
        n_to_remove = len(self._experiences) - self._max_experiences + 50
        if n_to_remove <= 0:
            return

        # 按"可遗忘度"排序
        scored = sorted(
            self._experiences,
            key=lambda e: e.importance + abs(e.emotional_valence) - e.age_hours / 100,
        )
        self._experiences = scored[n_to_remove:]

    def _merge_insights(self, new_insights: List[Insight]) -> List[Insight]:
        """合并新洞察，去重"""
        truly_new = []
        for new in new_insights:
            is_duplicate = False
            for existing in self._insights:
                # 简单去重：模式文本高度相似
                if self._text_similarity(new.pattern, existing.pattern) > 0.7:
                    # 合并：更新置信度和证据
                    existing.confidence = max(existing.confidence, new.confidence)
                    existing.evidence_count += new.evidence_count
                    is_duplicate = True
                    break

            if not is_duplicate:
                self._insights.append(new)
                truly_new.append(new)

        return truly_new

    def _text_similarity(self, a: str, b: str) -> float:
        """简单文本相似度（Jaccard on words）"""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    # ==================== 持久化 ====================

    def _save(self) -> None:
        """保存到文件"""
        try:
            data = {
                "experiences": [e.to_dict() for e in self._experiences[-200:]],
                "insights": [i.to_dict() for i in self._insights],
                "consolidation_count": self._consolidation_count,
                "last_consolidation": self._last_consolidation,
                "saved_at": datetime.now().isoformat(),
            }
            with open(self._storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存整合数据失败: {e}")

    def _load(self) -> None:
        """从文件加载"""
        if not self._storage_path.exists():
            return
        try:
            with open(self._storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._experiences = [ExperienceRecord.from_dict(e) for e in data.get("experiences", [])]
            self._insights = [Insight.from_dict(i) for i in data.get("insights", [])]
            self._consolidation_count = data.get("consolidation_count", 0)
            self._last_consolidation = data.get("last_consolidation")
            logger.info(
                f"加载整合数据: {len(self._experiences)} 条经验, "
                f"{len(self._insights)} 条洞察"
            )
        except Exception as e:
            logger.error(f"加载整合数据失败: {e}")
