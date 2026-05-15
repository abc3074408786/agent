# 实施计划: LangGraph Agent 模块

## 概述

基于 LangGraph ReAct 模式构建独立 Agent 模块，与现有 RAG 系统并列部署。实施采用自底向上策略：先搭建项目结构和核心接口，再逐步实现各组件，最后集成联调。

## 任务

- [ ] 1. 搭建项目结构与核心接口
  - [x] 1.1 创建 agent/ 目录结构和基础文件
    - 创建 `agent/` 目录及所有子目录（graph/、tools/、llm/、memory/、observability/）
    - 创建各目录的 `__init__.py` 文件
    - 创建 `config/agent_config.yaml` 配置文件模板
    - _需求: 6.1, 6.4_

  - [ ] 1.2 定义 Pydantic 数据模型（schemas.py）
    - 实现 `ChatRequest`、`ChatResponse`、`ToolCallInfo`、`ResponseMetadata`、`SessionInfo`、`SSEEvent` 模型
    - 添加字段验证约束（min_length、ge/le 范围等）
    - _需求: 1.1, 1.2, 1.4_

  - [ ] 1.3 实现配置管理模块（config.py）
    - 实现 `LLMProviderConfig` 模型
    - 实现 `ConfigManager` 类，支持从 YAML 文件加载配置
    - 支持环境变量替换（`${ENV_VAR}` 语法）
    - _需求: 5.2, 6.4_

  - [x] 1.4 定义 LangGraph Agent 状态（graph/state.py）
    - 实现 `AgentState` TypedDict，包含 messages、session_id、trace_id、current_provider、current_model 字段
    - 使用 `Annotated[Sequence[BaseMessage], add_messages]` 定义消息累加器
    - _需求: 2.1_

- [ ] 2. 实现 LLM 提供商管理
  - [ ] 2.1 实现 LLM 提供商工厂（llm/provider.py）
    - 实现 `LLMProviderFactory` 类
    - 通过 `ChatOpenAI` 统一接入各提供商（OpenAI 兼容模式）
    - 支持 provider_name 和 model 参数选择
    - 未指定时使用默认提供商配置
    - _需求: 5.1, 5.3_

  - [ ] 2.2 实现提供商配置 CRUD API
    - 实现 GET `/api/agent/providers` 列出已配置提供商
    - 实现 POST `/api/agent/providers` 添加提供商
    - 实现 PUT `/api/agent/providers/{name}` 修改提供商
    - 实现 DELETE `/api/agent/providers/{name}` 删除提供商
    - 配置变更持久化到 YAML 文件
    - _需求: 5.2, 5.7_

  - [ ]* 2.3 编写 LLM 提供商管理属性测试
    - **Property 12: 提供商配置 CRUD 一致性**
    - **Property 13: 提供商选择逻辑**
    - **验证: 需求 5.2, 5.3, 5.7**

  - [ ]* 2.4 编写 LLM 提供商单元测试
    - 测试工厂创建 LLM 实例的参数传递
    - 测试默认提供商回退逻辑
    - 测试无效提供商名称的错误处理
    - _需求: 5.1, 5.3, 5.4_

- [ ] 3. 实现会话与上下文管理
  - [ ] 3.1 实现会话存储（memory/session.py）
    - 实现 `SessionStore` 类（内存实现）
    - 支持 create_session、get_session、delete_session、list_sessions 操作
    - 会话数据包含 messages、created_at、last_active_at
    - _需求: 4.1, 4.3, 4.4, 4.5_

  - [ ] 3.2 实现上下文压缩器（memory/compressor.py）
    - 实现 `ContextCompressor` 类
    - 实现 truncate 策略：保留系统消息 + 最近 N 条消息
    - 实现 summarize 策略：使用 LLM 将早期消息压缩为摘要
    - 当消息数超过阈值时自动触发压缩
    - _需求: 4.6_

  - [ ]* 3.3 编写会话管理属性测试
    - **Property 8: 新会话初始化**
    - **Property 9: 会话删除完整性**
    - **Property 10: 上下文窗口压缩保证**
    - **验证: 需求 4.3, 4.5, 4.6**

- [ ] 4. 实现 RAG 工具封装
  - [ ] 4.1 实现 RAG 工具（tools/rag_tool.py）
    - 使用 `@tool` 装饰器定义 `rag_search` 工具
    - 接受 query（必填）和 knowledge_base_id（可选）参数
    - 通过 httpx 异步调用现有 RAG 系统 API
    - 返回结构化 `RAGToolResult`（包含 success、answer、documents、error_message）
    - 实现超时处理和错误捕获，返回描述性错误消息而非抛出异常
    - _需求: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 4.2 编写 RAG 工具属性测试
    - **Property 6: RAG Tool 输入接受性**
    - **Property 15: RAG 不可用时的优雅降级**
    - **验证: 需求 3.3, 3.4, 3.5, 6.5**

