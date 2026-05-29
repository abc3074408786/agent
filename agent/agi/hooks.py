"""
AGI Hooks for LangGraph Integration.

Unified interface: AGI Hooks (LangGraph adapter) + BrainOS (cognitive engine).

Architecture:
    LangGraph ReAct Loop
        ↓ calls
    AGIHooks (this file) — interface layer
        ↓ delegates to
    BrainOS (agent/brain/) — 8 cognitive modules do the actual computation
    AGICore (agent/agi/) — goal engine, world model, transfer, evaluator

Usage:
    from agent.agi.hooks import AGIHooks
    
    hooks = AGIHooks(project_dir="/path/to/project")
    
    # In LangGraph graph builder:
    workflow.add_node("tools", hooks.wrap_tool_node(tool_node))
"""

from __future__ import annotations
import time
from typing import Any, Dict, Sequence, Optional

from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from agent.agi.core import AGICore
from agent.brain.core import BrainOS
from agent.agi.self_evaluator.auto_verifier import AutoVerifier
from agent.agi.metacognition import MetacognitionEngine
from agent.graph.state import AgentState


class AGIHooks:
    """
    Unified LangGraph integration: BrainOS (cognition) + AGICore (learning).
    
    Pipeline for every action:
    1. BrainOS.process() → filter, risk check, memory recall, predict, habits
    2. AGICore.pre_action() → world model predictions, transfer advice
    3. Merge into LLM context
    4. [Tool executes]
    5. BrainOS.feedback() → update all 8 brain modules
    6. AGICore.post_action() → update world model, self-evaluate, consolidate
    """

    def __init__(self, project_dir: str = ".", enabled: bool = True):
        self.enabled = enabled
        self.agi = AGICore(project_dir=project_dir)
        self.brain = BrainOS(project_id="main", data_dir=f"{project_dir}/.brain")
        self.verifier = AutoVerifier(workspace=project_dir)
        self.metacognition = MetacognitionEngine()
        self._pending_tool_calls: dict[str, dict] = {}
        self._actions_taken: list[str] = []
        self._results: list[dict] = []
        self._current_goal: str = ""

    # ─── Agent Node Hook (pre-LLM) ───

    def enhance_messages(self, state: AgentState) -> list[BaseMessage]:
        """
        Full cognitive pipeline before LLM call:
        BrainOS.process() + AGICore.pre_action() → inject into messages.
        """
        if not self.enabled:
            return list(state["messages"])

        messages = list(state["messages"])

        # Get last user message for context
        last_user = None
        for msg in reversed(messages):
            if hasattr(msg, 'content') and not isinstance(msg, (AIMessage, ToolMessage)):
                last_user = msg.content
                break

        if not last_user:
            return messages

        # ══════ Metacognition: self-awareness checks ══════
        meta_check = self.metacognition.pre_check(last_user[:200], context={"iteration": state.get("iteration", 0)})
        
        # If metacognition says don't proceed, add strong signal
        if not meta_check["proceed"]:
            if meta_check.get("questions"):
                context_parts.append("❓ 信息不足，建议先问: " + "; ".join(meta_check["questions"][:2]))
            if meta_check.get("warnings"):
                context_parts.extend(["🚫 " + w for w in meta_check["warnings"]])

        # Critical context (never forget)
        critical = meta_check.get("critical", {})
        if critical:
            context_parts.append("📌 关键约束: " + "; ".join(f"{k}={v}" for k, v in list(critical.items())[:3]))

        # Course correction check
        if self.metacognition.should_rollback():
            context_parts.append("⏪ 连续失败3次，建议回退到上一个正确状态，换一种方法")

        # Completion check (if we have a goal)
        if self._current_goal and self._actions_taken:
            completion = self.metacognition.check_completion(self._current_goal, self._actions_taken, self._results)
            if completion["done"]:
                context_parts.append(f"✅ 目标可能已完成 (信心:{completion['confidence']:.0%})")
            elif completion.get("remaining"):
                context_parts.append(f"📋 未完成: {'; '.join(completion['remaining'])}")

        # Track goal
        if not self._current_goal:
            self._current_goal = last_user[:100]

        # ══════ BrainOS: Full Cognitive Pipeline ══════
        brain_result = self.brain.process(last_user[:300], context={"iteration": state.get("iteration", 0)})

        # If brain blocks it (amygdala risk too high), add strong warning
        if brain_result.get("blocked"):
            messages.append(SystemMessage(content=(
                f"[⚠️ 紧急中断] 杏仁核风险评估: 危险操作被阻止\n"
                f"原因: {'; '.join(brain_result.get('reason', []))}\n"
                f"建议: 请确认用户真的想要执行此操作"
            )))
            return messages

        # ══════ AGICore: World Model + Transfer ══════
        agi_advice = self.agi.pre_action("respond", {"user_input": last_user[:200]})

        # ══════ Merge All Cognitive Signals ══════
        context_parts = []

        # BrainOS signals
        if brain_result.get("memories"):
            context_parts.append(f"🧠 记忆: {'; '.join(brain_result['memories'][:2])}")

        if brain_result.get("prediction", {}).get("confidence", 0) > 0.4:
            pred = brain_result["prediction"]
            context_parts.append(f"🔮 小脑预测: {pred.get('predicted_outcome', '?')} (信心:{pred.get('confidence', 0):.0%})")

        if brain_result.get("habit"):
            habit = brain_result["habit"]
            if habit.get("is_automatic"):
                context_parts.append(f"⚡ 习惯(自动): {habit['routine']} (强度:{habit['strength']:.0%})")
            elif habit.get("strength", 0) > 0.4:
                context_parts.append(f"💡 习惯建议: {habit['routine']}")

        if brain_result.get("risk", {}).get("risk_level", 0) > 0.3:
            risk = brain_result["risk"]
            context_parts.append(f"⚠️ 风险({risk['risk_level']:.0%}): {'; '.join(risk.get('reasons', []))}")

        if brain_result.get("imitations"):
            top_imit = brain_result["imitations"][0]
            context_parts.append(f"👁️ 模仿建议: {top_imit['action']}")

        # AGICore signals
        if agi_advice.get("warnings"):
            context_parts.append("⚠️ " + "; ".join(agi_advice["warnings"]))

        if agi_advice.get("patterns"):
            for p in agi_advice["patterns"][:1]:
                context_parts.append(f"📊 经验模式: {p['rule']} (信心:{p['confidence']:.0%})")

        if agi_advice.get("transfer_advice"):
            context_parts.append(f"🔄 跨域: {agi_advice['transfer_advice'][0]}")

        # Confidence check
        if agi_advice.get("should_ask_human"):
            context_parts.append("❓ 信心不足，建议确认后再执行")

        # Only inject if we have useful context
        if context_parts:
            agi_msg = SystemMessage(content=(
                "[认知模块 - BrainOS + AGI]\n" +
                "\n".join(context_parts) +
                "\n[以上为内部认知信号，请参考但自主判断]"
            ))
            insert_idx = 1 if messages and isinstance(messages[0], SystemMessage) else 0
            messages.insert(insert_idx, agi_msg)

        return messages

    # ─── Tool Node Hook (pre/post execution) ───

    def pre_tool(self, state: AgentState) -> Dict[str, Any]:
        """Called before tools execute. Uses code_graph for impact analysis."""
        if not self.enabled:
            return {}

        messages = state["messages"]
        last_msg = messages[-1] if messages else None
        advice = None

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})

                # Get AGI + BrainOS advice
                advice = self.agi.pre_action(
                    action=tool_name,
                    context=tool_args,
                    domain=self._infer_domain(tool_name),
                )

                # ══════ Code Graph: Impact Analysis before file changes ══════
                if tool_name in ("file_write", "file_edit"):
                    impact = self._analyze_code_impact(tool_args)
                    if impact:
                        advice["code_impact"] = impact
                        # Feed impact into world model
                        if impact.get("affected_files"):
                            self.agi.world_model.observe(
                                f"modify:{impact.get('symbol', 'unknown')}",
                                tool_args,
                                f"affects {len(impact['affected_files'])} files",
                                conditions=[f"file={tool_args.get('path', '')}"],
                            )

                self._pending_tool_calls[tc.get("id", "")] = {
                    "name": tool_name,
                    "args": tool_args,
                    "advice": advice,
                    "start_time": time.time(),
                }

        return {"agi_advice": advice}

    def _analyze_code_impact(self, tool_args: dict) -> Optional[dict]:
        """Use code_graph to analyze what a file modification will affect."""
        try:
            from agent.agent.code_graph import CodeGraphAnalyzer, _get_analyzer

            filepath = tool_args.get("path", "")
            if not filepath or not filepath.endswith(".py"):
                return None

            analyzer = _get_analyzer()
            # If graph is empty, try to analyze the project
            if not analyzer.graph.nodes:
                return None

            # Get the module name from filepath
            module_name = filepath.replace("/", ".").replace("\\", ".").replace(".py", "").split(".")[-1]

            # Find affected code
            impact = analyzer.get_impact(module_name)
            affected_files = impact.get("files", set())
            affected_symbols = impact.get("symbols", set())

            if not affected_files and not affected_symbols:
                return None

            return {
                "symbol": module_name,
                "affected_files": list(affected_files)[:10],
                "affected_symbols": list(affected_symbols)[:10],
                "total_affected": len(affected_files) + len(affected_symbols),
                "risk_note": f"修改 {module_name} 会影响 {len(affected_files)} 个文件、{len(affected_symbols)} 个符号",
            }
        except Exception:
            return None

    def post_tool(self, state: AgentState) -> Dict[str, Any]:
        """
        After tool execution: both BrainOS and AGICore learn.
        BrainOS: updates 8 brain modules (memory, habits, predictions, risk)
        AGICore: updates world model, evaluates, consolidates patterns
        """
        if not self.enabled:
            return {}

        messages = state["messages"]
        report = None

        # Find tool messages (results)
        for msg in reversed(messages):
            if isinstance(msg, ToolMessage):
                tool_call_id = getattr(msg, "tool_call_id", "")
                pending = self._pending_tool_calls.pop(tool_call_id, None)

                if pending:
                    duration = time.time() - pending["start_time"]
                    content = msg.content if hasattr(msg, 'content') else ""

                    # Determine success
                    success = not any(
                        err in content.lower()
                        for err in ["error", "failed", "exception", "traceback", "permission denied"]
                    )
                    reward = 1.0 if success else -0.5
                    domain = self._infer_domain(pending["name"])

                    # ══════ BrainOS: feedback to all 8 modules ══════
                    brain_report = self.brain.feedback(
                        action=pending["name"],
                        result=content[:300],
                        reward=reward,
                    )

                    # ══════ AutoVerifier: self-check after file changes ══════
                    verification = None
                    if pending["name"] in ("file_write", "file_edit") and pending["args"].get("path", "").endswith(".py"):
                        verification = self.verifier.verify(
                            pending["args"].get("path", ""),
                            content[:500],
                        )
                        # Override reward based on verification
                        if verification and not verification["passed"]:
                            reward = -0.3  # downgrade reward
                            success = False

                    # ══════ AGICore: world model + evaluator + learner ══════
                    agi_report = self.agi.post_action(
                        action=pending["name"],
                        context=pending["args"],
                        result=content[:500],
                        success=success,
                        domain=domain,
                    )

                    report = {
                        "brain": brain_report,
                        "agi": agi_report,
                        "verification": verification,
                        "success": success,
                        "duration_ms": int(duration * 1000),
                    }

                    # Track for metacognition
                    self._actions_taken.append(pending["name"])
                    self._results.append({"success": success, "result": content[:100]})
                    self.metacognition.record_result(success)

                    # Save rollback point before risky ops
                    if pending["name"] in ("file_write", "file_edit", "bash_execute"):
                        self.metacognition.save_rollback(
                            f"{pending['name']}: {str(pending['args'])[:50]}",
                            {"tool": pending["name"], "args": pending["args"]}
                        )

                break  # only process the most recent tool result

        return {"agi_report": report}

    # ─── Wrapped Tool Node ───

    def wrap_tool_node(self, tool_node: ToolNode):
        """
        Wrap a ToolNode with AGI pre/post hooks.
        Returns a function that can replace the tool_node in the graph.
        """
        def enhanced_tool_node(state: AgentState) -> Dict[str, Any]:
            # Pre-hook
            self.pre_tool(state)

            # Execute original tool node
            result = tool_node.invoke(state)

            # Post-hook (on the result state)
            if isinstance(result, dict) and "messages" in result:
                merged_state = {**state, **result}
                post_report = self.post_tool(merged_state)
                result.update(post_report)

            return result

        return enhanced_tool_node

    # ─── Decision Override ───

    def should_pause(self, state: AgentState) -> bool:
        """
        Check if cognitive modules recommend pausing for human confirmation.
        Checks both: AGI evaluator confidence + BrainOS amygdala risk.
        """
        if not self.enabled:
            return False

        messages = state["messages"]
        last_msg = messages[-1] if messages else None

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                domain = self._infer_domain(tool_name)

                # Check AGI confidence
                if self.agi.evaluator.should_ask_human(domain):
                    return True

                # Check BrainOS amygdala
                risk = self.brain.amygdala.assess_risk(tool_name, str(tool_args))
                if risk["should_interrupt"]:
                    return True

        return False

    # ─── Autonomous Goal Integration ───

    def inject_autonomous_goal(self, state: AgentState) -> Optional[str]:
        """
        If no user input, check for autonomous goals.
        Returns a goal description to work on, or None.
        """
        goal = self.agi.get_next_goal()
        if goal:
            return f"[自主目标] {goal.description}"
        return None

    # ─── Helpers ───

    def _infer_domain(self, tool_name: str) -> str:
        """Infer domain from tool name."""
        domain_map = {
            "file_read": "development",
            "file_write": "development",
            "file_edit": "development",
            "bash_execute": "devops",
            "git_status": "development",
            "git_diff": "development",
            "git_commit": "development",
            "git_log": "development",
            "git_branch": "development",
            "github_create_pr": "development",
            "github_list_issues": "development",
            "grep_search": "development",
            "glob_search": "development",
            "list_directory": "development",
            "web_search": "research",
            "http_request": "development",
            "calculator": "analysis",
            "json_parse": "development",
            "text_process": "content",
        }
        return domain_map.get(tool_name, "general")

    def get_stats(self) -> dict:
        """Get unified stats from both BrainOS and AGICore."""
        return {
            "brain": self.brain.stats(),
            "agi": self.agi.stats(),
            "enabled": self.enabled,
            "pending_tools": len(self._pending_tool_calls),
        }

    def daydream(self) -> dict:
        """Idle-time processing: call during downtime for creativity + consolidation."""
        return self.brain.daydream()
