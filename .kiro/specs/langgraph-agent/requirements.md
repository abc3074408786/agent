# 需求文档

## 简介

本文档定义了在现有 RAG 系统（D:\rag_app）旁新增独立 LangGraph Agent 模块的需求。该模块使用 LangGraph 作为 Agent 框架，管理对话流程和状态，将现有 RAG 系统作为 Agent 的一个工具（Tool）进行调用。Agent 通过 FastAPI 提供 API 接口，与现有 RAG API 共存，支持多轮对话和上下文记忆。LLM 推理使用本地 vLLM 服务（兼容 OpenAI API 格式）。

## 术语表

- **Agent**: 基于 LangGraph 构建的智能代理，能够自主决策调用工具或直接回答用户问题
- **LangGraph**: LangChain 生态中的 Agent 框架，用于构建有状态的多步骤对话流程
- **RAG_Tool**: 将现有 RAG 系统封装为 Agent 可调用的工具，提供知识库检索能力
- **vLLM_Service**: 本地部署的 vLLM 推理服务，提供兼容 OpenAI API 格式的 LLM 接口
- **Conversation_Session**: 一次多轮对话的完整会话，包含上下文历史和状态信息
- **Agent_API**: 为 Agent 模块提供的 FastAPI REST 接口
- **Agent_State**: LangGraph 管理的 Agent 运行时状态，包含消息历史、工具调用记录等
- **Agent_Module**: 新增的 agent/ 目录模块，与现有 rag/ 模块并列存在

## 需求

### 需求 1: Agent 对话接口

**用户故事:** 作为开发者，我希望通过 REST API 与 Agent 交互，以便发送消息并接收智能响应。

#### 验收标准

1. Agent_API 应提供一个 POST 端点，用于提交用户消息并接收 Agent 响应
2. 当收到用户消息时，Agent_API 应以结构化 JSON 格式返回 Agent 的响应，包含回复文本和元数据
3. Agent_API 应接受会话标识符参数，将消息关联到特定的 Conversation_Session
4. 如果 Agent_API 收到格式错误的请求，则应返回 HTTP 422 错误并附带描述性验证消息
5. Agent_API 应支持通过 Server-Sent Events 进行流式响应，实现实时输出

### 需求 2: LangGraph Agent 流程编排

**用户故事:** 作为开发者，我希望 Agent 能自主决定何时使用 RAG 检索、何时直接回答，以便响应既准确又高效。

#### 验收标准

1. Agent 应使用 LangGraph 定义一个有状态的图来编排决策流程
2. 当收到用户消息时，Agent 应评估该问题是否需要知识检索，还是可以直接回答
3. 当 Agent 判定需要知识检索时，Agent 应调用 RAG_Tool 执行检索
4. 当 Agent 判定可以从通用知识或对话上下文中回答时，Agent 应直接生成响应而不调用 RAG_Tool
5. Agent 应将 RAG_Tool 的检索结果作为上下文传递给 LLM 进行最终答案生成

### 需求 3: RAG 系统工具封装

**用户故事:** 作为开发者，我希望将现有 RAG 系统封装为 Agent 工具，以便 Agent 能利用知识库进行检索增强生成。

#### 验收标准

1. Agent_Module 应提供一个 RAG_Tool，封装现有 RAG 系统的检索 API
2. 当 RAG_Tool 被调用时，应调用现有 RAG 系统的查询端点并返回检索到的文档和生成的答案
3. RAG_Tool 应接受查询字符串和可选的知识库标识符作为输入参数
4. 如果 RAG 系统返回错误或不可用，则 RAG_Tool 应向 Agent 返回描述性错误消息以便优雅处理
5. RAG_Tool 应将检索结果格式化为结构化表示，以便 Agent 纳入其推理过程

### 需求 4: 多轮对话与上下文记忆

**用户故事:** 作为用户，我希望 Agent 能记住对话中之前的消息，以便进行连贯的多轮对话。

#### 验收标准

1. Agent 应使用 LangGraph 状态管理在 Conversation_Session 内维护对话历史
2. 当收到带有已存在会话标识符的消息时，Agent 应加载对应的对话历史并纳入当前推理上下文
3. 当发起新会话时，Agent 应创建一个空历史的新 Conversation_Session
4. Agent_API 应提供端点列出指定用户或客户端的活跃会话
5. Agent_API 应提供端点删除特定的 Conversation_Session 及其关联历史
6. 当 Conversation_Session 中的消息超过配置的上下文窗口限制时，Agent 应截断或摘要较早的消息以适应 LLM 上下文约束

### 需求 5: 多 LLM 提供商集成

**用户故事:** 作为开发者，我希望 Agent 支持多种 LLM 提供商（本地 vLLM、OpenAI、Anthropic、Google、MiniMax、Moonshot、SiliconFlow、OpenRouter、ByteDance Ark、Ollama 及自定义提供商），以便灵活切换模型。

#### 验收标准

1. Agent 应通过统一的 OpenAI 兼容 API 格式连接各 LLM 提供商进行聊天补全
2. Agent_Module 应支持配置多个 LLM 提供商，每个提供商包含名称、端点 URL、API Key 和默认模型名称
3. Agent_API 应允许在请求中指定使用哪个提供商和模型，未指定时使用默认配置
4. 如果指定的 LLM 提供商不可达或返回错误，则 Agent 应向调用方返回服务不可用错误并附带描述性消息
5. Agent 应支持可配置的生成参数，包括 temperature、max_tokens 和 top_p
6. Agent 应将对话历史和工具结果作为格式正确的消息发送给选定的 LLM 提供商
7. Agent_Module 应支持通过配置文件或 API 动态添加、修改和删除 LLM 提供商配置

### 需求 6: 模块架构与共存

**用户故事:** 作为开发者，我希望 Agent 模块与现有 RAG 模块无冲突共存，以便两个系统可以独立或一起运行。

#### 验收标准

1. Agent_Module 应位于项目根目录下独立的 agent/ 目录中，与现有 rag/ 目录并列
2. Agent_API 应作为独立路由器挂载到现有 FastAPI 应用上，使用不同的 URL 前缀
3. Agent_Module 应管理自己的依赖，不与现有 RAG 模块的依赖冲突
4. Agent_Module 应使用自己的配置文件或配置段落存放 Agent 特定设置
5. 当现有 RAG 系统不可用时，Agent 应继续为直接回答类查询提供服务，仅在尝试检索时报告 RAG_Tool 不可用

### 需求 7: 错误处理与可观测性

**用户故事:** 作为开发者，我希望 Agent 能优雅处理错误并提供可观测性，以便有效监控和调试系统。

#### 验收标准

1. 如果 Agent 执行过程中发生未处理的异常，则应记录完整上下文的错误日志并向客户端返回通用错误响应
2. Agent 应记录 LangGraph 执行流程的每个步骤，包括节点转换和工具调用
3. Agent_API 应在响应中包含请求追踪标识符，用于与服务端日志关联
4. 如果工具调用超时，则 Agent 应中止该工具调用，并使用已有信息继续处理或向用户返回错误
5. Agent_Module 应暴露健康检查端点，报告 Agent 及其依赖（包括 vLLM_Service 连接性）的状态
