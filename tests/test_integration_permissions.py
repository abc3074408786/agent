"""
权限系统集成测试

测试 Permission 模块的完整行为:
- bypass 模式允许一切
- strict 模式 + AutoDenyHandler 全部拒绝
- 规则优先级
- 会话级授权持久化
"""
import pytest

from agent.permissions import (
    PermissionMode,
    PermissionDecision,
    ToolRiskLevel,
    PermissionRule,
    PermissionRequest,
    PermissionResult,
    PermissionEngine,
    AutoApproveHandler,
    AutoDenyHandler,
    CallbackPermissionHandler,
    create_permission_engine,
)


class TestBypassModeAllowsEverything:
    """bypass 模式下所有工具都允许"""

    @pytest.mark.asyncio
    async def test_bypass_mode_allows_everything(self):
        """BYPASS 模式下任何请求都被允许"""
        engine = PermissionEngine(
            mode=PermissionMode.BYPASS,
            handler=AutoDenyHandler(),  # 即使用拒绝处理器
        )

        # 高风险工具也应该被允许
        request = PermissionRequest(
            tool_name="bash_execute",
            action="Execute dangerous command",
            arguments={"command": "rm -rf /"},
            risk_level=ToolRiskLevel.CRITICAL,
        )

        result = await engine.check_permission(request)
        assert result.allowed is True
        assert "Bypass" in result.reason

    @pytest.mark.asyncio
    async def test_bypass_ignores_deny_rules(self):
        """BYPASS 模式忽略拒绝规则"""
        engine = PermissionEngine(mode=PermissionMode.BYPASS)

        # 添加拒绝规则
        engine.add_rule(PermissionRule(
            tool_pattern="*",
            decision=PermissionDecision.DENY,
            reason="Deny everything",
            priority=1000,
        ))

        request = PermissionRequest(
            tool_name="file_write",
            action="Write file",
            arguments={"path": "/etc/passwd"},
            risk_level=ToolRiskLevel.HIGH,
        )

        result = await engine.check_permission(request)
        assert result.allowed is True


class TestStrictModeBlocks:
    """strict 模式 + AutoDenyHandler → 全部拒绝"""

    @pytest.mark.asyncio
    async def test_strict_mode_blocks(self):
        """STRICT 模式 + AutoDenyHandler 应拒绝所有请求"""
        engine = PermissionEngine(
            mode=PermissionMode.STRICT,
            handler=AutoDenyHandler(),
        )

        # 即使是低风险只读工具也应被拒绝
        request = PermissionRequest(
            tool_name="unknown_tool",
            action="Read data",
            arguments={},
            risk_level=ToolRiskLevel.LOW,
        )

        result = await engine.check_permission(request)
        assert result.allowed is False
        assert result.decision == PermissionDecision.DENY

    @pytest.mark.asyncio
    async def test_strict_with_allow_rule_passes(self):
        """STRICT 模式有明确 ALLOW 规则时通过"""
        engine = PermissionEngine(
            mode=PermissionMode.STRICT,
            handler=AutoDenyHandler(),
        )

        # 添加一条允许规则
        engine.add_rule(PermissionRule(
            tool_pattern="calculator",
            decision=PermissionDecision.ALLOW,
            reason="Calculator is safe",
            priority=100,
        ))

        request = PermissionRequest(
            tool_name="calculator",
            action="Calculate",
            arguments={"expression": "1+1"},
            risk_level=ToolRiskLevel.LOW,
        )

        result = await engine.check_permission(request)
        assert result.allowed is True


