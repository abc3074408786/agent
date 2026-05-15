"""
Agent - 基于 LangGraph 的 ReAct 智能代理框架

模块:
- config: 配置管理
- schemas: 数据模型
- observability: 日志和追踪
- llm: 多提供商 LLM 支持
- memory: 会话和消息管理
- tools: 工具注册和内置工具
- graph: ReAct 图构建和执行

快速开始:
    >>> from agent import create_react_agent, create_chat_model, register_builtin_tools, get_tools
    >>> 
    >>> # 注册内置工具
    >>> register_builtin_tools()
    >>> 
    >>> # 创建 LLM
    >>> llm = create_chat_model("openai", "gpt-4")
    >>> 
    >>> # 获取工具
    >>> tools = get_tools()
    >>> 
    >>> # 创建 Agent
    >>> agent = create_react_agent(llm, tools)
    >>> 
    >>> # 调用
    >>> result = agent.invoke("你好，请帮我计算 123 * 456")
    >>> print(result["messages"][-1].content)
"""

__version__ = "0.1.0"
__author__ = "Agent Team"

# ============ 配置 ============
from agent.config import (
    ConfigManager,
    get_config,
)

# ============ 数据模型 ============
from agent.schemas import (
    ChatRequest,
    ChatResponse,
    Message,
    MessageRole,
    Session,
    SSEEvent,
    SSEEventType,
)

# ============ 可观测性 ============
from agent.observability import (
    AgentLogger,
    Tracer,
    Span,
    get_logger,
    get_tracer,
    get_trace_id,
    get_span_id,
    get_session_id,
    set_trace_context,
)

# ============ LLM ============
from agent.llm import (
    LLMProvider,
    LLMConfig,
    LLMFactory,
    LLMManager,
    create_chat_model,
    llm_manager,
)

# ============ 内存/会话 ============
from agent.memory import (
    SessionMetadata,
    BaseMemoryBackend,
    InMemoryBackend,
    RedisBackend,
    AgentChatMessageHistory,
    SessionManager,
    get_session_manager,
    default_session_manager,
)

# ============ 工具 ============
from agent.tools import (
    ToolMetadata,
    ToolRegistry,
    create_tool,
    calculator_tool,
    datetime_tool,
    web_search_tool,
    http_request_tool,
    json_parse_tool,
    text_process_tool,
    register_builtin_tools,
    get_tools,
    tool_registry,
)

# ============ 图/Agent ============
from agent.graph import (
    AgentState,
    DEFAULT_SYSTEM_PROMPT,
    ReActGraphBuilder,
    AgentExecutor,
    create_react_agent,
)


# ============ 便捷初始化函数 ============

def init(
    config_path: str = "config.yaml",
    register_tools: bool = True,
    log_level: str = "INFO",
) -> None:
    """
    初始化 Agent 框架
    
    Args:
        config_path: 配置文件路径
        register_tools: 是否注册内置工具
        log_level: 日志级别
        
    Example:
        >>> import agent
        >>> agent.init("config.yaml")
    """
    import logging
    
    # 设置日志级别
    logging.getLogger("agent").setLevel(getattr(logging, log_level.upper()))
    
    # 加载配置
    config = get_config(config_path)
    
    # 注册 LLM
    if config and "llm" in config._config:
        llm_configs = config.get("llm.providers", [])
        default_provider = config.get("llm.default")
        
        for llm_config in llm_configs:
            name = llm_config.get("name", llm_config.get("provider"))
            is_default = name == default_provider
            llm_manager.register(name, llm_config, set_default=is_default)
    
    # 注册工具
    if register_tools:
        register_builtin_tools()
    
    logger = get_logger("agent")
    logger.info(
        "Agent framework initialized",
        config_path=config_path,
        tools_registered=register_tools,
    )


def create_agent(
    llm_name: Optional[str] = None,
    tools: Optional[list] = None,
    system_prompt: Optional[str] = None,
    **kwargs,
) -> AgentExecutor:
    """
    创建 Agent 的便捷函数
    
    Args:
        llm_name: LLM 名称（从 llm_manager 获取）
        tools: 工具列表，None 则使用已注册的所有工具
        system_prompt: 系统提示
        **kwargs: 传递给 create_react_agent 的其他参数
        
    Returns:
        AgentExecutor 实例
        
    Example:
        >>> import agent
        >>> agent.init()
        >>> my_agent = agent.create_agent()
        >>> result = my_agent.invoke("你好")
    """
    # 获取 LLM
    llm = llm_manager.get(llm_name)
    
    # 获取工具
    if tools is None:
        tools = get_tools()
    
    # 创建 Agent
    agent_kwargs = {
        "llm": llm,
        "tools": tools,
    }
    
    if system_prompt:
        agent_kwargs["system_prompt"] = system_prompt
    
    agent_kwargs.update(kwargs)
    
    return create_react_agent(**agent_kwargs)


__all__ = [
    # 版本
    "__version__",
    "__author__",
    # 配置
    "ConfigManager",
    "get_config",
    # 数据模型
    "ChatRequest",
    "ChatResponse",
    "Message",
    "MessageRole",
    "Session",
    "SSEEvent",
    "SSEEventType",
    # 可观测性
    "AgentLogger",
    "Tracer",
    "Span",
    "get_logger",
    "get_tracer",
    "get_trace_id",
    "get_span_id",
    "get_session_id",
    "set_trace_context",
    # LLM
    "LLMProvider",
    "LLMConfig",
    "LLMFactory",
    "LLMManager",
    "create_chat_model",
    "llm_manager",
    # 内存/会话
    "SessionMetadata",
    "BaseMemoryBackend",
    "InMemoryBackend",
    "RedisBackend",
    "AgentChatMessageHistory",
    "SessionManager",
    "get_session_manager",
    "default_session_manager",
    # 工具
    "ToolMetadata",
    "ToolRegistry",
    "create_tool",
    "calculator_tool",
    "datetime_tool",
    "web_search_tool",
    "http_request_tool",
    "json_parse_tool",
    "text_process_tool",
    "register_builtin_tools",
    "get_tools",
    "tool_registry",
    # 图/Agent
    "AgentState",
    "DEFAULT_SYSTEM_PROMPT",
    "ReActGraphBuilder",
    "AgentExecutor",
    "create_react_agent",
    # 便捷函数
    "init",
    "create_agent",
]
