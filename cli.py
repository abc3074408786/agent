"""
Agent CLI - 终端交互式对话界面

使用标准库实现的简单 REPL，支持多轮对话、命令和工具调用。

入口: python cli.py 或 agent-cli (通过 pyproject.toml scripts)
需要设置环境变量: OPENAI_API_KEY 或 ANTHROPIC_API_KEY
"""

import os
import sys
import signal
import asyncio
from typing import Optional


# ============ 配置 ============

VERSION = "0.2.0"
APP_NAME = "Agent CLI"

# 支持的 LLM 提供商
PROVIDERS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


# ============ 帮助信息 ============

HELP_TEXT = f"""
{APP_NAME} v{VERSION} - AI Agent 终端交互界面

命令:
  /help      显示此帮助信息
  /clear     清除对话历史
  /tools     列出可用工具
  /skills    列出可用技能
  /cost      显示本次会话消耗
  /exit      退出程序

使用方法:
  直接输入问题或指令与 AI 对话。
  支持多轮对话，上下文会自动保持。

环境变量:
  OPENAI_API_KEY      OpenAI API 密钥
  ANTHROPIC_API_KEY   Anthropic API 密钥
  AGENT_MODEL         模型名称 (默认: gpt-4o)
  AGENT_TEMPERATURE   温度参数 (默认: 0.7)
"""


# ============ 会话状态 ============

class Session:
    """对话会话状态"""

    def __init__(self):
        self.history: list = []
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost: float = 0.0
        self.turn_count: int = 0
        self.provider: Optional[str] = None
        self.model: Optional[str] = None

    def clear(self):
        """清除对话历史"""
        self.history.clear()
        self.turn_count = 0

    def add_user_message(self, content: str):
        """添加用户消息"""
        self.history.append({"role": "user", "content": content})
        self.turn_count += 1

    def add_assistant_message(self, content: str):
        """添加助手消息"""
        self.history.append({"role": "assistant", "content": content})

    def update_cost(self, input_tokens: int = 0, output_tokens: int = 0):
        """更新token消耗"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        # 简单估算费用 (基于 GPT-4o 价格)
        self.total_cost += (input_tokens * 0.0025 + output_tokens * 0.01) / 1000


# ============ 工具和技能列表 ============

def get_available_tools() -> list:
    """获取可用工具列表"""
    try:
        from agent.tools import tool_registry, register_builtin_tools
        from agent.tools.file_tools import register_file_tools
        from agent.tools.bash_tool import register_bash_tools

        # 确保工具已注册
        if not tool_registry.list_tools():
            register_builtin_tools(tool_registry)
            register_file_tools(tool_registry)
            register_bash_tools(tool_registry)

        tools = []
        for name in tool_registry.list_tools():
            metadata = tool_registry.get_metadata(name)
            desc = metadata.description if metadata else ""
            tools.append((name, desc))
        return tools
    except ImportError:
        return [("(工具模块未安装)", "请运行 pip install -e .")]


def get_available_skills() -> list:
    """获取可用技能列表"""
    try:
        from agent.skills import skill_registry, register_builtin_skills

        if not skill_registry.list_skills():
            register_builtin_skills()

        skills = []
        for name in skill_registry.list_skills():
            skill = skill_registry.get(name)
            desc = skill.description if skill else ""
            skills.append((name, desc))
        return skills
    except ImportError:
        return [("(技能模块未安装)", "请运行 pip install -e .")]


# ============ LLM 调用 ============

def detect_provider() -> tuple[Optional[str], Optional[str]]:
    """检测可用的 LLM 提供商"""
    model = os.environ.get("AGENT_MODEL")

    # 优先使用指定的模型
    if model:
        if "claude" in model.lower():
            if os.environ.get("ANTHROPIC_API_KEY"):
                return "anthropic", model
        else:
            if os.environ.get("OPENAI_API_KEY"):
                return "openai", model

    # 自动检测
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", model or "gpt-4o"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", model or "claude-3-5-sonnet-20241022"

    return None, None


async def call_llm(session: Session, user_input: str) -> str:
    """调用 LLM 获取回复"""
    provider, model = detect_provider()

    if not provider:
        return "错误: 未设置 API 密钥。请设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY 环境变量。"

    session.provider = provider
    session.model = model
    session.add_user_message(user_input)

    try:
        if provider == "openai":
            return await _call_openai(session, model)
        elif provider == "anthropic":
            return await _call_anthropic(session, model)
        else:
            return f"错误: 不支持的提供商 '{provider}'"
    except ImportError as e:
        return f"错误: 缺少依赖包。请运行: pip install langchain-{provider}\n详情: {e}"
    except Exception as e:
        return f"错误: LLM 调用失败 - {type(e).__name__}: {str(e)}"


async def _call_openai(session: Session, model: str) -> str:
    """调用 OpenAI"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

    temperature = float(os.environ.get("AGENT_TEMPERATURE", "0.7"))
    llm = ChatOpenAI(model=model, temperature=temperature)

    # 构建消息列表
    messages = [SystemMessage(content="You are a helpful AI assistant.")]
    for msg in session.history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    response = await llm.ainvoke(messages)

    # 更新消耗
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        session.update_cost(
            input_tokens=response.usage_metadata.get("input_tokens", 0),
            output_tokens=response.usage_metadata.get("output_tokens", 0),
        )

    content = response.content
    session.add_assistant_message(content)
    return content


