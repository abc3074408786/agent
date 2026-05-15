# Design Document

## 概述

本设计文档描述 LangGraph Agent 模块的架构设计。该模块作为独立组件与现有 RAG 系统并列部署，使用 LangGraph 实现 ReAct 模式的智能代理，通过 FastAPI 提供 REST API 接口，支持多 LLM 提供商、多轮对话、流式输出和可观测性。

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   FastAPI Application                │
│  ┌──────────────────┐    ┌────────────────────────┐ │
│  │  /api/rag/*      │    │  /api/agent/*          │ │
│  │  (现有 RAG API)   │    │  (Agent API Router)    │ │
│  └──────────────────┘    └────────────┬───────────┘ │
└───────────────────────────────────────┼─────────────┘
                                        │
                          ┌─────────────▼─────────────┐
                          │     LangGraph Engine       │
                          │  ┌─────────────────────┐  │
                          │  │   ReAct State Graph  │  │
                          │  │                     │  │
                          │  │  [Router] ──► [LLM] │  │
                          │  │     │               │  │
                          │  │     ▼               │  │
                          │  │  [RAG Tool]         │  │
                          │  └─────────────────────┘  │
                          └─────────────┬─────────────┘
                                        │
              ┌─────────────────────────┼──────────────────────┐
              │                         │                      │
    ┌─────────▼────────┐   ┌───────────▼──────────┐  ┌───────▼────────┐
    │  LLM Provider    │   │  Session Store        │  │  RAG System    │
    │  (vLLM/OpenAI/   │   │  (Memory)             │  │  (现有系统)     │
    │   Anthropic/...) │   │                       │  │                │
    └──────────────────┘   └───────────────────────┘  └────────────────┘
```

## 组件设计

### 1. 目录结构

```
D:\rag_app\
├── rag/                    # 现有 RAG 模块（不修改）
├── agent/                  # 新增 Agent 模块
│   ├── __init__.py
│   ├── main.py             # FastAPI 路由器定义
│   ├── config.py           # Agent 配置管理
│   ├── schemas.py          # Pydantic 请求/响应模型
│   ├── graph/              # LangGraph 图定义
│   │   ├── __init__.py
│   │   ├── state.py        # Agent 状态定义
│   │   ├── nodes.py        # 图节点（LLM调用、工具调用）
│   │   └── builder.py      # 图构建器
│   ├── tools/              # Agent 工具
│   │   ├── __init__.py
│   │   └── rag_tool.py     # RAG 系统封装工具
│   ├── llm/                # LLM 提供商管理
│   │   ├── __init__.py
│   │   ├── provider.py     # 提供商抽象与工厂
│   │   └── config.py       # 提供商配置模型
│   ├── memory/             # 会话与记忆管理
│   │   ├── __init__.py
│   │   ├── session.py      # 会话存储
│   │   └── compressor.py   # 上下文压缩
│   └── observability/      # 可观测性
│       ├── __init__.py
│       ├── logging.py      # 结构化日志
│       └── tracing.py      # 请求追踪
├── config/
│   └── agent_config.yaml   # Agent 配置文件
├── main.py                 # 应用入口（挂载 RAG + Agent 路由器）
└── requirements.txt        # 依赖（含 Agent 新增依赖）
```


### 2. 数据模型

#### Agent 状态（LangGraph State）

```python
from typing import Annotated, Sequence, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """LangGraph Agent 运行时状态"""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    session_id: str
    trace_id: str
    current_provider: Optional[str]
    current_model: Optional[str]
```

#### 请求/响应模型

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    """Agent 对话请求"""
    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    provider: Optional[str] = Field(None, description="LLM提供商名称")
    model: Optional[str] = Field(None, description="模型名称")
    stream: bool = Field(False, description="是否启用SSE流式输出")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    knowledge_base_id: Optional[str] = Field(None, description="知识库标识符")


class ChatResponse(BaseModel):
    """Agent 对话响应"""
    reply: str = Field(..., description="Agent回复文本")
    session_id: str = Field(..., description="会话ID")
    trace_id: str = Field(..., description="请求追踪ID")
    tool_calls: List[ToolCallInfo] = Field(default_factory=list)
    metadata: ResponseMetadata


class ToolCallInfo(BaseModel):
    """工具调用信息"""
    tool_name: str
    input_params: dict
    output_summary: str
    duration_ms: float


class ResponseMetadata(BaseModel):
    """响应元数据"""
    provider: str
    model: str
    tokens_used: Optional[int] = None
    duration_ms: float
    used_rag: bool = False


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: datetime
    last_active_at: datetime
    message_count: int


class SSEEvent(BaseModel):
    """SSE 流式事件"""
    event: str = Field(..., description="事件类型: token|tool_call|done|error")
    data: str = Field(..., description="事件数据")
```

#### LLM 提供商配置模型

```python
from pydantic import BaseModel, Field
from typing import Optional


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""
    name: str = Field(..., description="提供商名称标识")
    endpoint_url: str = Field(..., description="API端点URL")
    api_key: Optional[str] = Field(None, description="API密钥")
    default_model: str = Field(..., description="默认模型名称")
    max_retries: int = Field(3, description="最大重试次数")
    timeout_seconds: float = Field(30.0, description="请求超时秒数")
```


### 3. 接口设计

#### Agent API 路由

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/agent/chat` | 发送消息并获取 Agent 响应 |
| POST | `/api/agent/chat/stream` | 发送消息并获取 SSE 流式响应 |
| GET | `/api/agent/sessions` | 列出活跃会话 |
| DELETE | `/api/agent/sessions/{session_id}` | 删除指定会话 |
| GET | `/api/agent/health` | 健康检查 |
| GET | `/api/agent/providers` | 列出已配置的 LLM 提供商 |
| POST | `/api/agent/providers` | 添加 LLM 提供商配置 |
| PUT | `/api/agent/providers/{name}` | 修改 LLM 提供商配置 |
| DELETE | `/api/agent/providers/{name}` | 删除 LLM 提供商配置 |

#### FastAPI 路由器挂载

```python
# main.py（应用入口）
from fastapi import FastAPI
from agent.main import router as agent_router
# 假设现有 RAG 路由器
# from rag.main import router as rag_router

app = FastAPI(title="RAG & Agent Service")
# app.include_router(rag_router, prefix="/api/rag")
app.include_router(agent_router, prefix="/api/agent")
```

#### SSE 流式输出格式

```
event: token
data: {"content": "你", "trace_id": "abc-123"}

event: token
data: {"content": "好", "trace_id": "abc-123"}

event: tool_call
data: {"tool": "rag_search", "status": "started", "trace_id": "abc-123"}

event: tool_call
data: {"tool": "rag_search", "status": "completed", "result_summary": "找到3条相关文档", "trace_id": "abc-123"}

event: token
data: {"content": "根据", "trace_id": "abc-123"}

event: done
data: {"session_id": "sess-456", "trace_id": "abc-123", "metadata": {...}}

event: error
data: {"message": "工具调用超时", "trace_id": "abc-123"}
```


### 4. LangGraph 图设计

#### ReAct 模式状态图

```
                    ┌──────────────┐
                    │   START      │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  load_state  │  加载会话历史
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   agent      │  LLM 决策节点
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌─────┤  should_use  ├─────┐
              │     │   tools?     │     │
              │     └──────────────┘     │
              │ yes                  no  │
       ┌──────▼───────┐          ┌──────▼───────┐
       │  tool_node   │          │  respond     │
       │  (RAG调用)    │          │  (直接回答)   │
       └──────┬───────┘          └──────┬───────┘
              │                         │
              └────────────┬────────────┘
                           │
                    ┌──────▼───────┐
                    │  save_state  │  保存会话状态
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │     END      │
                    └──────────────┘
```

#### 图构建实现

```python
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage


def should_use_tools(state: AgentState) -> str:
    """条件边：判断是否需要调用工具"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "respond"


def build_agent_graph(tools, llm):
    """构建 Agent 状态图"""
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("load_state", load_session_state)
    graph.add_node("agent", create_agent_node(llm, tools))
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("respond", format_response)
    graph.add_node("save_state", save_session_state)

    # 添加边
    graph.set_entry_point("load_state")
    graph.add_edge("load_state", "agent")
    graph.add_conditional_edges("agent", should_use_tools, {
        "tools": "tools",
        "respond": "respond"
    })
    graph.add_edge("tools", "agent")  # 工具结果返回给 agent 再次决策
    graph.add_edge("respond", "save_state")
    graph.add_edge("save_state", END)

    return graph.compile()
```


### 5. LLM 提供商管理

#### 统一接口设计

所有 LLM 提供商通过 `ChatOpenAI`（LangChain）的 OpenAI 兼容模式接入，利用各提供商对 OpenAI API 格式的兼容性：

```python
from langchain_openai import ChatOpenAI


class LLMProviderFactory:
    """LLM 提供商工厂"""

    def __init__(self, config_manager: "ConfigManager"):
        self._config_manager = config_manager

    def get_llm(
        self,
        provider_name: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> ChatOpenAI:
        """获取指定提供商的 LLM 实例"""
        provider_config = self._config_manager.get_provider(provider_name)
        return ChatOpenAI(
            base_url=provider_config.endpoint_url,
            api_key=provider_config.api_key or "not-needed",
            model=model or provider_config.default_model,
            max_retries=provider_config.max_retries,
            timeout=provider_config.timeout_seconds,
            **kwargs
        )
```

#### 支持的提供商配置示例

```yaml
# config/agent_config.yaml
llm_providers:
  - name: vllm-local
    endpoint_url: "http://localhost:8000/v1"
    api_key: "not-needed"
    default_model: "Qwen/Qwen2.5-7B-Instruct"
  - name: openai
    endpoint_url: "https://api.openai.com/v1"
    api_key: "${OPENAI_API_KEY}"
    default_model: "gpt-4o"
  - name: anthropic
    endpoint_url: "https://api.anthropic.com/v1"
    api_key: "${ANTHROPIC_API_KEY}"
    default_model: "claude-sonnet-4-20250514"
  - name: google
    endpoint_url: "https://generativelanguage.googleapis.com/v1beta/openai"
    api_key: "${GOOGLE_API_KEY}"
    default_model: "gemini-2.0-flash"
  - name: minimax
    endpoint_url: "https://api.minimax.chat/v1"
    api_key: "${MINIMAX_API_KEY}"
    default_model: "MiniMax-Text-01"
  - name: moonshot
    endpoint_url: "https://api.moonshot.cn/v1"
    api_key: "${MOONSHOT_API_KEY}"
    default_model: "moonshot-v1-8k"
  - name: siliconflow
    endpoint_url: "https://api.siliconflow.cn/v1"
    api_key: "${SILICONFLOW_API_KEY}"
    default_model: "Qwen/Qwen2.5-72B-Instruct"
  - name: openrouter
    endpoint_url: "https://openrouter.ai/api/v1"
    api_key: "${OPENROUTER_API_KEY}"
    default_model: "openai/gpt-4o"
  - name: bytedance-ark
    endpoint_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "${ARK_API_KEY}"
    default_model: "doubao-pro-32k"
  - name: ollama
    endpoint_url: "http://localhost:11434/v1"
    api_key: "ollama"
    default_model: "qwen2.5:7b"

default_provider: vllm-local

agent:
  max_iterations: 5
  tool_timeout_seconds: 30
  system_prompt: |
    你是一个智能助手。你可以使用 RAG 工具来检索知识库中的信息。
    如果用户的问题需要特定领域知识，请使用 rag_search 工具进行检索。
    如果是通用问题或闲聊，直接回答即可。

memory:
  max_messages: 50
  compression_threshold: 40
  compression_strategy: "summarize"  # summarize | truncate

observability:
  log_level: "INFO"
  log_format: "json"
  trace_enabled: true
```


### 6. RAG 工具封装

```python
from langchain_core.tools import tool
from typing import Optional
import httpx


@tool
def rag_search(query: str, knowledge_base_id: Optional[str] = None) -> str:
    """
    搜索知识库获取相关信息。

    Args:
        query: 搜索查询字符串
        knowledge_base_id: 可选的知识库标识符

    Returns:
        检索到的相关文档和生成的答案
    """
    # 调用现有 RAG 系统 API
    ...
```

#### RAG Tool 结构化输出

```python
class RAGToolResult(BaseModel):
    """RAG 工具返回的结构化结果"""
    success: bool
    answer: Optional[str] = None
    documents: List[RetrievedDocument] = []
    error_message: Optional[str] = None


class RetrievedDocument(BaseModel):
    """检索到的文档"""
    content: str
    source: str
    relevance_score: float
```

### 7. 会话与上下文管理

#### 会话存储

```python
from typing import Dict, Optional
from datetime import datetime
import uuid


class SessionStore:
    """会话存储管理器（内存实现，可扩展为持久化）"""

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}

    def create_session(self) -> str:
        """创建新会话，返回会话ID"""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = SessionData(
            session_id=session_id,
            messages=[],
            created_at=datetime.utcnow(),
            last_active_at=datetime.utcnow()
        )
        return session_id

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """获取会话数据"""
        ...

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其历史"""
        ...

    def list_sessions(self) -> List[SessionInfo]:
        """列出所有活跃会话"""
        ...
```

#### 上下文压缩策略

```python
from langchain_core.messages import BaseMessage, SystemMessage
from typing import List


class ContextCompressor:
    """上下文压缩器"""

    def __init__(self, max_messages: int, threshold: int, strategy: str, llm):
        self._max_messages = max_messages
        self._threshold = threshold
        self._strategy = strategy
        self._llm = llm

    def compress_if_needed(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """当消息数超过阈值时执行压缩"""
        if len(messages) <= self._threshold:
            return messages

        if self._strategy == "truncate":
            return self._truncate(messages)
        elif self._strategy == "summarize":
            return self._summarize(messages)
        return messages

    def _truncate(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """截断策略：保留系统消息 + 最近N条消息"""
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        recent = messages[-self._max_messages:]
        return system_msgs + recent

    def _summarize(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """摘要策略：将早期消息压缩为摘要"""
        system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
        recent = messages[-self._max_messages:]
        older = messages[len(system_msgs):-self._max_messages]

        # 使用 LLM 生成摘要
        summary = self._llm.invoke(
            f"请将以下对话历史压缩为简洁摘要：\n{older}"
        )
        summary_msg = SystemMessage(content=f"[对话历史摘要]: {summary.content}")
        return system_msgs + [summary_msg] + recent
```


### 8. 错误处理设计

#### 错误处理层次

| 层级 | 错误类型 | 处理方式 |
|------|----------|----------|
| API 层 | 请求验证失败 | 返回 HTTP 422 + 验证详情 |
| API 层 | 未处理异常 | 记录日志 + 返回 HTTP 500 通用错误 |
| Agent 层 | LLM 提供商不可达 | 返回 HTTP 503 + 描述性消息 |
| Agent 层 | 工具调用超时 | 中止工具 + 使用已有信息继续或返回错误 |
| Tool 层 | RAG 系统不可用 | 返回描述性错误给 Agent，Agent 决定后续行为 |

#### 工具超时处理

```python
import asyncio
from langchain_core.messages import ToolMessage


async def execute_tool_with_timeout(tool, args, timeout_seconds: float):
    """带超时的工具执行"""
    try:
        result = await asyncio.wait_for(
            tool.ainvoke(args),
            timeout=timeout_seconds
        )
        return result
    except asyncio.TimeoutError:
        return ToolMessage(
            content=f"工具 {tool.name} 调用超时（{timeout_seconds}秒），请使用已有信息回答或告知用户。",
            tool_call_id=args.get("tool_call_id", ""),
        )
```

### 9. 可观测性设计

#### 结构化日志

```python
import structlog
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_logger(name: str):
    """获取带追踪ID的结构化日志器"""
    return structlog.get_logger(name).bind(trace_id=trace_id_var.get())


# 日志输出示例
# {"event": "agent_step", "node": "agent", "trace_id": "abc-123", "duration_ms": 150}
# {"event": "tool_call", "tool": "rag_search", "trace_id": "abc-123", "status": "success"}
```

#### 请求追踪中间件

```python
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import uuid


class TraceMiddleware(BaseHTTPMiddleware):
    """请求追踪中间件：为每个请求生成唯一 trace_id"""

    async def dispatch(self, request: Request, call_next):
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        trace_id_var.set(trace_id)
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

#### 健康检查

```python
class HealthStatus(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    components: Dict[str, ComponentHealth]


class ComponentHealth(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    message: Optional[str] = None


# GET /api/agent/health 响应示例
# {
#   "status": "healthy",
#   "components": {
#     "vllm": {"status": "healthy", "latency_ms": 12.5},
#     "rag_system": {"status": "healthy", "latency_ms": 45.2},
#     "session_store": {"status": "healthy"}
#   }
# }
```


## Correctness Properties

*属性（Property）是系统在所有有效执行中都应保持为真的特征或行为——本质上是关于系统应该做什么的形式化陈述。属性作为人类可读规范与机器可验证正确性保证之间的桥梁。*

### Property 1: API 响应结构完整性

*For any* 有效的用户消息请求，Agent API 返回的 JSON 响应必须包含 `reply`（非空字符串）、`session_id`、`trace_id` 和 `metadata` 字段，且 metadata 中包含 `provider`、`model` 和 `duration_ms`。

**Validates: Requirements 1.2**

### Property 2: 无效请求拒绝

*For any* 格式错误的请求（缺少必填字段、字段类型错误、值超出范围），Agent API 必须返回 HTTP 422 状态码，且响应体包含描述性验证错误消息。

**Validates: Requirements 1.4**

### Property 3: SSE 流式事件格式正确性

*For any* 启用流式输出的有效请求，返回的 SSE 事件流中每个事件必须包含 `event` 类型字段（值为 token/tool_call/done/error 之一）和 `data` 字段（有效 JSON），且流必须以 `done` 或 `error` 事件结束。

**Validates: Requirements 1.5**

### Property 4: Agent 路由决策正确性

*For any* Agent 状态，当 LLM 返回的消息包含 tool_calls 时，Agent 必须执行工具调用节点；当 LLM 返回的消息不包含 tool_calls 时，Agent 必须直接进入响应节点而不调用任何工具。

**Validates: Requirements 2.3, 2.4**

### Property 5: RAG 检索结果传递完整性

*For any* RAG_Tool 返回的检索结果，该结果必须作为 ToolMessage 完整传递到 Agent 的消息历史中，供 LLM 在后续推理中使用。

**Validates: Requirements 2.5**

### Property 6: RAG Tool 输入接受性

*For any* 非空查询字符串和任意可选的知识库标识符，RAG_Tool 必须接受该输入并返回结构化结果（成功结果或描述性错误消息），不抛出未处理异常。

**Validates: Requirements 3.3, 3.4, 3.5**

### Property 7: 会话历史加载正确性

*For any* 已存在的会话（包含 N 条历史消息），当发送新消息时，传递给 LLM 的上下文必须包含该会话的历史消息（可能经过压缩），且新消息位于历史之后。

**Validates: Requirements 4.2**

### Property 8: 新会话初始化

*For any* 不带 session_id 或带不存在 session_id 的请求，系统必须创建一个新的 Conversation_Session，其初始消息历史为空。

**Validates: Requirements 4.3**

### Property 9: 会话删除完整性

*For any* 已存在的会话，执行删除操作后，该会话 ID 不再可查询，其关联的消息历史不再可访问。

**Validates: Requirements 4.5**

### Property 10: 上下文窗口压缩保证

*For any* 消息数超过配置阈值的对话历史，经过压缩后传递给 LLM 的消息数必须不超过配置的最大消息数限制，且最近的消息必须被保留。

**Validates: Requirements 4.6**

### Property 11: LLM 消息格式正确性

*For any* 对话状态（包含系统消息、用户消息、助手消息和工具结果），发送给 LLM 提供商的请求必须符合 OpenAI Chat Completion API 格式，每条消息包含正确的 `role` 和 `content` 字段。

**Validates: Requirements 5.1, 5.6**

### Property 12: 提供商配置 CRUD 一致性

*For any* 有效的提供商配置，执行添加操作后该配置可被查询到；执行修改操作后查询返回修改后的值；执行删除操作后该配置不再可查询。

**Validates: Requirements 5.2, 5.7**

### Property 13: 提供商选择逻辑

*For any* 请求，若指定了 provider 参数则使用指定提供商；若未指定则使用默认提供商配置。选择的提供商必须与实际发送 API 请求的端点一致。

**Validates: Requirements 5.3**

### Property 14: 生成参数透传

*For any* 请求中指定的生成参数（temperature、max_tokens、top_p），这些参数必须原样传递到 LLM API 调用中，不被修改或丢弃。

**Validates: Requirements 5.5**

### Property 15: RAG 不可用时的优雅降级

*For any* 不需要知识检索的用户查询，即使 RAG 系统完全不可用，Agent 仍必须返回有效响应（非错误状态码）。

**Validates: Requirements 6.5**

### Property 16: 异常处理一致性

*For any* Agent 执行过程中抛出的未处理异常，API 必须返回包含 trace_id 的通用错误响应（非 500 裸错误），且异常详情被记录到日志中而非暴露给客户端。

**Validates: Requirements 7.1**

### Property 17: 响应追踪标识符

*For any* API 请求（无论成功或失败），响应中必须包含非空的 `trace_id` 字段，且该 trace_id 与服务端日志中记录的一致。

**Validates: Requirements 7.3**

### Property 18: 工具超时处理

*For any* 超过配置超时时间的工具调用，Agent 必须中止该调用并返回包含超时信息的 ToolMessage，而非无限等待。

**Validates: Requirements 7.4**
