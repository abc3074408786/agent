"""LangGraph Agent 运行时状态定义"""

from typing import Annotated, Optional, Sequence, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph Agent 运行时状态

    使用 TypedDict 定义 Agent 在图执行过程中的状态结构。
    messages 字段使用 add_messages 注解实现消息累加器模式，
    确保新消息自动追加到现有消息序列中。
    """

    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    trace_id: str
    current_provider: Optional[str]
    current_model: Optional[str]
    # AGI cognitive state
    agi_advice: Optional[dict]  # pre_action advice from AGI modules
    agi_report: Optional[dict]  # post_action learning report
    iteration: Optional[int]
    max_iterations: Optional[int]
