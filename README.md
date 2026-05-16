# Agent - 生产级 AI Agent 框架

> 基于 LangGraph ReAct 模式构建的高性能 AI Agent 开发框架，提供完整的工具链、技能系统和多 Agent 协调能力。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.2.0-orange.svg)](pyproject.toml)

```
  ____  生产级框架    ____  20 个工具    ____  11 技能包
 / _  | 13,532 行   / _  | 6 核心算法  / _  | 12 预制Agent
| (_| | 161 测试    | (_| | 多LLM支持  | (_| | 3种交互方式
 \__,_| Python     \__,_| 流式响应    \__,_| Docker部署
```

---

## 功能特性

- **多 LLM 支持** — OpenAI (GPT-4/4o) + Anthropic (Claude) 双引擎，自动降级和负载均衡
- **20 个内置工具** — 文件操作、Bash 执行、Git/GitHub 集成、HTTP 请求、计算器等
- **11 个技能包** — YAML 定义的领域专家（架构师、安全审计、Python 专家等）
- **12 个预制 Agent** — 开箱即用的专业 Agent（代码审查、Bug 修复、全栈开发等）
- **6 个核心算法** — Token 估算、SWR 缓存、优先级队列、流式执行器、高级重试、上下文压缩
- **多 Agent 协调** — Coordinator + Worker 模式，支持任务分解和并行执行
- **流式响应** — SSE 实时流式输出，支持速率控制和 Token 计数
- **安全权限系统** — 工具级权限控制，命令黑名单，敏感文件保护
- **上下文管理** — 自动上下文压缩，滑动窗口，128K Token 支持
- **可观测性** — 结构化日志、链路追踪、OpenTelemetry 集成
- **中间件系统** — 速率限制、输入验证、可扩展管道
- **会话持久化** — 支持 Redis 后端的会话存储
- **Hook 系统** — 生命周期钩子，支持 before/after 工具调用拦截
- **三种使用方式** — CLI 终端 / REST API 服务 / Telegram Bot

---

## 快速开始

### 安装

```bash
# 基础安装
pip install -e .

# 带 OpenAI 支持
pip install -e ".[openai]"

# 带 Anthropic 支持
pip install -e ".[anthropic]"

# 全部可选依赖 (推荐)
pip install -e ".[all]"

# 开发模式 (含测试工具)
pip install -e ".[all,dev]"
```

### 环境变量

```bash
# 必需 (至少设置一个 LLM Provider)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# 可选
export REDIS_URL="redis://localhost:6379/0"
export AGENT_MODEL="gpt-4o"              # 默认模型
export AGENT_TEMPERATURE="0.7"           # 默认温度
export TELEGRAM_BOT_TOKEN="xxx:yyy"      # Telegram Bot Token
export TELEGRAM_ALLOWED_USERS="123,456"  # 白名单用户 ID
```

### 方式一：CLI 终端交互

```bash
# 启动 CLI
python cli.py
# 或通过入口点
agent-cli

# 支持命令:
#   /help   - 帮助信息
#   /tools  - 列出工具
#   /skills - 列出技能
#   /cost   - 会话消耗统计
#   /clear  - 清除对话
#   /exit   - 退出
```

### 方式二：REST API 服务

```bash
# 启动 API 服务
agent-server
# 或手动指定
uvicorn agent.api:create_app --host 0.0.0.0 --port 8000 --factory

# 调用示例
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "帮我分析这段代码的性能问题"}'
```

### 方式三：Telegram Bot

```bash
# 设置 Token
export TELEGRAM_BOT_TOKEN="your-bot-token"
export OPENAI_API_KEY="sk-..."

# 启动 Bot
agent-telegram

# 支持命令: /start, /help, /clear, /cost
# 特性: 用户白名单、速率限制、长消息自动分割、多用户会话隔离
```

---

