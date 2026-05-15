"""测试 permissions 模块"""
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
    create_permission_engine,
)


class TestPermissionRule:
    def test_exact_match(self):
        rule = PermissionRule(tool_pattern="calculator", decision=PermissionDecision.ALLOW)
        assert rule.matches("calculator")
        assert not rule.matches("http_request")

    def test_wildcard_match(self):
        rule = PermissionRule(tool_pattern="file_*", decision=PermissionDecision.ASK)
        assert rule.matches("file_read")
        assert rule.matches("file_write")
        assert not rule.matches("calculator")

    def test_condition_match(self):
        rule = PermissionRule(
            tool_pattern="*",
            decision=PermissionDecision.ALLOW,
            conditions={"env": "dev"},
        )
        assert rule.matches("anything", context={"env": "dev"})
        assert not rule.matches("anything", context={"env": "prod"})

    def test_expired_rule(self):
        from datetime import datetime, timezone, timedelta
        rule = PermissionRule(
            tool_pattern="*",
            decision=PermissionDecision.ALLOW,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert not rule.matches("anything")


class TestPermissionResult:
    def test_allow(self):
        r = PermissionResult.allow("test reason")
        assert r.allowed is True
        assert r.decision == PermissionDecision.ALLOW

    def test_deny(self):
        r = PermissionResult.deny("denied")
        assert r.allowed is False
        assert r.decision == PermissionDecision.DENY


class TestPermissionEngine:
    @pytest.mark.asyncio
    async def test_bypass_mode(self):
        engine = PermissionEngine(mode=PermissionMode.BYPASS)
        request = PermissionRequest(
            tool_name="dangerous_tool",
            action="delete everything",
            arguments={},
            risk_level=ToolRiskLevel.CRITICAL,
        )
        result = await engine.check_permission(request)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_auto_mode(self):
        engine = PermissionEngine(mode=PermissionMode.AUTO)
        request = PermissionRequest(
            tool_name="anything",
            action="do stuff",
            arguments={},
        )
        result = await engine.check_permission(request)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_rule_matching(self):
        engine = PermissionEngine(mode=PermissionMode.DEFAULT)
        engine.add_rule(PermissionRule(
            tool_pattern="calculator",
            decision=PermissionDecision.ALLOW,
            priority=100,
        ))
        engine.add_rule(PermissionRule(
            tool_pattern="http_*",
            decision=PermissionDecision.DENY,
            priority=50,
        ))

        # calculator → allow
        r1 = await engine.check_permission(PermissionRequest(
            tool_name="calculator", action="calc", arguments={}
        ))
        assert r1.allowed is True

        # http_request → deny
        r2 = await engine.check_permission(PermissionRequest(
            tool_name="http_request", action="fetch", arguments={}
        ))
        assert r2.allowed is False

    @pytest.mark.asyncio
    async def test_session_grant(self):
        engine = PermissionEngine(mode=PermissionMode.STRICT, handler=AutoDenyHandler())
        engine.grant_session_permission("session-1", "special_tool")

        request = PermissionRequest(
            tool_name="special_tool",
            action="test",
            arguments={},
            session_id="session-1",
        )
        result = await engine.check_permission(request)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_denial_tracking(self):
        engine = PermissionEngine(mode=PermissionMode.DEFAULT, handler=AutoDenyHandler())
        engine.add_rule(PermissionRule(
            tool_pattern="blocked",
            decision=PermissionDecision.DENY,
        ))

        await engine.check_permission(PermissionRequest(
            tool_name="blocked", action="x", arguments={}
        ))
        await engine.check_permission(PermissionRequest(
            tool_name="blocked", action="y", arguments={}
        ))
        assert engine.get_denial_count("blocked") == 2


class TestCreatePermissionEngine:
    def test_with_default_rules(self):
        engine = create_permission_engine(use_default_rules=True)
        assert len(engine._rules) > 0

    def test_without_default_rules(self):
        engine = create_permission_engine(use_default_rules=False)
        assert len(engine._rules) == 0
