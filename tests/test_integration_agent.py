"""
Mock LLM Agent 集成测试

使用 FakeLLM（不调用真实 API）测试 Agent 完整流程:
- Agent 简单问答
- Agent 工具调用
- 多轮对话
- 最大迭代次数限制
"""
import pytest
import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatResult, ChatGeneration

from agent.tools import calculator_tool, calculator
from agent.coordinator import Worker, WorkerTask, TaskStatus


# ============ FakeLLM ============


class FakeLLM(BaseChatModel):
    """
    假 LLM - 不调用真实 API，返回预设响应。
    
    支持:
    - 固定响应模式: 总是返回相同内容
    - 队列模式: 按顺序返回预设响应
    - 工具调用模式: 返回带有 tool_calls 的消息
    """

    responses: List[str] = []
    """按顺序返回的响应列表"""

    tool_call_responses: List[Dict[str, Any]] = []
    """按顺序返回的工具调用列表"""

    _call_count: int = 0
    """调用计数器"""

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return "fake-llm"

    def bind_tools(self, tools: Any, **kwargs) -> "FakeLLM":
        """绑定工具 - FakeLLM 不实际使用工具定义，直接返回 self"""
        return self

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        """生成响应"""
        idx = self._call_count
        self._call_count += 1

        # 如果有工具调用响应
        if idx < len(self.tool_call_responses):
            tc = self.tool_call_responses[idx]
            msg = AIMessage(
                content=tc.get("content", ""),
                tool_calls=tc.get("tool_calls", []),
            )
            return ChatResult(generations=[ChatGeneration(message=msg)])

        # 普通文本响应
        if idx < len(self.responses):
            content = self.responses[idx]
        elif self.responses:
            content = self.responses[-1]  # 重复最后一个
        else:
            content = "I am a fake LLM response."

        msg = AIMessage(content=content)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> ChatResult:
        """异步生成"""
        return self._generate(messages, stop, **kwargs)

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {"type": "fake-llm"}


# ============ 测试用例 ============


class TestAgentSimpleResponse:
    """Agent 收到问题 → 返回答案（无工具调用）"""

    @pytest.mark.asyncio
    async def test_agent_simple_response(self):
        """Agent 无工具时直接返回文本"""
        fake_llm = FakeLLM(responses=["The answer is 42."])

        worker = Worker(
            worker_id="test-worker",
            llm=fake_llm,
            tools=[],
            max_iterations=5,
        )

        task = WorkerTask(
            description="Simple question",
            prompt="What is the meaning of life?",
        )

        result = await worker.execute(task)
        assert result.status == TaskStatus.COMPLETED
        assert "42" in result.output

    @pytest.mark.asyncio
    async def test_agent_response_with_system_prompt(self):
        """Agent 使用自定义系统提示"""
        fake_llm = FakeLLM(responses=["I am a Python expert."])

        worker = Worker(
            worker_id="test-worker",
            llm=fake_llm,
            tools=[],
            system_prompt="You are a Python expert.",
            max_iterations=5,
        )

        task = WorkerTask(
            description="Expert question",
            prompt="Help me with Python.",
        )

        result = await worker.execute(task)
        assert result.status == TaskStatus.COMPLETED
        assert "Python" in result.output


class TestAgentToolCall:
    """Agent 收到数学问题 → 调用 calculator 工具 → 返回结果"""

    @pytest.mark.asyncio
    async def test_agent_tool_call(self):
        """Agent 调用工具后返回结果"""
        fake_llm = FakeLLM(
            tool_call_responses=[
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "name": "calculator",
                            "args": {"expression": "2 + 2"},
                            "id": "call_001",
                        }
                    ],
                },
            ],
            responses=["The answer is 4."],
        )

        worker = Worker(
            worker_id="tool-worker",
            llm=fake_llm,
            tools=[calculator_tool],
            max_iterations=5,
        )

        task = WorkerTask(
            description="Math question",
            prompt="What is 2 + 2?",
        )

        result = await worker.execute(task)
        assert result.status == TaskStatus.COMPLETED
        assert result.output == "The answer is 4."
        assert result.usage.get("iterations", 0) >= 1


class TestAgentMultiTurn:
    """多轮对话保持上下文"""

    @pytest.mark.asyncio
    async def test_agent_multi_turn(self):
        """多轮对话：Worker.send_message 保持上下文"""
        fake_llm = FakeLLM(
            responses=[
                "Hello! How can I help?",
                "Sure, I remember our conversation. You asked about Python.",
            ]
        )

        worker = Worker(
            worker_id="multi-turn-worker",
            llm=fake_llm,
            tools=[],
            max_iterations=5,
        )

        # 第一轮
        task = WorkerTask(
            description="First turn",
            prompt="Hi, tell me about Python.",
        )
        result1 = await worker.execute(task)
        assert result1.status == TaskStatus.COMPLETED
        assert "Hello" in result1.output

        # 第二轮 (继续对话)
        result2 = await worker.send_message("Do you remember what I asked?")
        assert result2.status == TaskStatus.COMPLETED
        assert "remember" in result2.output or "conversation" in result2.output


class TestAgentMaxIterations:
    """验证最大迭代次数限制生效"""

    @pytest.mark.asyncio
    async def test_agent_max_iterations(self):
        """工具调用超过 max_iterations 时应停止"""
        # 每次都返回工具调用，永远不结束
        infinite_tool_calls = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "name": "calculator",
                        "args": {"expression": f"{i} + 1"},
                        "id": f"call_{i:03d}",
                    }
                ],
            }
            for i in range(20)
        ]

        fake_llm = FakeLLM(tool_call_responses=infinite_tool_calls)

        worker = Worker(
            worker_id="limit-worker",
            llm=fake_llm,
            tools=[calculator_tool],
            max_iterations=3,
        )

        task = WorkerTask(
            description="Infinite loop test",
            prompt="Keep calculating forever.",
            max_iterations=3,
        )

        result = await worker.execute(task)
        # 应该在 3 次迭代后停止
        assert result.status == TaskStatus.COMPLETED
        assert result.usage.get("iterations", 0) <= 3
