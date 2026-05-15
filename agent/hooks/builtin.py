"""
内置 Hooks - 预制生命周期钩子

参考 ECC 的自动化 hooks:
- memory_persist: 自动保存对话摘要到记忆
- security_scan: 工具调用前安全检查
- cost_tracker: Token 用量和成本追踪
- auto_compact: 上下文接近上限时自动压缩
- error_reporter: 错误自动上报和分类
"""

import time
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from agent.hooks import HookEvent, HookContext, HookManager

import logging
logger = logging.getLogger(__name__)


# ============ Memory Persist Hook ============

class MemoryPersistHook:
    """
    记忆持久化钩子

    在每次查询结束后，自动提取关键信息保存到会话记忆
    """

    def __init__(self, max_memory_items: int = 50):
        self._max_items = max_memory_items
        self._memory: List[Dict[str, Any]] = []

    def register(self, manager: HookManager) -> None:
        manager.register(HookEvent.POST_QUERY, self._on_post_query, name="memory_persist")

    def _on_post_query(self, context: HookContext) -> None:
        """查询完成后保存关键信息"""
        data = context.data
        if not data:
            return

        # 提取关键信息
        memory_item = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": context.session_id,
            "query_summary": data.get("query", "")[:200],
            "result_summary": data.get("result", "")[:500],
            "tools_used": data.get("tools_used", []),
            "iterations": data.get("iterations", 0),
        }

        self._memory.append(memory_item)

        # 限制大小
        if len(self._memory) > self._max_items:
            self._memory = self._memory[-self._max_items:]

    @property
    def memories(self) -> List[Dict[str, Any]]:
        return list(self._memory)

    def get_context_summary(self) -> str:
        """生成记忆摘要 (可注入到系统提示)"""
        if not self._memory:
            return ""

        recent = self._memory[-5:]
        lines = ["## 最近交互记忆"]
        for m in recent:
            lines.append(f"- [{m['timestamp'][:16]}] {m['query_summary'][:100]}")
        return "\n".join(lines)


# ============ Security Scan Hook ============

class SecurityScanHook:
    """
    安全扫描钩子

    在工具调用前检查潜在的安全风险
    """

    # 危险命令模式
    DANGEROUS_PATTERNS = [
        "rm -rf /",
        "rm -rf ~",
        ":(){ :|:& };:",  # fork bomb
        "dd if=/dev/zero",
        "mkfs.",
        "chmod 777",
        "> /dev/sda",
        "curl | bash",
        "wget | sh",
    ]

    # 敏感文件路径
    SENSITIVE_PATHS = [
        "/etc/passwd", "/etc/shadow",
        ".env", ".ssh/", "id_rsa",
        "credentials", "secrets",
    ]

    def __init__(self, block_on_threat: bool = True):
        self._block = block_on_threat
        self._alerts: List[Dict[str, Any]] = []

    def register(self, manager: HookManager) -> None:
        manager.register(
            HookEvent.PRE_TOOL_USE,
            self._on_pre_tool,
            name="security_scan",
            priority=10,  # 高优先级
        )

    def _on_pre_tool(self, context: HookContext) -> None:
        """工具调用前安全检查"""
        data = context.data
        tool_name = data.get("tool_name", "")
        arguments = data.get("arguments", {})
        args_str = json.dumps(arguments, default=str).lower()

        threats = []

        # 检查危险命令
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in args_str:
                threats.append(f"Dangerous command detected: {pattern}")

        # 检查敏感文件访问
        for path in self.SENSITIVE_PATHS:
            if path.lower() in args_str:
                threats.append(f"Sensitive file access: {path}")

        if threats:
            alert = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool": tool_name,
                "threats": threats,
                "arguments": arguments,
                "blocked": self._block,
            }
            self._alerts.append(alert)
            logger.warning(f"Security alert: {threats}")

            if self._block:
                context.cancelled = True
                context.data["blocked_reason"] = "; ".join(threats)

    @property
    def alerts(self) -> List[Dict[str, Any]]:
        return list(self._alerts)


# ============ Cost Tracker Hook ============

