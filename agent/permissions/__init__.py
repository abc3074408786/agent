"""
Permission System - 工具执行权限控制

参考 Claude Code 权限模型:
- PermissionMode: default / auto / strict / bypass
- 规则匹配: allow / deny / ask
- 工具粒度权限控制
- 运行时权限上下文
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional, Set, Union
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent.observability import get_logger, get_tracer

logger = get_logger("permissions")
tracer = get_tracer("permissions")


# ============ 权限模式 ============

class PermissionMode(str, Enum):
    """权限模式"""
    DEFAULT = "default"       # 默认: 敏感操作需要确认
    AUTO = "auto"             # 自动: 自动批准所有操作
    STRICT = "strict"         # 严格: 所有操作都需要确认
    BYPASS = "bypass"         # 绕过: 完全跳过权限检查（仅开发环境）


class PermissionDecision(str, Enum):
    """权限决策"""
    ALLOW = "allow"           # 允许
    DENY = "deny"             # 拒绝
    ASK = "ask"               # 需要询问用户


class ToolRiskLevel(str, Enum):
    """工具风险等级"""
    LOW = "low"               # 低风险: 只读操作
    MEDIUM = "medium"         # 中等: 可能有副作用
    HIGH = "high"             # 高风险: 系统修改、网络请求
    CRITICAL = "critical"     # 关键: 不可逆操作


# ============ 权限规则 ============

@dataclass
class PermissionRule:
    """权限规则"""
    tool_pattern: str                    # 工具名称模式 (支持 glob)
    decision: PermissionDecision         # 权限决策
    conditions: Dict[str, Any] = field(default_factory=dict)  # 附加条件
    reason: Optional[str] = None         # 规则说明
    source: str = "config"               # 规则来源: config / runtime / user
    priority: int = 0                    # 优先级 (数字越大优先级越高)
    expires_at: Optional[datetime] = None  # 过期时间

    def matches(self, tool_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """检查规则是否匹配"""
        # 名称匹配 (支持 * 通配符)
        pattern = self.tool_pattern.replace("*", ".*")
        if not re.match(f"^{pattern}$", tool_name):
            return False

        # 过期检查
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False

        # 条件匹配
        if self.conditions and context:
            for key, value in self.conditions.items():
                if context.get(key) != value:
                    return False

        return True


@dataclass
class PermissionRequest:
    """权限请求"""
    tool_name: str
    action: str                          # 工具要执行的动作描述
    arguments: Dict[str, Any]            # 工具参数
    risk_level: ToolRiskLevel = ToolRiskLevel.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    trace_id: Optional[str] = None


@dataclass
class PermissionResult:
    """权限结果"""
    allowed: bool
    decision: PermissionDecision
    rule: Optional[PermissionRule] = None
    reason: Optional[str] = None
    expires_at: Optional[datetime] = None

    @staticmethod
    def allow(reason: str = "Allowed by rule") -> "PermissionResult":
        return PermissionResult(
            allowed=True,
            decision=PermissionDecision.ALLOW,
            reason=reason,
        )

    @staticmethod
    def deny(reason: str = "Denied by rule") -> "PermissionResult":
        return PermissionResult(
            allowed=False,
            decision=PermissionDecision.DENY,
            reason=reason,
        )

    @staticmethod
    def needs_approval(reason: str = "Requires user approval") -> "PermissionResult":
        return PermissionResult(
            allowed=False,
            decision=PermissionDecision.ASK,
            reason=reason,
        )


# ============ 权限处理器 ============

class PermissionHandler(ABC):
    """权限处理器抽象基类"""

    @abstractmethod
    async def handle_permission_request(
        self, request: PermissionRequest
    ) -> PermissionResult:
        """处理权限请求"""
        pass


class AutoApproveHandler(PermissionHandler):
    """自动批准处理器"""

    async def handle_permission_request(
        self, request: PermissionRequest
    ) -> PermissionResult:
        return PermissionResult.allow("Auto-approved")


class AutoDenyHandler(PermissionHandler):
    """自动拒绝处理器"""

    async def handle_permission_request(
        self, request: PermissionRequest
    ) -> PermissionResult:
        return PermissionResult.deny("Auto-denied in strict mode")


class CallbackPermissionHandler(PermissionHandler):
    """回调权限处理器 - 通过回调函数处理"""

    def __init__(self, callback: Callable[[PermissionRequest], bool]):
        self._callback = callback

    async def handle_permission_request(
        self, request: PermissionRequest
    ) -> PermissionResult:
        allowed = self._callback(request)
        if allowed:
            return PermissionResult.allow("Approved by callback")
        return PermissionResult.deny("Denied by callback")


# ============ 权限引擎 ============

class PermissionEngine:
    """
    权限引擎 - 核心权限决策逻辑

    工作流:
    1. 检查模式 (bypass → 直接允许)
    2. 按优先级匹配规则
    3. 根据规则决策或风险等级决定
    4. 需要询问时委托给 PermissionHandler
    """

    def __init__(
        self,
        mode: PermissionMode = PermissionMode.DEFAULT,
        handler: Optional[PermissionHandler] = None,
    ):
        self._mode = mode
        self._handler = handler or AutoApproveHandler()
        self._rules: List[PermissionRule] = []
        self._session_grants: Dict[str, Set[str]] = {}  # session_id -> granted tools
        self._denial_tracking: Dict[str, int] = {}      # tool_name -> denial count

    @property
    def mode(self) -> PermissionMode:
        return self._mode

    @mode.setter
    def mode(self, value: PermissionMode) -> None:
        logger.info(f"Permission mode changed", old_mode=self._mode.value, new_mode=value.value)
        self._mode = value

    def add_rule(self, rule: PermissionRule) -> None:
        """添加权限规则"""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added permission rule", pattern=rule.tool_pattern, decision=rule.decision.value)

    def add_rules(self, rules: List[PermissionRule]) -> None:
        """批量添加规则"""
        self._rules.extend(rules)
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def remove_rules(self, source: Optional[str] = None) -> int:
        """移除规则"""
        if source:
            before = len(self._rules)
            self._rules = [r for r in self._rules if r.source != source]
            return before - len(self._rules)
        else:
            count = len(self._rules)
            self._rules.clear()
            return count

    def grant_session_permission(self, session_id: str, tool_name: str) -> None:
        """授予会话级权限"""
        if session_id not in self._session_grants:
            self._session_grants[session_id] = set()
        self._session_grants[session_id].add(tool_name)

    @tracer.trace("permission.check")
    async def check_permission(self, request: PermissionRequest) -> PermissionResult:
        """
        检查权限

        决策流程:
        1. BYPASS 模式 → 允许
        2. 会话级已授权 → 允许
        3. 规则匹配 → 按规则决策
        4. 无匹配规则 → 按模式和风险等级决策
        """
        logger.debug(
            f"Checking permission",
            tool=request.tool_name,
            mode=self._mode.value,
            risk_level=request.risk_level.value,
        )

        # 1. BYPASS 模式
        if self._mode == PermissionMode.BYPASS:
            return PermissionResult.allow("Bypass mode")

        # 2. 会话级授权
        if request.session_id and request.session_id in self._session_grants:
            if request.tool_name in self._session_grants[request.session_id]:
                return PermissionResult.allow("Session grant")

        # 3. 规则匹配
        for rule in self._rules:
            if rule.matches(request.tool_name, request.context):
                if rule.decision == PermissionDecision.ALLOW:
                    return PermissionResult(
                        allowed=True,
                        decision=PermissionDecision.ALLOW,
                        rule=rule,
                        reason=rule.reason or "Allowed by rule",
                    )
                elif rule.decision == PermissionDecision.DENY:
                    self._track_denial(request.tool_name)
                    return PermissionResult(
                        allowed=False,
                        decision=PermissionDecision.DENY,
                        rule=rule,
                        reason=rule.reason or "Denied by rule",
                    )
                elif rule.decision == PermissionDecision.ASK:
                    return await self._handle_ask(request, rule)

        # 4. 按模式决策
        return await self._decide_by_mode(request)

    async def _decide_by_mode(self, request: PermissionRequest) -> PermissionResult:
        """按模式和风险等级决策"""
        if self._mode == PermissionMode.AUTO:
            return PermissionResult.allow("Auto mode")

        if self._mode == PermissionMode.STRICT:
            return await self._handle_ask(request)

        # DEFAULT 模式: 按风险等级
        if request.risk_level == ToolRiskLevel.LOW:
            return PermissionResult.allow("Low risk - auto approved")
        elif request.risk_level in (ToolRiskLevel.HIGH, ToolRiskLevel.CRITICAL):
            return await self._handle_ask(request)
        else:
            # MEDIUM: 委托给 handler
            return await self._handle_ask(request)

    async def _handle_ask(
        self, request: PermissionRequest, rule: Optional[PermissionRule] = None
    ) -> PermissionResult:
        """处理需要询问的情况"""
        result = await self._handler.handle_permission_request(request)

        # 如果批准了，记录会话级授权
        if result.allowed and request.session_id:
            self.grant_session_permission(request.session_id, request.tool_name)

        if not result.allowed:
            self._track_denial(request.tool_name)

        return result

    def _track_denial(self, tool_name: str) -> None:
        """追踪拒绝次数"""
        self._denial_tracking[tool_name] = self._denial_tracking.get(tool_name, 0) + 1

    def get_denial_count(self, tool_name: str) -> int:
        """获取拒绝次数"""
        return self._denial_tracking.get(tool_name, 0)

    def clear_session(self, session_id: str) -> None:
        """清除会话权限"""
        if session_id in self._session_grants:
            del self._session_grants[session_id]


# ============ 工具权限装饰器 ============

def require_permission(
    risk_level: ToolRiskLevel = ToolRiskLevel.MEDIUM,
    action_description: Optional[str] = None,
):
    """
    工具权限装饰器

    Example:
        @require_permission(risk_level=ToolRiskLevel.HIGH, action_description="Execute shell command")
        async def bash_tool(command: str) -> str:
            ...
    """
    def decorator(func):
        func._permission_risk_level = risk_level
        func._permission_action = action_description or func.__name__
        return func
    return decorator


# ============ 预定义规则集 ============

# 只读工具自动允许
READONLY_ALLOW_RULES = [
    PermissionRule(
        tool_pattern="calculator",
        decision=PermissionDecision.ALLOW,
        reason="Read-only math operation",
        source="builtin",
        priority=100,
    ),
    PermissionRule(
        tool_pattern="get_current_datetime",
        decision=PermissionDecision.ALLOW,
        reason="Read-only time query",
        source="builtin",
        priority=100,
    ),
    PermissionRule(
        tool_pattern="json_parse",
        decision=PermissionDecision.ALLOW,
        reason="Read-only JSON parsing",
        source="builtin",
        priority=100,
    ),
    PermissionRule(
        tool_pattern="text_process",
        decision=PermissionDecision.ALLOW,
        reason="Read-only text processing",
        source="builtin",
        priority=100,
    ),
]

# 高风险工具需要确认
HIGH_RISK_ASK_RULES = [
    PermissionRule(
        tool_pattern="http_request",
        decision=PermissionDecision.ASK,
        reason="Network request - may have side effects",
        source="builtin",
        priority=50,
    ),
    PermissionRule(
        tool_pattern="bash_*",
        decision=PermissionDecision.ASK,
        reason="Shell execution - potentially dangerous",
        source="builtin",
        priority=50,
    ),
    PermissionRule(
        tool_pattern="file_write*",
        decision=PermissionDecision.ASK,
        reason="File modification",
        source="builtin",
        priority=50,
    ),
]

DEFAULT_RULES = READONLY_ALLOW_RULES + HIGH_RISK_ASK_RULES


def create_permission_engine(
    mode: PermissionMode = PermissionMode.DEFAULT,
    handler: Optional[PermissionHandler] = None,
    use_default_rules: bool = True,
) -> PermissionEngine:
    """创建权限引擎"""
    engine = PermissionEngine(mode=mode, handler=handler)
    if use_default_rules:
        engine.add_rules(DEFAULT_RULES)
    return engine


__all__ = [
    # 枚举
    "PermissionMode",
    "PermissionDecision",
    "ToolRiskLevel",
    # 数据类
    "PermissionRule",
    "PermissionRequest",
    "PermissionResult",
    # 处理器
    "PermissionHandler",
    "AutoApproveHandler",
    "AutoDenyHandler",
    "CallbackPermissionHandler",
    # 引擎
    "PermissionEngine",
    # 装饰器
    "require_permission",
    # 预定义规则
    "DEFAULT_RULES",
    "READONLY_ALLOW_RULES",
    "HIGH_RISK_ASK_RULES",
    # 便捷函数
    "create_permission_engine",
]