async def _call_anthropic(session: Session, model: str) -> str:
    """调用 Anthropic"""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

    temperature = float(os.environ.get("AGENT_TEMPERATURE", "0.7"))
    llm = ChatAnthropic(model=model, temperature=temperature)

    # 构建消息列表
    messages = [SystemMessage(content="You are a helpful AI assistant.")]
    for msg in session.history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    response = await llm.ainvoke(messages)

    # 更新消耗
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        session.update_cost(
            input_tokens=response.usage_metadata.get("input_tokens", 0),
            output_tokens=response.usage_metadata.get("output_tokens", 0),
        )

    content = response.content
    session.add_assistant_message(content)
    return content


# ============ 命令处理 ============

def handle_command(command: str, session: Session) -> Optional[str]:
    """
    处理斜杠命令

    Returns:
        命令输出字符串，或 None 表示退出
    """
    cmd = command.strip().lower()

    if cmd == "/help":
        return HELP_TEXT

    elif cmd == "/clear":
        session.clear()
        return "对话历史已清除。"

    elif cmd == "/tools":
        tools = get_available_tools()
        if not tools:
            return "没有可用的工具。"
        lines = ["可用工具:"]
        lines.append("-" * 40)
        for name, desc in tools:
            # 截断描述
            short_desc = desc[:60] + "..." if len(desc) > 60 else desc
            lines.append(f"  {name:<20} {short_desc}")
        return "\n".join(lines)

    elif cmd == "/skills":
        skills = get_available_skills()
        if not skills:
            return "没有可用的技能。"
        lines = ["可用技能:"]
        lines.append("-" * 40)
        for name, desc in skills:
            short_desc = desc[:60] + "..." if len(desc) > 60 else desc
            lines.append(f"  {name:<20} {short_desc}")
        return "\n".join(lines)

    elif cmd == "/cost":
        lines = [
            "会话消耗统计:",
            "-" * 40,
            f"  提供商:      {session.provider or '未连接'}",
            f"  模型:        {session.model or '未设置'}",
            f"  对话轮次:    {session.turn_count}",
            f"  输入 tokens: {session.total_input_tokens:,}",
            f"  输出 tokens: {session.total_output_tokens:,}",
            f"  估算费用:    ${session.total_cost:.4f}",
        ]
        return "\n".join(lines)

    elif cmd in ("/exit", "/quit", "/q"):
        return None  # 信号退出

    else:
        return f"未知命令: '{command}'。输入 /help 查看可用命令。"


# ============ 主循环 ============

async def async_main():
    """异步主循环"""
    session = Session()

    # 显示欢迎信息
    print(f"\n{'=' * 50}")
    print(f"  {APP_NAME} v{VERSION}")
    print(f"{'=' * 50}")

    # 检测提供商
    provider, model = detect_provider()
    if provider:
        print(f"  提供商: {provider} | 模型: {model}")
    else:
        print("  警告: 未检测到 API 密钥")
        print("  请设置 OPENAI_API_KEY 或 ANTHROPIC_API_KEY")

    print(f"\n  输入 /help 查看帮助，/exit 退出")
    print(f"{'=' * 50}\n")

    while True:
        try:
            # 读取用户输入
            user_input = input("你> ").strip()

            if not user_input:
                continue

            # 处理命令
            if user_input.startswith("/"):
                result = handle_command(user_input, session)
                if result is None:
                    print("\n再见！")
                    break
                print(f"\n{result}\n")
                continue

            # 调用 LLM
            print("\n思考中...", end="", flush=True)
            response = await call_llm(session, user_input)
            # 清除 "思考中..." 提示
            print(f"\r{'  ' * 10}\r", end="")
            print(f"AI> {response}\n")

        except KeyboardInterrupt:
            print("\n\n再见！(Ctrl+C)")
            break
        except EOFError:
            print("\n\n再见！")
            break


def main():
    """CLI 入口点"""
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n\n再见！")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n再见！")
        sys.exit(0)


if __name__ == "__main__":
    main()
