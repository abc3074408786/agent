"""
MetacognitionEngine: 7 self-awareness capabilities.
Makes the Agent know when it doesn't know, ask questions,
refuse impossible tasks, backtrack, prioritize, and know when done.
"""

from __future__ import annotations
import re
import time
from typing import Any, Optional
from dataclasses import dataclass, field


@dataclass
class UncertaintySignal:
    topic: str
    confidence: float
    reason: str
    suggestion: str


@dataclass
class MissingInfo:
    what: str
    why_needed: str
    question: str


@dataclass
class FeasibilityReport:
    feasible: bool
    confidence: float
    blockers: list = field(default_factory=list)
    requirements: list = field(default_factory=list)
    estimated_steps: int = 0


class MetacognitionEngine:
    def __init__(self):
        self.critical_context: dict[str, Any] = {}
        self.rollback_points: list[dict] = []
        self.consecutive_failures: int = 0
        self.max_rollback = 10

    # 1. Uncertainty Detection
    def detect_uncertainty(self, query: str, context: str = "") -> Optional[UncertaintySignal]:
        indicators = [
            (r'\b(某个|那个|一些|可能|大概)\b', 0.4, "请求模糊"),
            (r'\b(怎么配置|如何部署|什么版本)\b', 0.3, "需要环境信息"),
        ]
        max_u = 0.0
        reason = ""
        for pattern, weight, desc in indicators:
            if re.search(pattern, query):
                if weight > max_u:
                    max_u = weight
                    reason = desc
        if context:
            q_topics = set(re.findall(r'[a-zA-Z_]\w{3,}', query.lower()))
            c_topics = set(re.findall(r'[a-zA-Z_]\w{3,}', context.lower()))
            unknown = q_topics - c_topics
            if len(unknown) > 3:
                max_u = max(max_u, 0.5)
                reason = f"{len(unknown)} 个未知概念"
        if max_u > 0.3:
            return UncertaintySignal(query[:50], 1.0 - max_u, reason,
                "建议确认" if max_u > 0.5 else "可尝试")
        return None

    # 2. Question Generation
    def identify_missing_info(self, task: str, context: dict = None) -> list[MissingInfo]:
        missing = []
        context = context or {}
        t = task.lower()
        checks = [
            ("文件" in t and not context.get("path"), "目标文件", "需要知道操作哪个文件", "要操作哪个文件？"),
            (any(w in t for w in ["部署", "deploy"]) and not context.get("env"), "目标环境", "环境不同配置不同", "部署到哪个环境？"),
            ("重构" in t and not context.get("scope"), "范围", "需要明确边界", "重构范围是什么？"),
            ("api" in t and not context.get("spec"), "API规格", "需要接口定义", "有API文档吗？"),
        ]
        for cond, what, why, q in checks:
            if cond:
                missing.append(MissingInfo(what, why, q))
        return missing[:3]

    # 3. Context Guard
    def mark_critical(self, key: str, value: Any) -> None:
        self.critical_context[key] = {"value": value, "time": time.time()}

    def get_critical_context(self) -> dict[str, Any]:
        return {k: v["value"] for k, v in self.critical_context.items()}

    def extract_critical(self, message: str) -> list[tuple[str, str]]:
        critical = []
        patterns = [
            (r'(?:不要|禁止|never)\s*(.+?)(?:\n|。|$)', "prohibition"),
            (r'(?:注意|important|必须)\s*(.+?)(?:\n|。|$)', "constraint"),
            (r'(?:版本|version)\s*[：:]\s*([\d.]+)', "version"),
        ]
        for pattern, cat in patterns:
            for match in re.findall(pattern, message, re.IGNORECASE):
                critical.append((cat, match.strip()))
                self.mark_critical(f"{cat}:{match[:20]}", match)
        return critical

    # 4. Feasibility Check
    def check_feasibility(self, task: str, tools: list[str] = None) -> FeasibilityReport:
        tools = tools or []
        blockers = []
        t = task.lower()
        impossible = [
            (r'预测.*(?:股票|彩票)', "无法预测随机事件"),
            (r'(?:破解|hack|入侵)', "不执行非法操作"),
        ]
        for pattern, reason in impossible:
            if re.search(pattern, t):
                blockers.append(reason)
        return FeasibilityReport(
            feasible=len(blockers) == 0,
            confidence=0.9 if not blockers else 0.1,
            blockers=blockers,
            estimated_steps=self._estimate_steps(t),
        )

    def _estimate_steps(self, t: str) -> int:
        for steps, kws in [(8, ["架构", "全栈"]), (5, ["重构", "部署"]), (3, ["创建", "实现"]), (2, ["修改"]), (1, ["查看"])]:
            if any(k in t for k in kws):
                return steps
        return 3

    # 5. Course Correction
    def save_rollback(self, desc: str, state: dict) -> str:
        pt = {"id": f"rb-{len(self.rollback_points)}", "desc": desc, "state": state, "time": time.time()}
        self.rollback_points.append(pt)
        if len(self.rollback_points) > self.max_rollback:
            self.rollback_points = self.rollback_points[-self.max_rollback:]
        return pt["id"]

    def record_result(self, success: bool) -> None:
        if success:
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

    def should_rollback(self) -> bool:
        return self.consecutive_failures >= 3

    def get_last_rollback(self) -> Optional[dict]:
        return self.rollback_points[-1] if self.rollback_points else None

    # 6. Priority Ranking
    def rank_tasks(self, tasks: list[str]) -> list[dict]:
        scored = [{"task": t, "score": self._priority(t)} for t in tasks]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def _priority(self, t: str) -> float:
        t = t.lower()
        s = 0.5
        if any(w in t for w in ["紧急", "崩了", "挂了", "urgent"]):
            s += 0.4
        if any(w in t for w in ["bug", "error", "修复"]):
            s += 0.3
        if any(w in t for w in ["安全", "漏洞"]):
            s += 0.35
        if any(w in t for w in ["以后", "有空", "文档"]):
            s -= 0.2
        return max(0.0, min(1.0, s))

    # 7. Completion Check
    def check_completion(self, goal: str, actions: list[str], results: list[dict]) -> dict:
        has_success = any(r.get("success") for r in results)
        goal_kws = set(re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z_]\w+', goal.lower()))
        action_text = " ".join(actions).lower()
        coverage = sum(1 for kw in goal_kws if kw in action_text) / max(len(goal_kws), 1)
        if has_success and coverage > 0.5:
            return {"done": True, "confidence": min(1.0, coverage + 0.3), "remaining": []}
        remaining = []
        if not has_success:
            remaining.append("未验证结果正确性")
        if coverage < 0.5:
            remaining.append(f"只完成约 {coverage:.0%}")
        return {"done": False, "confidence": coverage, "remaining": remaining}

    # Unified pre-check
    def pre_check(self, task: str, context: dict = None, tools: list[str] = None) -> dict:
        context = context or {}
        result = {"proceed": True, "warnings": [], "questions": []}
        u = self.detect_uncertainty(task, str(context))
        if u and u.confidence < 0.5:
            result["warnings"].append(f"不确定: {u.reason}")
            result["proceed"] = False
        missing = self.identify_missing_info(task, context)
        if missing:
            result["questions"] = [m.question for m in missing]
            if len(missing) >= 2:
                result["proceed"] = False
        f = self.check_feasibility(task, tools)
        if not f.feasible:
            result["proceed"] = False
            result["warnings"].extend(f.blockers)
        self.extract_critical(task)
        result["critical"] = self.get_critical_context()
        result["priority"] = self._priority(task)
        return result
