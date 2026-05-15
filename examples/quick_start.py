"""
快速开始示例 - 展示如何使用 Agent 框架

运行前请设置环境变量:
    export OPENAI_API_KEY=your_api_key
    # 或
    export ANTHROPIC_API_KEY=your_api_key
"""

import os
import asyncio

# 方式 1: 使用便捷函数
def example_quick_start():
    """最简单的使用方式"""
    from agent import (
        create_chat_model,
        create_react_agent,
        register_builtin_tools,
        get_tools,
    )
    
    # 1. 注册内置工具
    register_builtin_tools()
    
    # 2. 创建 LLM (自动从环境变量读取 API Key)
    llm = create_chat_model(
        provider="openai",
        model="gpt-4",
        temperature=0.7,
    )
    
    # 3. 获取工具
    tools = get_tools()
    
    # 4. 创建 Agent
    agent = create_react_agent(
        llm=llm,
        tools=tools,
        system_prompt="你是一个有用的助手，可以进行数学计算和文本处理。",
    )
    
    # 5. 调用
    result = agent.invoke("请计算 123 * 456，并告诉我现在的时间")
    
    # 打印结果
    for msg in result["messages"]:
        print(f"[{msg.__class__.__name__}]: {msg.content[:200] if msg.content else '(tool call)'}")


# 方式 2: 使用配置文件和 init
def example_with_config():
    """使用配置文件初始化"""
    import agent
    
    # 初始化框架 (会加载配置文件并注册工具)
    agent.init(
        config_path="config.yaml",
        register_tools=True,
    )
    
    # 创建 Agent
    my_agent = agent.create_agent(
        llm_name="default",  # 使用配置文件中的默认 LLM
    )
    
    # 调用
    result = my_agent.invoke("你好！")
    print(result["messages"][-1].content)


# 方式 3: 自定义工具
def example_custom_tool():
    """创建和使用自定义工具"""
    from pydantic import BaseModel, Field
    from agent import (
        create_tool,
        create_chat_model,
        create_react_agent,
        tool_registry,
    )
    
    # 定义工具输入模型
    class WeatherInput(BaseModel):
        city: str = Field(description="城市名称")
    
    # 创建自定义工具
    def get_weather(city: str) -> str:
        """获取城市天气 (模拟)"""
        # 实际应用中这里会调用天气 API
        return f"{city}的天气: 晴朗，温度 25°C，湿度 60%"
    
    weather_tool = create_tool(
        name="get_weather",
        description="获取指定城市的天气信息",
        func=get_weather,
        args_schema=WeatherInput,
    )
    
    # 注册到工具注册器
    tool_registry.register(weather_tool, category="weather", tags=["weather", "api"])
    
    # 创建 Agent
    llm = create_chat_model("openai", "gpt-4")
    agent = create_react_agent(llm, [weather_tool])
    
    # 调用
    result = agent.invoke("北京今天天气怎么样？")
    print(result["messages"][-1].content)


# 方式 4: 流式输出
async def example_streaming():
    """流式输出示例"""
    from agent import create_chat_model, create_react_agent, register_builtin_tools, get_tools
    
    register_builtin_tools()
    llm = create_chat_model("openai", "gpt-4", streaming=True)
    tools = get_tools()
    agent = create_react_agent(llm, tools)
    
    print("开始流式输出:")
    async for state in agent.astream("请介绍一下自己"):
        # 每次状态更新
        for node_name, node_state in state.items():
            if "messages" in node_state:
                last_msg = node_state["messages"][-1]
                if last_msg.content:
                    print(f"[{node_name}] {last_msg.content[:100]}...")


# 方式 5: 会话管理
def example_with_session():
    """带会话管理的示例"""
    from agent import (
        create_chat_model,
        create_react_agent,
        register_builtin_tools,
        get_tools,
        SessionManager,
        InMemoryBackend,
    )
    from langchain_core.messages import HumanMessage, AIMessage
    
    # 创建会话管理器
    session_manager = SessionManager(InMemoryBackend())
    
    # 创建新会话
    session_id = session_manager.create_session(title="测试会话")
    print(f"创建会话: {session_id}")
    
    # 创建 Agent
    register_builtin_tools()
    llm = create_chat_model("openai", "gpt-4")
    tools = get_tools()
    agent = create_react_agent(llm, tools)
    
    # 第一轮对话
    result1 = agent.invoke("我叫小明，请记住我的名字")
    session_manager.add_message(session_id, HumanMessage(content="我叫小明，请记住我的名字"))
    session_manager.add_message(session_id, result1["messages"][-1])
    print(f"回复1: {result1['messages'][-1].content}")
    
    # 第二轮对话 (带历史)
    history = session_manager.get_messages(session_id)
    # 注意: 实际使用中应该使用 checkpointer 来自动管理历史
    print(f"会话历史消息数: {len(history)}")


# 方式 6: 使用 LangGraph Checkpointer 持久化
def example_with_checkpointer():
    """使用检查点保存器实现对话持久化"""
    from langgraph.checkpoint.memory import MemorySaver
    from agent import create_chat_model, ReActGraphBuilder, AgentExecutor, register_builtin_tools, get_tools
    
    register_builtin_tools()
    
    # 创建带检查点的 Agent
    llm = create_chat_model("openai", "gpt-4")
    tools = get_tools()
    checkpointer = MemorySaver()
    
    builder = ReActGraphBuilder(
        llm=llm,
        tools=tools,
        checkpointer=checkpointer,
    )
    
    graph = builder.build()
    agent = AgentExecutor(graph)
    
    # 使用 thread_id 进行多轮对话
    config = {"configurable": {"thread_id": "user-123"}}
    
    # 第一轮
    result1 = agent.invoke("我叫小明", config=config)
    print(f"回复1: {result1['messages'][-1].content}")
    
    # 第二轮 (自动带上历史)
    result2 = agent.invoke("我叫什么名字？", config=config)
    print(f"回复2: {result2['messages'][-1].content}")


if __name__ == "__main__":
    # 检查 API Key
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("ANTHROPIC_API_KEY"):
        print("请设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 环境变量")
        print("示例: export OPENAI_API_KEY=sk-xxx")
        exit(1)
    
    print("=" * 50)
    print("Agent 框架快速开始示例")
    print("=" * 50)
    
    # 运行示例
    print("\n--- 示例 1: 快速开始 ---")
    example_quick_start()
