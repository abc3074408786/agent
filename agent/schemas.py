"""Agent 模块 Pydantic 数据模型定义

定义 Agent API 的请求/响应模型，包含字段验证约束。
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ToolCallInfo(BaseModel):
    """工具调用信息"""

    tool_name: str = Field(..., description="工具名称")
    input_params: dict = Field(..., description="工具输入参数")
    output_summary: str = Field(..., description="工具输出摘要")
    duration_ms: float = Field(..., ge=0.0, description="工具调用耗时（毫秒）")


class ResponseMetadata(BaseModel):
    """响应元数据"""

    provider: str = Field(..., description="LLM 提供商名称")
    model: str = Field(..., description="模型名称")
    tokens_used: Optional[int] = Field(None, ge=0, description="消耗的 token 数量")
    duration_ms: float = Field(..., ge=0.0, description="请求总耗时（毫秒）")
    used_rag: bool = Field(False, description="是否使用了 RAG 检索")


class ChatRequest(BaseModel):
    """Agent 对话请求"""

    message: str = Field(..., min_length=1, description="用户消息")
    session_id: Optional[str] = Field(None, description="会话ID，为空则创建新会话")
    provider: Optional[str] = Field(None, description="LLM提供商名称")
    model: Optional[str] = Field(None, description="模型名称")
    stream: bool = Field(False, description="是否启用SSE流式输出")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="生成温度")
    max_tokens: Optional[int] = Field(None, gt=0, description="最大生成 token 数")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Top-p 采样参数")
    knowledge_base_id: Optional[str] = Field(None, description="知识库标识符")


class ChatResponse(BaseModel):
    """Agent 对话响应"""

    reply: str = Field(..., description="Agent回复文本")
    session_id: str = Field(..., description="会话ID")
    trace_id: str = Field(..., description="请求追踪ID")
    tool_calls: List[ToolCallInfo] = Field(default_factory=list, description="工具调用记录")
    metadata: ResponseMetadata = Field(..., description="响应元数据")


class SessionInfo(BaseModel):
    """会话信息"""

    session_id: str = Field(..., description="会话ID")
    created_at: datetime = Field(..., description="创建时间")
    last_active_at: datetime = Field(..., description="最后活跃时间")
    message_count: int = Field(..., ge=0, description="消息数量")


class SSEEvent(BaseModel):
    """SSE 流式事件"""

    event: str = Field(..., description="事件类型: token|tool_call|done|error")
    data: str = Field(..., description="事件数据")