## 项目架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户接入层                                    │
│   ┌──────────┐    ┌──────────────┐    ┌───────────────────┐        │
│   │  CLI     │    │  REST API    │    │  Telegram Bot     │        │
│   │ (REPL)   │    │  (FastAPI)   │    │  (Long Polling)   │        │
│   └────┬─────┘    └──────┬───────┘    └────────┬──────────┘        │
└────────┼─────────────────┼─────────────────────┼────────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       中间件管道                                      │
│   ┌──────────┐    ┌───────────────┐    ┌───────────────────┐       │
│   │ 速率限制  │───▶│  输入验证     │───▶│   权限检查         │       │
│   └──────────┘    └───────────────┘    └───────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     核心引擎 (LangGraph)                              │
│                                                                      │
│   ┌──────────────┐     ┌───────────────┐     ┌──────────────┐      │
│   │ Coordinator  │────▶│  Agent Graph  │────▶│   Streaming  │      │
│   │ (任务分解)    │     │  (ReAct Loop) │     │  (SSE 输出)   │      │
│   └──────────────┘     └───────┬───────┘     └──────────────┘      │
│                                │                                     │
│          ┌─────────────────────┼──────────────────────┐             │
│          ▼                     ▼                      ▼             │
│   ┌────────────┐      ┌────────────────┐     ┌────────────┐        │
│   │   Tools    │      │    LLM Layer   │     │   Memory   │        │
│   │ (20 工具)  │      │ (多Provider)    │     │(Redis/Mem) │        │
│   └────────────┘      └────────────────┘     └────────────┘        │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     基础设施层                                        │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐      │
│   │Algorithms│  │Observable│  │  Hooks   │  │ Session Store│      │
│   │ (6 算法) │  │(日志+追踪)│  │(生命周期) │  │ (持久化)     │      │
│   └──────────┘  └──────────┘  └──────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 模块说明

| 模块 | 路径 | 说明 |
|------|------|------|
| **algorithms** | `agent/algorithms/` | 6 个核心算法：Token估算、SWR缓存、优先级队列、流式执行器、高级重试、上下文压缩 |
| **tools** | `agent/tools/` | 20 个内置工具：文件操作、Bash、Git、GitHub、HTTP、计算器、文本处理等 |
| **skills** | `agent/skills/` | 技能系统：YAML 定义领域专家，支持组合和热加载 |
| **presets** | `agent/presets/` | 12 个预制 Agent 模板，开箱即用 |
| **graph** | `agent/graph/` | LangGraph 图定义和状态管理 |
| **coordinator** | `agent/coordinator/` | 多 Agent 协调器，任务分解与分发 |
| **llm** | `agent/llm/` | LLM 抽象层，多 Provider 支持和模型降级 |
| **memory** | `agent/memory/` | 会话记忆，支持 Redis 后端 |
| **context** | `agent/context/` | 上下文窗口管理和自动压缩 |
| **streaming** | `agent/streaming/` | SSE 流式响应，速率控制 |
| **permissions** | `agent/permissions/` | 工具级权限引擎，支持 allow/ask/deny |
| **middleware** | `agent/middleware/` | 中间件管道：速率限制、输入验证 |
| **observability** | `agent/observability/` | 结构化日志 + 链路追踪 (OpenTelemetry) |
| **hooks** | `agent/hooks/` | 生命周期钩子系统 |
| **retry** | `agent/retry/` | 重试策略和断路器 |
| **integrations** | `agent/integrations/` | 外部集成（Telegram Bot） |
| **api** | `agent/api/` | FastAPI REST 服务 |
| **config** | `agent/config.py` | 统一配置管理 |
| **plugins** | `agent/plugins/` | 插件系统接口 |
| **rag** | `agent/rag/` | RAG（检索增强生成）模块 |

---

## 工具列表（20 个）

| # | 工具名 | 分类 | 说明 |
|---|--------|------|------|
| 1 | `calculator` | 数学 | 数学表达式计算（支持 sqrt/sin/cos/log 等） |
| 2 | `get_current_datetime` | 工具 | 获取当前时间（支持时区） |
| 3 | `web_search` | 搜索 | Web 搜索（需配置搜索 API） |
| 4 | `http_request` | 网络 | HTTP 请求（GET/POST/PUT/DELETE） |
| 5 | `json_parse` | 工具 | JSON 解析和路径提取 |
| 6 | `text_process` | 工具 | 文本处理（字数统计、URL/邮箱提取） |
| 7 | `file_read` | 文件 | 读取文件（支持行号范围） |
| 8 | `file_write` | 文件 | 创建/覆盖文件 |
| 9 | `file_edit` | 文件 | 字符串替换编辑（精确匹配） |
| 10 | `grep_search` | 文件 | 正则表达式搜索文件内容 |
| 11 | `glob_search` | 文件 | Glob 模式搜索文件路径 |
| 12 | `list_directory` | 文件 | 列出目录内容（递归支持） |
| 13 | `bash_execute` | 系统 | 安全 Bash 命令执行（黑名单+超时） |
| 14 | `git_status` | Git | 显示仓库状态 |
| 15 | `git_diff` | Git | 查看文件差异 |
| 16 | `git_log` | Git | 查看提交历史 |
| 17 | `git_commit` | Git | 提交更改 |
| 18 | `git_branch` | Git | 分支管理（list/create/switch） |
| 19 | `github_create_pr` | GitHub | 创建 Pull Request |
| 20 | `github_list_issues` | GitHub | 列出/查看 Issues |

