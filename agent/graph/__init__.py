"""
Graph Module - LangGraph ReAct 图构建

提供:
- ReAct Agent 图节点
- 条件边和流程控制
- 图构建器
- 运行时执行
"""

from typing import Any, Dict, List, Optional, Sequence, Union, Literal, Callable, Annotated
import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver

from agent.graph.state import AgentState
from agent.observability import get_logger, get_tracer

logger = get_logger("graph")
tracer = get_tracer("graph")


# ============ 默认提示模板 ============

DEFAULT_SYSTEM_PROMPT = """你是一个智能助手，可以使用各种工具来帮助用户完成任务。

你应该:
1. 仔细理解用户的需求
2. 选择合适的工具来完成任务
3. 如果需要多步操作，逐步执行
4. 清晰地解释你的思考过程和结果

可用工具会在对话中提供。请根据需要使用它们。"""


# ============ 图节点函数 ============

def create_agent_node(
    llm: BaseChatModel,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Callable:
    """
    创建 Agent 节点函数
    
    Agent 节点负责:
    - 接收用户输入和历史消息
    - 调用 LLM 生成响应
    - 决定是否需要调用工具
    """
    
    @tracer.trace("agent_node")
    def agent_node(state: AgentState) -> Dict[str, Any]:
        """Agent 节点 - 调用 LLM 并生成响应"""
        messages = state["messages"]
        
        # 构建提示
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + list(messages)
        
        logger.debug(
            f"Agent node processing",
            message_count=len(messages),
            iteration=state.get("iteration", 0),
        )
        
        # 调用 LLM
        response = llm.invoke(messages)
        
        logger.debug(
            f"Agent response generated",
            has_tool_calls=bool(response.tool_calls) if hasattr(response, 'tool_calls') else False,
        )
        
        return {
            "messages": [response],
            "iteration": state.get("iteration", 0) + 1,
        }
    
    return agent_node


def create_tool_node(tools: Sequence[BaseTool]) -> ToolNode:
    """
    创建工具节点
    
    使用 LangGraph 内置的 ToolNode
    """
    return ToolNode(tools)


# ============ 条件边函数 ============

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    判断是否继续执行
    
    检查最后一条消息是否包含工具调用
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    # 检查迭代次数限制
    max_iterations = state.get("max_iterations", 10)
    current_iteration = state.get("iteration", 0)
    
    if current_iteration >= max_iterations:
        logger.warning(
            f"Max iterations reached",
            max_iterations=max_iterations,
            current_iteration=current_iteration,
        )
        return "end"
    
    # 检查是否有工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.debug(
            f"Tool calls detected",
            tool_count=len(last_message.tool_calls),
            tools=[tc["name"] for tc in last_message.tool_calls],
        )
        return "tools"
    
    return "end"


# ============ 图构建器 ============

