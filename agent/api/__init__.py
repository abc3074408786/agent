"""
API Service Layer - FastAPI 服务层

提供:
- RESTful API 接口
- SSE 流式响应
- WebSocket 支持
- 健康检查
- 优雅关闭
- OpenAPI 文档
"""

from typing import Any, AsyncGenerator, Dict, List, Optional
import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from agent.observability import get_logger, get_tracer
from agent.schemas import ChatRequest, ChatResponse, Message, MessageRole, SSEEvent, SSEEventType
from agent.middleware import (
    MiddlewarePipeline,
    MiddlewareContext,
    MiddlewarePipelineError,
    create_default_pipeline,
)
from agent.streaming import StreamEngine, StreamEvent, StreamEventType, create_stream_engine

logger = get_logger("api")
tracer = get_tracer("api")


# ============ App Factory ============

def create_app(
    agent_factory=None,
    middleware_pipeline: Optional[MiddlewarePipeline] = None,
    enable_cors: bool = True,
    api_keys: Optional[set] = None,
    title: str = "Agent API",
    version: str = "1.0.0",
):
    """
    创建 FastAPI 应用

    Args:
        agent_factory: Agent 工厂函数 (返回 AgentExecutor)
        middleware_pipeline: 中间件管道
        enable_cors: 是否启用 CORS
        api_keys: API 密钥集合
        title: API 标题
        version: API 版本

    Returns:
        FastAPI 应用实例
    """
    try:
        from fastapi import FastAPI, HTTPException, Request, Depends, Header
        from fastapi.responses import StreamingResponse, JSONResponse
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError:
        raise ImportError(
            "FastAPI is required for the API layer. "
            "Install it with: pip install fastapi uvicorn"
        )

    # 状态管理
    state = {
        "agent_factory": agent_factory,
        "pipeline": middleware_pipeline or create_default_pipeline(api_keys=api_keys),
        "stream_engine": create_stream_engine(enable_rate_limit=True),
        "active_sessions": {},
        "is_shutting_down": False,
    }

    # 生命周期管理
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(f"Starting {title} v{version}")
        yield
        logger.info("Shutting down...")
        state["is_shutting_down"] = True
        # 等待活跃会话完成
        if state["active_sessions"]:
            logger.info(f"Waiting for {len(state['active_sessions'])} active sessions...")
            await asyncio.sleep(2)

    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan,
    )

    # CORS
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ============ 认证依赖 ============

    async def verify_api_key(authorization: Optional[str] = Header(None)):
        """验证 API Key"""
        if not api_keys:
            return None  # 不需要认证

        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        token = authorization.replace("Bearer ", "")
        if token not in api_keys:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return token

    # ============ 路由 ============

    @app.get("/health")
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy" if not state["is_shutting_down"] else "shutting_down",
            "version": version,
            "active_sessions": len(state["active_sessions"]),
        }

    @app.get("/ready")
    async def readiness_check():
        """就绪检查"""
        if state["is_shutting_down"]:
            raise HTTPException(status_code=503, detail="Shutting down")
        if not state["agent_factory"]:
            raise HTTPException(status_code=503, detail="Agent not configured")
        return {"status": "ready"}

    @app.post("/v1/chat")
    async def chat(
        request: Request,
        api_key: Optional[str] = Depends(verify_api_key),
    ):
        """
        聊天接口 (同步)

        接收消息，返回完整响应
        """
        body = await request.json()
        chat_request = ChatRequest(**body)

        # 中间件处理
        context = MiddlewareContext(
            auth_token=api_key,
            session_id=chat_request.session_id,
            metadata={"client_ip": request.client.host if request.client else "unknown"},
        )

        try:
            pipeline = state["pipeline"]
            chat_request, context = await pipeline.process_request(chat_request, context)

            # 执行 Agent
            agent = state["agent_factory"]()
            if not agent:
                raise HTTPException(status_code=503, detail="Agent not available")

            result = agent.invoke(chat_request.messages[-1].content if chat_request.messages else "")

            # 构建响应
            response = ChatResponse(
                session_id=chat_request.session_id or str(uuid.uuid4()),
                messages=[Message(
                    role=MessageRole.ASSISTANT,
                    content=result["messages"][-1].content if result.get("messages") else "",
                )],
                metadata={
                    "request_id": context.request_id,
                    "iterations": result.get("iteration", 0),
                },
            )

            response = await pipeline.process_response(response, context)
            return response.model_dump() if hasattr(response, 'model_dump') else response.__dict__

        except MiddlewarePipelineError as e:
            resp = e.response
            return JSONResponse(
                status_code=resp.metadata.get("status_code", 500) if resp.metadata else 500,
                content=resp.model_dump() if hasattr(resp, 'model_dump') else resp.__dict__,
            )
        except Exception as e:
            logger.error(f"Chat error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/chat/stream")
    async def chat_stream(
        request: Request,
        api_key: Optional[str] = Depends(verify_api_key),
    ):
        """
        聊天接口 (SSE 流式)

        接收消息，以 SSE 事件流返回响应
        """
        body = await request.json()
        chat_request = ChatRequest(**body)

        context = MiddlewareContext(
            auth_token=api_key,
            session_id=chat_request.session_id,
            metadata={"client_ip": request.client.host if request.client else "unknown"},
        )

        try:
            pipeline = state["pipeline"]
            chat_request, context = await pipeline.process_request(chat_request, context)
        except MiddlewarePipelineError as e:
            error_sse = f"event: error\ndata: {json.dumps({'error': str(e.original_error)})}\n\n"
            return StreamingResponse(
                iter([error_sse]),
                media_type="text/event-stream",
            )

        async def event_generator():
            try:
                agent = state["agent_factory"]()
                if not agent:
                    yield f"event: error\ndata: {json.dumps({'error': 'Agent not available'})}\n\n"
                    return

                # 注册活跃会话
                session_id = chat_request.session_id or str(uuid.uuid4())
                state["active_sessions"][session_id] = True

                try:
                    user_message = chat_request.messages[-1].content if chat_request.messages else ""

                    # 流式执行
                    async for chunk in agent.astream(user_message):
                        for node_name, node_output in chunk.items():
                            if isinstance(node_output, dict) and "messages" in node_output:
                                for msg in node_output["messages"]:
                                    if hasattr(msg, "content") and msg.content:
                                        event = StreamEvent(
                                            type=StreamEventType.CONTENT_DELTA,
                                            data={
                                                "content": msg.content,
                                                "node": node_name,
                                            },
                                        )
                                        yield event.to_sse()

                                    # 工具调用
                                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                                        for tc in msg.tool_calls:
                                            event = StreamEvent(
                                                type=StreamEventType.TOOL_CALL_START,
                                                data={
                                                    "tool_name": tc.get("name", ""),
                                                    "arguments": tc.get("args", {}),
                                                },
                                            )
                                            yield event.to_sse()

                    # 完成事件
                    done_event = StreamEvent(
                        type=StreamEventType.DONE,
                        data={"session_id": session_id},
                    )
                    yield done_event.to_sse()

                finally:
                    state["active_sessions"].pop(session_id, None)

            except Exception as e:
                logger.error(f"Stream error: {e}", exc_info=True)
                error_event = StreamEvent(
                    type=StreamEventType.ERROR,
                    data={"error": str(e), "error_type": type(e).__name__},
                )
                yield error_event.to_sse()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Request-ID": context.request_id,
            },
        )

    @app.get("/v1/sessions")
    async def list_sessions(api_key: Optional[str] = Depends(verify_api_key)):
        """列出活跃会话"""
        return {
            "active_sessions": list(state["active_sessions"].keys()),
            "count": len(state["active_sessions"]),
        }

    @app.delete("/v1/sessions/{session_id}")
    async def stop_session(
        session_id: str,
        api_key: Optional[str] = Depends(verify_api_key),
    ):
        """停止会话"""
        if session_id in state["active_sessions"]:
            del state["active_sessions"][session_id]
            return {"status": "stopped", "session_id": session_id}
        raise HTTPException(status_code=404, detail="Session not found")

    @app.get("/v1/models")
    async def list_models(api_key: Optional[str] = Depends(verify_api_key)):
        """列出可用模型"""
        from agent.llm import llm_manager
        return {
            "models": llm_manager.list_models(),
        }

    return app


# ============ 服务器启动 ============

def run_server(
    app=None,
    host: str = "0.0.0.0",
    port: int = 8000,
    workers: int = 1,
    reload: bool = False,
    **kwargs,
):
    """
    启动 API 服务器

    Args:
        app: FastAPI 应用 (或 None 使用默认)
        host: 监听地址
        port: 监听端口
        workers: 工作进程数
        reload: 是否自动重载
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError("uvicorn is required. Install with: pip install uvicorn")

    if app is None:
        app = create_app(**kwargs)

    uvicorn.run(
        app,
        host=host,
        port=port,
        workers=workers,
        reload=reload,
    )


__all__ = [
    "create_app",
    "run_server",
]