class CostTrackerHook:
    """
    成本追踪钩子

    追踪 Token 用量和 API 调用成本
    """

    # 简化的定价 (USD per 1M tokens)
    PRICING = {
        "gpt-4": {"input": 30, "output": 60},
        "gpt-4o": {"input": 5, "output": 15},
        "gpt-4o-mini": {"input": 0.15, "output": 0.6},
        "claude-3-opus": {"input": 15, "output": 75},
        "claude-3-sonnet": {"input": 3, "output": 15},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }

    def __init__(self, budget_usd: Optional[float] = None):
        self._budget = budget_usd
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._query_count = 0
        self._history: List[Dict[str, Any]] = []

    def register(self, manager: HookManager) -> None:
        manager.register(HookEvent.POST_QUERY, self._on_post_query, name="cost_tracker")

    def _on_post_query(self, context: HookContext) -> None:
        data = context.data
        model = data.get("model", "gpt-4o")
        input_tokens = data.get("input_tokens", 0)
        output_tokens = data.get("output_tokens", 0)

        # 计算成本
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o"])
        cost = (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )

        self._total_cost += cost
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._query_count += 1

        self._history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
        })

        # 预算检查
        if self._budget and self._total_cost >= self._budget:
            context.data["budget_exceeded"] = True
            logger.warning(f"Budget exceeded: ${self._total_cost:.4f} >= ${self._budget:.4f}")

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "total_cost_usd": round(self._total_cost, 6),
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "query_count": self._query_count,
            "budget_usd": self._budget,
            "budget_remaining": round(self._budget - self._total_cost, 6) if self._budget else None,
        }


# ============ Auto Compact Hook ============

class AutoCompactHook:
    """
    自动压缩钩子

    当上下文接近 token 上限时自动触发压缩
    """

    def __init__(
        self,
        context_window: int = 200000,
        compact_threshold: float = 0.85,
    ):
        self._context_window = context_window
        self._threshold = compact_threshold
        self._compact_count = 0

    def register(self, manager: HookManager) -> None:
        manager.register(HookEvent.PRE_QUERY, self._on_pre_query, name="auto_compact")

    def _on_pre_query(self, context: HookContext) -> None:
        data = context.data
        current_tokens = data.get("current_tokens", 0)

        if current_tokens > 0:
            ratio = current_tokens / self._context_window
            if ratio >= self._threshold:
                context.data["needs_compact"] = True
                context.data["token_ratio"] = ratio
                self._compact_count += 1
                logger.info(f"Auto-compact triggered: {ratio:.1%} usage")


# ============ Error Reporter Hook ============

class ErrorReporterHook:
    """
    错误上报钩子

    收集和分类错误，用于后续分析
    """

    def __init__(self, max_errors: int = 100):
        self._max_errors = max_errors
        self._errors: List[Dict[str, Any]] = []

    def register(self, manager: HookManager) -> None:
        manager.register(HookEvent.ON_ERROR, self._on_error, name="error_reporter")

    def _on_error(self, context: HookContext) -> None:
        data = context.data
        error = data.get("error", "")
        error_type = data.get("error_type", "unknown")

        self._errors.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "message": str(error)[:500],
            "session_id": context.session_id,
            "trace_id": context.trace_id,
        })

        if len(self._errors) > self._max_errors:
            self._errors = self._errors[-self._max_errors:]

    @property
    def errors(self) -> List[Dict[str, Any]]:
        return list(self._errors)

    @property
    def error_count(self) -> int:
        return len(self._errors)

    def get_error_summary(self) -> Dict[str, int]:
        """按类型统计错误"""
        summary: Dict[str, int] = {}
        for e in self._errors:
            t = e["error_type"]
            summary[t] = summary.get(t, 0) + 1
        return summary


# ============ 注册所有内置钩子 ============

def register_builtin_hooks(
    manager: HookManager,
    enable_memory: bool = True,
    enable_security: bool = True,
    enable_cost: bool = True,
    enable_compact: bool = True,
    enable_errors: bool = True,
    budget_usd: Optional[float] = None,
    context_window: int = 200000,
) -> Dict[str, Any]:
    """
    注册所有内置钩子

    Returns:
        钩子实例字典 (用于后续查询状态)
    """
    hooks = {}

    if enable_memory:
        hook = MemoryPersistHook()
        hook.register(manager)
        hooks["memory"] = hook

    if enable_security:
        hook = SecurityScanHook()
        hook.register(manager)
        hooks["security"] = hook

    if enable_cost:
        hook = CostTrackerHook(budget_usd=budget_usd)
        hook.register(manager)
        hooks["cost"] = hook

    if enable_compact:
        hook = AutoCompactHook(context_window=context_window)
        hook.register(manager)
        hooks["compact"] = hook

    if enable_errors:
        hook = ErrorReporterHook()
        hook.register(manager)
        hooks["errors"] = hook

    logger.info(f"Registered {len(hooks)} builtin hooks")
    return hooks


__all__ = [
    "MemoryPersistHook",
    "SecurityScanHook",
    "CostTrackerHook",
    "AutoCompactHook",
    "ErrorReporterHook",
    "register_builtin_hooks",
]