class ReActGraphBuilder:
    """
    ReAct Agent 图构建器
    
    简化 LangGraph ReAct 模式的构建过程
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: Optional[Sequence[BaseTool]] = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        max_iterations: int = 10,
    ):
        """
        初始化图构建器
        
        Args:
            llm: 语言模型
            tools: 工具列表
            system_prompt: 系统提示
            checkpointer: 检查点保存器 (用于持久化)
            max_iterations: 最大迭代次数
        """
        self.llm = llm
        self.tools = list(tools) if tools else []
        self.system_prompt = system_prompt
        self.checkpointer = checkpointer
        self.max_iterations = max_iterations
        
        # 如果有工具，绑定到 LLM
        if self.tools:
            self.llm_with_tools = llm.bind_tools(self.tools)
        else:
            self.llm_with_tools = llm
    
    def add_tool(self, tool: BaseTool) -> "ReActGraphBuilder":
        """添加工具"""
        self.tools.append(tool)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        return self
    
    def add_tools(self, tools: Sequence[BaseTool]) -> "ReActGraphBuilder":
        """批量添加工具"""
        self.tools.extend(tools)
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        return self
    
    def set_system_prompt(self, prompt: str) -> "ReActGraphBuilder":
        """设置系统提示"""
        self.system_prompt = prompt
        return self
    
    def set_checkpointer(self, checkpointer: BaseCheckpointSaver) -> "ReActGraphBuilder":
        """设置检查点保存器"""
        self.checkpointer = checkpointer
        return self
    
    @tracer.trace("build_graph")
    def build(self) -> StateGraph:
        """
        构建并返回 StateGraph
        
        Returns:
            编译后的 StateGraph
        """
        logger.info(
            f"Building ReAct graph",
            tool_count=len(self.tools),
            has_checkpointer=self.checkpointer is not None,
        )
        
        # 创建图
        workflow = StateGraph(AgentState)
        
        # 创建节点
        agent_node = create_agent_node(
            self.llm_with_tools,
            self.system_prompt,
        )
        
        # 添加节点
        workflow.add_node("agent", agent_node)
        
        if self.tools:
            tool_node = create_tool_node(self.tools)
            workflow.add_node("tools", tool_node)
            
            # 添加边
            workflow.add_conditional_edges(
                "agent",
                should_continue,
                {
                    "tools": "tools",
                    "end": END,
                }
            )
            workflow.add_edge("tools", "agent")
        else:
            # 无工具时直接结束
            workflow.add_edge("agent", END)
        
        # 设置入口
        workflow.set_entry_point("agent")
        
        # 编译图
        compile_kwargs = {}
        if self.checkpointer:
            compile_kwargs["checkpointer"] = self.checkpointer
        
        graph = workflow.compile(**compile_kwargs)
        
        logger.info("ReAct graph built successfully")
        return graph


class AgentExecutor:
    """
    Agent 执行器
    
    封装图的运行逻辑，提供便捷的调用接口
    """
    
    def __init__(
        self,
        graph: StateGraph,
        max_iterations: int = 10,
    ):
        """
        初始化执行器
        
        Args:
            graph: 编译后的 StateGraph
            max_iterations: 最大迭代次数
        """
        self.graph = graph
        self.max_iterations = max_iterations
    
    @tracer.trace("agent.invoke")
    def invoke(
        self,
        input_message: Union[str, HumanMessage],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        同步调用 Agent
        
        Args:
            input_message: 用户输入
            config: 运行配置 (包含 thread_id 等)
            **kwargs: 额外参数
            
        Returns:
            包含消息和状态的字典
        """
        if isinstance(input_message, str):
            input_message = HumanMessage(content=input_message)
        
        initial_state = {
            "messages": [input_message],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            **kwargs,
        }
        
        logger.info(
            f"Invoking agent",
            input_length=len(input_message.content),
            config=config,
        )
        
        result = self.graph.invoke(initial_state, config=config)
        
        logger.info(
            f"Agent invocation complete",
            message_count=len(result.get("messages", [])),
            iterations=result.get("iteration", 0),
        )
        
        return result
    
    @tracer.trace("agent.stream")
    def stream(
        self,
        input_message: Union[str, HumanMessage],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        流式调用 Agent
        
        Args:
            input_message: 用户输入
            config: 运行配置
            **kwargs: 额外参数
            
        Yields:
            流式状态更新
        """
        if isinstance(input_message, str):
            input_message = HumanMessage(content=input_message)
        
        initial_state = {
            "messages": [input_message],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            **kwargs,
        }
        
        logger.info(
            f"Streaming agent",
            input_length=len(input_message.content),
        )
        
        for state in self.graph.stream(initial_state, config=config):
            yield state
    
    async def ainvoke(
        self,
        input_message: Union[str, HumanMessage],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """异步调用 Agent"""
        if isinstance(input_message, str):
            input_message = HumanMessage(content=input_message)
        
        initial_state = {
            "messages": [input_message],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            **kwargs,
        }
        
        return await self.graph.ainvoke(initial_state, config=config)
    
    async def astream(
        self,
        input_message: Union[str, HumanMessage],
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """异步流式调用 Agent"""
        if isinstance(input_message, str):
            input_message = HumanMessage(content=input_message)
        
        initial_state = {
            "messages": [input_message],
            "iteration": 0,
            "max_iterations": self.max_iterations,
            **kwargs,
        }
        
        async for state in self.graph.astream(initial_state, config=config):
            yield state


# ============ 便捷函数 ============

def create_react_agent(
    llm: BaseChatModel,
    tools: Optional[Sequence[BaseTool]] = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    max_iterations: int = 10,
) -> AgentExecutor:
    """
    快速创建 ReAct Agent
    
    Args:
        llm: 语言模型
        tools: 工具列表
        system_prompt: 系统提示
        checkpointer: 检查点保存器
        max_iterations: 最大迭代次数
        
    Returns:
        AgentExecutor 实例
        
    Example:
        >>> from agent.llm import create_chat_model
        >>> from agent.tools import get_tools, register_builtin_tools
        >>> 
        >>> register_builtin_tools()
        >>> llm = create_chat_model("openai", "gpt-4")
        >>> tools = get_tools()
        >>> agent = create_react_agent(llm, tools)
        >>> result = agent.invoke("计算 123 * 456")
    """
    builder = ReActGraphBuilder(
        llm=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
        max_iterations=max_iterations,
    )
    
    graph = builder.build()
    return AgentExecutor(graph, max_iterations=max_iterations)


__all__ = [
    # 状态
    "AgentState",
    # 常量
    "DEFAULT_SYSTEM_PROMPT",
    # 节点函数
    "create_agent_node",
    "create_tool_node",
    # 条件边
    "should_continue",
    # 构建器
    "ReActGraphBuilder",
    # 执行器
    "AgentExecutor",
    # 便捷函数
    "create_react_agent",
]