class TestRulePriority:
    """高优先级规则覆盖低优先级"""

    @pytest.mark.asyncio
    async def test_rule_priority(self):
        """高优先级的 ALLOW 应覆盖低优先级的 DENY"""
        engine = PermissionEngine(
            mode=PermissionMode.DEFAULT,
            handler=AutoDenyHandler(),
        )

        # 低优先级: 拒绝所有 file_*
        engine.add_rule(PermissionRule(
            tool_pattern="file_*",
            decision=PermissionDecision.DENY,
            reason="Deny file ops by default",
            priority=10,
        ))

        # 高优先级: 允许 file_read
        engine.add_rule(PermissionRule(
            tool_pattern="file_read",
            decision=PermissionDecision.ALLOW,
            reason="Allow reading files",
            priority=100,
        ))

        # file_read 应被允许（高优先级规则）
        request_read = PermissionRequest(
            tool_name="file_read",
            action="Read file",
            arguments={"path": "test.txt"},
            risk_level=ToolRiskLevel.LOW,
        )
        result_read = await engine.check_permission(request_read)
        assert result_read.allowed is True

        # file_write 应被拒绝（低优先级拒绝规则生效）
        request_write = PermissionRequest(
            tool_name="file_write",
            action="Write file",
            arguments={"path": "test.txt", "content": "hi"},
            risk_level=ToolRiskLevel.MEDIUM,
        )
        result_write = await engine.check_permission(request_write)
        assert result_write.allowed is False

    @pytest.mark.asyncio
    async def test_wildcard_vs_specific(self):
        """具体模式优先于通配符（通过优先级实现）"""
        engine = PermissionEngine(
            mode=PermissionMode.DEFAULT,
            handler=AutoApproveHandler(),
        )

        # 通配符允许所有
        engine.add_rule(PermissionRule(
            tool_pattern="*",
            decision=PermissionDecision.ALLOW,
            reason="Allow all",
            priority=1,
        ))

        # 具体拒绝 bash
        engine.add_rule(PermissionRule(
            tool_pattern="bash_execute",
            decision=PermissionDecision.DENY,
            reason="No bash",
            priority=50,
        ))

        # bash 应被拒绝
        request = PermissionRequest(
            tool_name="bash_execute",
            action="Execute",
            arguments={"command": "ls"},
            risk_level=ToolRiskLevel.HIGH,
        )
        result = await engine.check_permission(request)
        assert result.allowed is False


class TestSessionGrantPersists:
    """一次授权后同会话不再询问"""

    @pytest.mark.asyncio
    async def test_session_grant_persists(self):
        """会话授权后同一工具不再需要确认"""
        # 使用回调处理器来追踪询问次数
        ask_count = {"value": 0}

        def approve_callback(request: PermissionRequest) -> bool:
            ask_count["value"] += 1
            return True  # 总是批准

        handler = CallbackPermissionHandler(approve_callback)
        engine = PermissionEngine(
            mode=PermissionMode.STRICT,
            handler=handler,
        )

        session_id = "test-session-123"

        request = PermissionRequest(
            tool_name="http_request",
            action="Make HTTP request",
            arguments={"url": "https://example.com"},
            risk_level=ToolRiskLevel.HIGH,
            session_id=session_id,
        )

        # 第一次请求 - 应该询问 handler
        result1 = await engine.check_permission(request)
        assert result1.allowed is True
        assert ask_count["value"] == 1

        # 第二次请求 - 应该使用会话级授权，不再询问
        result2 = await engine.check_permission(request)
        assert result2.allowed is True
        assert ask_count["value"] == 1  # 没有增加

    @pytest.mark.asyncio
    async def test_session_grant_tool_specific(self):
        """会话授权仅对特定工具有效"""
        handler = AutoApproveHandler()
        engine = PermissionEngine(
            mode=PermissionMode.STRICT,
            handler=handler,
        )

        session_id = "test-session-456"

        # 授权 calculator
        engine.grant_session_permission(session_id, "calculator")

        # calculator 应被允许
        request_calc = PermissionRequest(
            tool_name="calculator",
            action="Calculate",
            arguments={"expression": "1+1"},
            risk_level=ToolRiskLevel.LOW,
            session_id=session_id,
        )
        result = await engine.check_permission(request_calc)
        assert result.allowed is True

        # 但 bash 不在授权范围内 (会被 handler 处理)
        # 由于使用 AutoApproveHandler, 它会被允许但走的是不同路径
        request_bash = PermissionRequest(
            tool_name="bash_execute",
            action="Execute",
            arguments={"command": "ls"},
            risk_level=ToolRiskLevel.HIGH,
            session_id=session_id,
        )
        # 由于 AutoApproveHandler 会批准，不测试拒绝
        # 主要验证 session_grant 只记录了 calculator
        assert "calculator" in engine._session_grants.get(session_id, set())
        assert "bash_execute" not in engine._session_grants.get(session_id, set())