---

## 技能包（11 个）

| 技能 | 文件 | 说明 |
|------|------|------|
| `architect` | `architect.yaml` | 系统架构设计和技术选型 |
| `code_reviewer` | `code_reviewer.yaml` | 代码审查：Bug、安全、性能 |
| `data_scientist` | `data_scientist.yaml` | 数据分析、建模、可视化 |
| `database_expert` | `database_expert.yaml` | 数据库设计和 SQL 优化 |
| `devops_engineer` | `devops_engineer.yaml` | CI/CD、容器化、自动化部署 |
| `frontend_expert` | `frontend_expert.yaml` | React/TypeScript 前端开发 |
| `performance_optimizer` | `performance_optimizer.yaml` | 性能分析和优化方案 |
| `python_expert` | `python_expert.yaml` | Python 最佳实践和高级特性 |
| `security_auditor` | `security_auditor.yaml` | 安全漏洞扫描和修复建议 |
| `technical_writer` | `technical_writer.yaml` | 技术文档、API 文档编写 |
| `test_engineer` | `test_engineer.yaml` | 测试策略和自动化测试 |

---

## 预制 Agent（12 个）

| Agent | 角色 | 说明 |
|-------|------|------|
| `code_reviewer` | 验证者 | 代码审查 + 安全审计组合 |
| `security_auditor` | 验证者 | 全面安全漏洞扫描 |
| `architect` | 研究者 | 系统设计 + 数据库专家组合 |
| `performance_optimizer` | 研究者 | 定位瓶颈并优化 |
| `python_developer` | 实现者 | Python 开发 + 测试组合 |
| `frontend_developer` | 实现者 | React/TS 开发 + 测试组合 |
| `devops_agent` | 实现者 | CI/CD 和容器化部署 |
| `data_analyst` | 研究者 | 数据探索和可视化 |
| `doc_writer` | 实现者 | API 文档和技术教程 |
| `full_stack` | 实现者 | 前端 + 后端 + DevOps 全栈 |
| `research_agent` | 研究者 | 代码库探索和信息收集 |
| `bug_fixer` | 实现者 | Bug 定位 + 修复 + 回归测试 |

---

## 配置说明

框架使用 `config.yaml` 统一管理配置，支持环境变量替换（`${VAR_NAME}` 语法）。

```yaml
# config.yaml 主要配置项

server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

llm:
  default: "openai"
  providers:
    - name: "openai"
      model: "gpt-4"
      api_key: "${OPENAI_API_KEY}"
      streaming: true
    - name: "anthropic"
      model: "claude-sonnet-4-20250514"
      api_key: "${ANTHROPIC_API_KEY}"

memory:
  backend: "redis"      # "memory" 或 "redis"
  redis:
    url: "${REDIS_URL:-redis://localhost:6379/0}"
    ttl: 86400

permissions:
  mode: "default"       # default / auto / strict / bypass
  rules:
    - tool_pattern: "bash_*"
      decision: "ask"   # allow / ask / deny

context:
  max_tokens: 128000
  strategy: "hybrid"    # summarize / sliding_window / hybrid / trim_tools

retry:
  max_retries: 3
  exponential_base: 2.0
  jitter: true

middleware:
  rate_limit:
    max_requests: 60
    window_seconds: 60
```

---

## Docker 部署

### 单容器部署

```bash
# 构建镜像
docker build -t agent:latest .

# 运行
docker run -d \
  --name agent \
  -p 8000:8000 \
  -e OPENAI_API_KEY="sk-..." \
  -e REDIS_URL="redis://host.docker.internal:6379/0" \
  agent:latest
```

### Docker Compose（推荐）

```bash
# 启动 Agent + Redis
docker compose up -d

# 查看日志
docker compose logs -f agent

# 停止
docker compose down
```

`docker-compose.yaml` 包含：
- **agent** — 应用服务（多阶段构建，非 root 用户，健康检查）
- **redis** — 会话存储（持久化，内存限制 256MB，LRU 淘汰策略）

### 生产部署建议

```bash
# 资源限制
deploy:
  resources:
    limits:
      memory: 2G
      cpus: "2.0"

# 健康检查
healthcheck:
  test: ["CMD", "python", "-c", "import httpx; r = httpx.get('http://localhost:8000/health'); assert r.status_code == 200"]
  interval: 30s
  timeout: 10s
  retries: 3
```

