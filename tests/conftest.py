"""测试基础设施"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage


@pytest.fixture
def sample_messages():
    """标准测试消息列表"""
    return [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="Hello, what is 2+2?"),
        AIMessage(content="2+2 equals 4."),
        HumanMessage(content="And what about 3*3?"),
        AIMessage(content="3*3 equals 9."),
    ]


@pytest.fixture
def long_messages():
    """包含工具调用的长消息列表"""
    messages = [SystemMessage(content="You are a helpful assistant.")]
    for i in range(20):
        messages.append(HumanMessage(content=f"Question {i}: " + "x" * 200))
        if i % 3 == 0:
            messages.append(AIMessage(
                content="",
                tool_calls=[{"name": "calculator", "args": {"expr": f"{i}*2"}, "id": f"call_{i}"}]
            ))
            messages.append(ToolMessage(content=f"Result: {i*2}", tool_call_id=f"call_{i}"))
            messages.append(AIMessage(content=f"The answer is {i*2}."))
        else:
            messages.append(AIMessage(content=f"Answer {i}: " + "y" * 200))
    return messages


@pytest.fixture
def mock_tool():
    """模拟工具"""
    tool = MagicMock()
    tool.name = "test_tool"
    tool.description = "A test tool"
    tool.invoke = MagicMock(return_value="tool result")
    tool.ainvoke = AsyncMock(return_value="async tool result")
    return tool


@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