- [ ] 5. 检查点 - 确保基础组件测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [ ] 6. 实现 LangGraph 图编排
  - [ ] 6.1 实现图节点（graph/nodes.py）
    - 实现 `load_session_state` 节点：加载会话历史到 Agent 状态
    - 实现 `create_agent_node` 节点：调用 LLM 进行决策（绑定工具）
    - 实现 `format_response` 节点：格式化最终响应
    - 实现 `save_session_state` 节点：保存更新后的会话状态
    - _需求: 2.1, 2.2, 4.2_

  - [ ] 6.2 实现图构建器（graph/builder.py）
    - 实现 `build_agent_graph` 函数
    - 定义 StateGraph 节点和边
    - 实现 `should_use_tools` 条件边：根据 AIMessage.tool_calls 判断路由
    - 工具调用后返回 agent 节点再次决策
    - 编译生成可执行图
    - _需求: 2.1, 2.3, 2.4, 2.5_

  - [ ]* 6.3 编写 Agent 图路由属性测试
    - **Property 4: Agent 路由决策正确性**
    - **Property 5: RAG 检索结果传递完整性**
    - **验证: 需求 2.3, 2.4, 2.5**

  - [ ]* 6.4 编写 Agent 图单元测试
    - 测试 should_use_tools 条件边的路由逻辑
    - 测试图节点的状态转换
    - 测试工具调用循环的终止条件（max_iterations）
    - _需求: 2.1, 2.3, 2.4_

- [ ] 7. 实现可观测性
  - [ ] 7.1 实现结构化日志（observability/logging.py）
    - 使用 structlog 配置结构化 JSON 日志
    - 实现 trace_id ContextVar 绑定
    - 提供 `get_logger` 工厂函数
    - _需求: 7.1, 7.2_

  - [ ] 7.2 实现请求追踪中间件（observability/tracing.py）
    - 实现 `TraceMiddleware`：为每个请求生成/提取 trace_id
    - 支持从请求头 `X-Trace-ID` 读取或自动生成
    - 将 trace_id 设置到 ContextVar 并添加到响应头
    - _需求: 7.3_

- [ ] 8. 实现 FastAPI 路由与 SSE 流式输出
  - [ ] 8.1 实现 Agent API 路由器（agent/main.py）
    - 实现 POST `/api/agent/chat` 同步对话端点
    - 实现 GET `/api/agent/sessions` 列出会话
    - 实现 DELETE `/api/agent/sessions/{session_id}` 删除会话
    - 实现 GET `/api/agent/health` 健康检查端点
    - 集成 LangGraph 图执行、会话管理和 LLM 提供商工厂
    - _需求: 1.1, 1.2, 1.3, 4.4, 4.5, 7.5_

  - [ ] 8.2 实现 SSE 流式输出端点
    - 实现 POST `/api/agent/chat/stream` 流式端点
    - 使用 `StreamingResponse` 和 `text/event-stream` 内容类型
    - 实现 token/tool_call/done/error 事件类型
    - 流式传输 LLM 生成的 token 和工具调用状态
    - 确保流以 done 或 error 事件结束
    - _需求: 1.5_

  - [ ] 8.3 实现错误处理与异常中间件
    - 实现全局异常处理器：捕获未处理异常，记录日志，返回通用错误响应
    - 实现工具超时处理：`execute_tool_with_timeout` 函数
    - 确保所有错误响应包含 trace_id
    - LLM 提供商不可达时返回 HTTP 503
    - _需求: 7.1, 7.4, 5.4, 1.4_

  - [ ]* 8.4 编写 API 响应属性测试
    - **Property 1: API 响应结构完整性**
    - **Property 2: 无效请求拒绝**
    - **Property 3: SSE 流式事件格式正确性**
    - **Property 16: 异常处理一致性**
    - **Property 17: 响应追踪标识符**
    - **验证: 需求 1.2, 1.4, 1.5, 7.1, 7.3**

- [ ] 9. 集成与应用入口
  - [ ] 9.1 实现应用入口（main.py）
    - 创建 FastAPI 应用实例
    - 挂载 Agent 路由器到 `/api/agent` 前缀
    - 注册 TraceMiddleware
    - 注册全局异常处理器
    - 添加启动事件：初始化配置、会话存储、LLM 工厂
    - _需求: 6.2_

  - [ ] 9.2 更新依赖文件（requirements.txt）
    - 添加 Agent 模块依赖：langgraph、langchain-core、langchain-openai、structlog、httpx、pyyaml
    - 确保不与现有 RAG 模块依赖冲突
    - _需求: 6.3_

  - [ ]* 9.3 编写集成测试
    - 测试完整对话流程（发送消息 → Agent 决策 → 工具调用 → 返回响应）
    - 测试多轮对话上下文保持
    - 测试 RAG 系统不可用时的降级行为
    - **Property 7: 会话历史加载正确性**
    - **Property 11: LLM 消息格式正确性**
    - **Property 14: 生成参数透传**
    - **Property 18: 工具超时处理**
    - **验证: 需求 4.2, 5.1, 5.5, 5.6, 6.5, 7.4**

- [ ] 10. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求条目以确保可追溯性
- 检查点确保增量验证，及时发现问题
- 属性测试验证系统的通用正确性属性
- 单元测试验证具体示例和边界情况
- 所有 LLM 提供商通过 OpenAI 兼容 API 格式统一接入，简化集成复杂度

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.4"] },
    { "id": 1, "tasks": ["1.2", "1.3"] },
    { "id": 2, "tasks": ["2.1", "3.1", "3.2", "7.1", "7.2"] },
    { "id": 3, "tasks": ["2.2", "2.3", "2.4", "3.3", "4.1"] },
    { "id": 4, "tasks": ["4.2", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4"] },
    { "id": 6, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 7, "tasks": ["8.4", "9.1", "9.2"] },
    { "id": 8, "tasks": ["9.3"] }
  ]
}
```