---

## 开发指南

### 运行测试

```bash
# 安装开发依赖
pip install -e ".[all,dev]"

# 运行全部测试 (161 个)
pytest tests/ -v

# 运行并生成覆盖率报告
pytest tests/ --cov=agent --cov-report=html

# 只运行特定模块测试
pytest tests/test_algorithms.py -v
pytest tests/test_tools.py -v
```

### 代码规范

```bash
# Lint 检查 (Ruff)
ruff check agent/ tests/

# 自动格式化
ruff format agent/ tests/

# 类型检查 (MyPy)
mypy agent/
```

### 项目规范

- **Python 版本**: 3.10+
- **代码风格**: Ruff (行宽 100)
- **类型检查**: MyPy (strict=false)
- **测试框架**: pytest + pytest-asyncio
- **异步模式**: asyncio_mode = "auto"

### 添加新工具

```python
from pydantic import BaseModel, Field
from agent.tools import create_tool, tool_registry

class MyToolInput(BaseModel):
    """工具输入参数"""
    query: str = Field(description="查询内容")

def my_tool(query: str) -> str:
    """工具实现"""
    return f"结果: {query}"

# 创建并注册
my_tool_instance = create_tool(
    name="my_tool",
    description="我的自定义工具",
    func=my_tool,
    args_schema=MyToolInput,
)
tool_registry.register(my_tool_instance, category="custom", tags=["custom"])
```

### 添加新技能

```yaml
# agent/skills/presets/my_skill.yaml
name: my_skill
description: "我的自定义技能"
version: "1.0.0"

system_prompt: |
  你是一个专业的 XXX 专家。
  你的职责是...

tools:
  - file_read
  - file_write
  - bash_execute

rules:
  - 始终检查文件是否存在再操作
  - 输出结果要包含文件路径和行号
  - 修改前先备份

tags:
  - custom
  - expert
```

---

## 对比其他工具

| 特性 | **Agent** | Claude Code | Codex CLI | OpenClaw | DeepSeek-TUI |
|------|-----------|-------------|-----------|----------|--------------|
| 语言 | Python | TypeScript | Rust | Go | Python |
| 框架基础 | LangGraph | 自研 | 自研 | LangChain | 自研 |
| 多 LLM 支持 | ✅ OpenAI + Anthropic | ❌ 仅 Claude | ✅ OpenAI | ✅ 多模型 | ✅ DeepSeek |
| 工具数量 | 20 | ~15 | ~10 | ~12 | ~8 |
| 技能系统 | ✅ YAML 定义 | ❌ | ❌ | ✅ 插件 | ❌ |
| 预制 Agent | ✅ 12 个 | ❌ | ❌ | ✅ | ❌ |
| 多 Agent 协调 | ✅ Coordinator | ❌ 单 Agent | ❌ | ✅ | ❌ |
| REST API | ✅ FastAPI | ❌ | ❌ | ✅ | ❌ |
| Telegram Bot | ✅ | ❌ | ❌ | ❌ | ❌ |
| 流式响应 | ✅ SSE | ✅ | ✅ | ✅ | ✅ |
| 权限系统 | ✅ 工具级 | ✅ | ✅ 沙箱 | ⚠️ 基础 | ❌ |
| 上下文压缩 | ✅ 6种策略 | ✅ | ⚠️ 基础 | ⚠️ 基础 | ⚠️ 基础 |
| 会话持久化 | ✅ Redis | ❌ 内存 | ❌ | ✅ | ❌ |
| Docker 部署 | ✅ 多阶段 | ❌ | ❌ | ✅ | ❌ |
| 开源协议 | MIT | 商业 | Apache 2.0 | Apache 2.0 | MIT |
| 核心算法 | 6 个 | 未公开 | 未公开 | 未知 | 未知 |
| 可扩展性 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| 适用场景 | 框架集成/私有化 | 个人终端 | 个人终端 | 框架集成 | 个人终端 |

---

## 统计数据

```
📦 项目规模
├── Python 源文件:    37 个
├── 框架代码:         13,532 行
├── 单元测试:         161 个
├── 工具:             20 个
├── 技能包:           11 个
├── 预制 Agent:       12 个
└── 核心算法:         6 个
```

---

## License

[MIT License](LICENSE) - 可自由用于商业和个人项目。

```
MIT License

Copyright (c) 2024 Agent Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
