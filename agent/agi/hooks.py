"""
AGI Hooks for LangGraph Integration.

Wraps the standard ReAct loop with AGI cognitive hooks:
- pre_tool:  Before tool execution → predictions, warnings, advice
- post_tool: After tool execution → learn, update world model, self-evaluate
- pre_agent: Before LLM call → inject AGI context into messages
- should_ask_human: Override to pause when confidence is low

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
from agent.graph.state import AgentState


class AGIHooks:
    """
    LangGraph integration hooks for AGI cognitive modules.
    
    Intercepts the ReAct loop at key points to:
    1. Inject AGI advice into LLM context
    2. Learn from every tool execution
    3. Update world model with observed cause-effects
    4. Track confidence and request human help when needed
    """

    def __init__(self, project_dir: str = ".", enabled: bool = True):
        self.enabled = enabled
        self.agi = AGICore(project_dir=project_dir)
        self._pending_tool_calls: dict[str, dict] = {}  # tool_call_id → context

    # ─── Agent Node Hook (pre-LLM) ───

    def enhance_messages(self, state: AgentState) -> list[BaseMessage]:
        """
        Inject AGI context into messages before LLM call.
        Adds a system message with predictions and advice.
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

        # Get AGI advice
        advice = self.agi.pre_action("respond", {"user_input": last_user[:200]})

        # Build context injection
        agi_context_parts = []

        if advice.get("warnings"):
            agi_context_parts.append("⚠️ 注意: " + "; ".join(advice["warnings"]))

        if advice.get("patterns"):
            top_patterns = advice["patterns"][:2]
            for p in top_patterns:
                agi_context_parts.append(f"💡 经验: {p['rule']} (信心:{p['confidence']:.0%})")

        if advice.get("predictions"):
            top_pred = advice["predictions"][0]
            agi_context_parts.append(f"🔮 预测: {top_pred['effect']} (概率:{top_pred['confidence']:.0%})")

        if advice.get("transfer_advice"):
            agi_context_parts.append(f"🔄 跨域建议: {advice['transfer_advice'][0]}")

        # Only inject if we have something useful
        if agi_context_parts:
            agi_msg = SystemMessage(content=(
                "[AGI 认知模块提示]\n" + "\n".join(agi_context_parts) +
                "\n[以上信息仅供参考，请结合实际情况判断]"
            ))
            # Insert after first system message
            insert_idx = 1 if messages and isinstance(messages[0], SystemMessage) else 0
            messages.insert(insert_idx, agi_msg)

        return messages

    # ─── Tool Node Hook (pre/post execution) ───

    def pre_tool(self, state: AgentState) -> Dict[str, Any]:
        """Called before tools execute. Records pending tool calls."""
        if not self.enabled:
            return {}

        messages = state["messages"]
        last_msg = messages[-1] if messages else None

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})

                # Get AGI advice for this specific tool
                advice = self.agi.pre_action(
                    action=tool_name,
                    context=tool_args,
                    domain=self._infer_domain(tool_name),
                )

                self._pending_tool_calls[tc.get("id", "")] = {
                    "name": tool_name,
                    "args": tool_args,
                    "advice": advice,
                    "start_time": time.time(),
                }

        return {"agi_advice": advice if hasattr(last_msg, "tool_calls") and last_msg.tool_calls else None}

    def post_tool(self, state: AgentState) -> Dict[str, Any]:
        """Called after tools execute. Learns from results."""
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

                    # Post-action learning
                    report = self.agi.post_action(
                        action=pending["name"],
                        context=pending["args"],
                        result=content[:500],
                        success=success,
                        domain=self._infer_domain(pending["name"]),
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
        Check if AGI modules recommend pausing for human confirmation.
        Can be used as a conditional edge in the graph.
        """
        if not self.enabled:
            return False

        messages = state["messages"]
        last_msg = messages[-1] if messages else None

        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            for tc in last_msg.tool_calls:
                tool_name = tc.get("name", "")
                domain = self._infer_domain(tool_name)
                if self.agi.evaluator.should_ask_human(domain):
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
        """Get AGI stats for monitoring."""
        return self.agi.stats()
