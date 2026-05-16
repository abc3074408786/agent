# Changelog

## [0.2.0] - 2026-05-16

### Added
- **核心模块**: observability, llm, memory, tools, graph
- **生产级模块**: permissions, streaming, coordinator, context, middleware, retry, hooks, api
- **算法模块**: token_estimator, cache, priority_queue, streaming_executor, advanced_retry, context_compaction
- **工具** (20 个): 文件操作, Bash, Git, GitHub, HTTP, 计算器, 文本处理
- **技能系统**: 11 个 YAML 预制技能包
- **预制 Agent**: 12 个专业 Agent 模板
- **代码图谱**: AST 分析 + 调用图 + 影响分析
- **自动测试闭环**: 改代码→跑测试→失败自动修→再跑
- **CLI**: 终端 REPL (/help /tools /skills /cost /clear /exit)
- **API**: FastAPI REST + SSE 流式
- **Telegram Bot**: 多用户会话隔离 + 速率限制
- **对话持久化**: JSON 文件存储 (/save /resume /sessions)
- **插件系统**: Plugin 基类 + PluginManager + 目录加载
- **RAG**: TF-IDF 向量存储 + 文档检索
- **Docker**: 多阶段构建 + docker-compose (Agent + Redis)
- **测试**: 223 个用例 (单元 + 集成 + 端到端)

## [0.1.0] - 2026-05-15

### Added
- 项目初始化
- 基础配置管理 (YAML + 环境变量替换)
- 数据模型 (Pydantic v2)
- LangGraph 状态定义
