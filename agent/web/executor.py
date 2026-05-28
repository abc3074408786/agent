"""
Team Executor - 团队执行器

负责按照 TaskPlan 执行子任务，发出实时事件
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.web.leader import TaskPlan, SubTask, AgentRole, ROLE_INFO

import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """执行事件类型"""
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_OUTPUT = "task_output"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ALL_COMPLETED = "all_completed"


@dataclass
class ExecutionEvent:
    """执行事件"""
    type: EventType
    task_id: str = ""
    task_title: str = ""
    role: str = ""
    model: str = ""
    message: str = ""
    output: str = ""
    progress: float = 0.0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "task_id": self.task_id,
            "task_title": self.task_title,
            "role": self.role,
            "model": self.model,
            "message": self.message,
            "output": self.output,
            "progress": self.progress,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
        }


class TeamExecutor:
    """
    团队执行器

    按照 TaskPlan 中的依赖关系执行子任务
    - 无依赖的任务并行执行
    - 有依赖的任务等待依赖完成
    - 实时产出执行事件
    """

    def __init__(self, llm=None, model_config: Optional[Dict[str, str]] = None):
        self._llm = llm
        self._model_config = model_config or {}
        self._members = self._init_members()

    def _init_members(self) -> List[Dict[str, Any]]:
        """初始化团队成员信息"""
        members = []
        for role in AgentRole:
            info = ROLE_INFO.get(role, {"icon": "🤖", "label": "Agent", "color": "#666"})
            members.append({
                "role": role.value,
                "icon": info["icon"],
                "label": info["label"],
                "color": info["color"],
                "model": self._model_config.get(role.value, "gpt-4o"),
            })
        return members

    def get_members_info(self) -> List[Dict[str, Any]]:
        return self._members

    async def execute(self, plan: TaskPlan) -> AsyncGenerator[ExecutionEvent, None]:
        """
        执行任务计划，逐步产出事件

        按拓扑顺序执行：
        1. 找出无依赖的任务，并行执行
        2. 完成后找下一批可执行任务
        3. 直到所有任务完成
        """
        completed: Dict[str, str] = {}  # task_id -> output
        failed: set = set()
        all_tasks = {st.id: st for st in plan.subtasks}
        total = len(plan.subtasks)
        done_count = 0

        while done_count < total:
            # 找出当前可执行的任务（依赖已完成且自身未完成）
            ready = []
            for task_id, task in all_tasks.items():
                if task_id in completed or task_id in failed:
                    continue
                deps_met = all(dep in completed for dep in task.depends_on)
                deps_failed = any(dep in failed for dep in task.depends_on)
                if deps_failed:
                    # 依赖失败，标记为失败
                    failed.add(task_id)
                    done_count += 1
                    yield ExecutionEvent(
                        type=EventType.TASK_FAILED,
                        task_id=task_id,
                        task_title=task.title,
                        role=task.role.value,
                        model=task.model,
                        message=f"被阻塞: 依赖任务失败",
                    )
                elif deps_met:
                    ready.append(task)

            if not ready:
                break

            # 并行执行当前批次
            results = await asyncio.gather(
                *[self._execute_single(task, completed) for task in ready],
                return_exceptions=True,
            )

            for task, result in zip(ready, results):
                if isinstance(result, Exception):
                    failed.add(task.id)
                    done_count += 1
                    yield ExecutionEvent(
                        type=EventType.TASK_FAILED,
                        task_id=task.id,
                        task_title=task.title,
                        role=task.role.value,
                        model=task.model,
                        message=f"执行异常: {str(result)}",
                    )
                else:
                    # result 是一系列事件
                    for event in result:
                        yield event
                    completed[task.id] = result[-1].output if result else ""
                    done_count += 1

        # 全部完成
        yield ExecutionEvent(
            type=EventType.ALL_COMPLETED,
            message=f"所有任务已完成 ({len(completed)} 成功, {len(failed)} 失败)",
            progress=1.0,
        )

    async def _execute_single(
        self, task: SubTask, context: Dict[str, str]
    ) -> List[ExecutionEvent]:
        """执行单个子任务"""
        events = []
        start_time = time.perf_counter()

        role_info = ROLE_INFO.get(task.role, {"icon": "🤖", "label": "Agent"})

        # 发出开始事件
        events.append(ExecutionEvent(
            type=EventType.TASK_STARTED,
            task_id=task.id,
            task_title=task.title,
            role=task.role.value,
            model=task.model,
            message=f"{role_info['icon']} {role_info['label']} 开始执行: {task.title}",
        ))

        # 模拟进度
        await asyncio.sleep(0.3)

        events.append(ExecutionEvent(
            type=EventType.TASK_PROGRESS,
            task_id=task.id,
            task_title=task.title,
            role=task.role.value,
            model=task.model,
            progress=0.3,
            message="正在分析需求...",
        ))

        # 执行任务
        if self._llm:
            output = await self._call_llm(task, context)
        else:
            output = await self._mock_execute(task, context)

        await asyncio.sleep(0.2)

        events.append(ExecutionEvent(
            type=EventType.TASK_PROGRESS,
            task_id=task.id,
            task_title=task.title,
            role=task.role.value,
            model=task.model,
            progress=0.9,
            message="正在整理输出...",
        ))

        await asyncio.sleep(0.2)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # 完成事件
        events.append(ExecutionEvent(
            type=EventType.TASK_COMPLETED,
            task_id=task.id,
            task_title=task.title,
            role=task.role.value,
            model=task.model,
            output=output,
            progress=1.0,
            duration_ms=duration_ms,
            message=f"✅ {task.title} 完成 ({duration_ms:.0f}ms)",
        ))

        return events

    async def _call_llm(self, task: SubTask, context: Dict[str, str]) -> str:
        """使用 LLM 执行任务"""
        from langchain_core.messages import HumanMessage, SystemMessage

        role_info = ROLE_INFO.get(task.role, {"label": "Agent"})

        system = f"""你是团队中的 {role_info['label']}。
你的任务: {task.title}
详细描述: {task.description}

请高质量地完成分配给你的工作。输出要简洁、专业。"""

        # 加入前序任务上下文
        context_text = ""
        if context:
            context_text = "\n\n## 前序任务输出:\n"
            for dep_id in task.depends_on:
                if dep_id in context:
                    context_text += f"\n---\n{context[dep_id]}\n"

        prompt = f"{task.description}\n{context_text}"

        try:
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=prompt),
            ]
            response = await self._llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"LLM call failed for task {task.id}: {e}")
            return f"[执行出错: {str(e)}]"

    async def _mock_execute(self, task: SubTask, context: Dict[str, str]) -> str:
        """Mock 执行 (无 LLM 时的演示模式)"""
        # 模拟不同时长
        delays = {
            AgentRole.ARCHITECT: 1.5,
            AgentRole.PYTHON_DEV: 2.0,
            AgentRole.BACKEND_DEV: 2.0,
            AgentRole.FRONTEND_DEV: 1.8,
            AgentRole.TEST_ENGINEER: 1.5,
            AgentRole.SECURITY_AUDITOR: 1.2,
            AgentRole.DEVOPS: 1.0,
            AgentRole.DATABASE_EXPERT: 1.3,
            AgentRole.CODE_REVIEWER: 1.2,
        }
        await asyncio.sleep(delays.get(task.role, 1.5))

        # Mock 输出
        mock_outputs = {
            AgentRole.ARCHITECT: """## 架构设计方案

### 模块划分
1. **API 层** - FastAPI 路由和请求处理
2. **业务逻辑层** - 核心业务逻辑
3. **数据访问层** - 数据库操作和 ORM

### 技术选型
- 框架: FastAPI + Pydantic
- 数据库: PostgreSQL + SQLAlchemy
- 缓存: Redis
- 认证: JWT + bcrypt

### 接口设计
```
POST /api/v1/register  - 用户注册
POST /api/v1/login     - 用户登录
GET  /api/v1/profile   - 获取用户信息
```""",
            AgentRole.PYTHON_DEV: """## 代码实现

```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import jwt

app = FastAPI()
pwd_context = CryptContext(schemes=["bcrypt"])

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

@app.post("/api/v1/register")
async def register(user: UserRegister):
    # 检查邮箱是否已注册
    hashed = pwd_context.hash(user.password)
    # 创建用户并发送验证邮件
    return {"message": "注册成功，请查收验证邮件"}

@app.post("/api/v1/login")
async def login(user: UserLogin):
    # 验证用户
    token = jwt.encode({"sub": user.email}, "secret")
    return {"access_token": token}
```

实现要点:
- 密码使用 bcrypt 加密
- JWT token 用于会话管理
- 邮箱验证使用异步发送""",
            AgentRole.BACKEND_DEV: """## 后端 API 实现

```python
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from email_service import send_verification_email

@app.post("/api/v1/register")
async def register(
    user: UserRegister,
    db: AsyncSession = Depends(get_db),
    bg_tasks: BackgroundTasks = BackgroundTasks()
):
    # 检查重复
    existing = await db.execute(select(User).where(User.email == user.email))
    if existing.scalar():
        raise HTTPException(400, "邮箱已注册")

    # 创建用户
    new_user = User(email=user.email, hashed_password=hash_pw(user.password))
    db.add(new_user)
    await db.commit()

    # 异步发送验证邮件
    bg_tasks.add_task(send_verification_email, user.email)

    return {"message": "注册成功"}
```""",
            AgentRole.TEST_ENGINEER: """## 测试报告

### 测试用例
| # | 用例 | 状态 |
|---|------|------|
| 1 | 正常注册流程 | ✅ PASSED |
| 2 | 重复邮箱注册 | ✅ PASSED |
| 3 | 无效邮箱格式 | ✅ PASSED |
| 4 | 密码强度验证 | ✅ PASSED |
| 5 | 登录正常流程 | ✅ PASSED |
| 6 | 错误密码登录 | ✅ PASSED |
| 7 | Token 验证 | ✅ PASSED |

### 结果
- 通过: 7/7 (100%)
- 覆盖率: 92%
- all tests passed""",
            AgentRole.SECURITY_AUDITOR: """## 安全审计报告

### 检查项目
| 检查项 | 状态 | 说明 |
|--------|------|------|
| 密码存储 | ✅ 安全 | 使用 bcrypt 哈希 |
| SQL 注入 | ✅ 安全 | 使用 ORM 参数化查询 |
| JWT 配置 | ⚠️ 建议 | 建议设置过期时间 |
| CORS | ✅ 安全 | 已配置白名单 |
| 速率限制 | ⚠️ 建议 | 建议添加登录频率限制 |

### 建议
1. JWT token 添加 exp 过期时间 (建议 24h)
2. 添加登录失败次数限制 (5次/小时)
3. 注册接口添加验证码防刷

### 总结
未发现严重安全问题，建议修复上述2个中等级别问题。""",
            AgentRole.DEVOPS: """## 部署配置

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - postgres
      - redis
  postgres:
    image: postgres:15
  redis:
    image: redis:7
```""",
            AgentRole.DATABASE_EXPERT: """## 数据模型设计

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE email_verifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_verifications_token ON email_verifications(token);
```""",
            AgentRole.CODE_REVIEWER: """## 代码审查结果

### 总体评价: 👍 LGTM

### 优点
- 结构清晰，职责分离合理
- 使用了类型注解和 Pydantic 验证
- 异步处理邮件发送

### 建议 (非阻塞)
1. 建议添加 logging
2. 错误处理可以更细粒度
3. 配置项建议抽取到环境变量

### 结论
代码质量良好，建议合并。""",
            AgentRole.FRONTEND_DEV: """## 前端实现

```jsx
// RegisterForm.tsx
import { useState } from 'react'

export function RegisterForm() {
  const [form, setForm] = useState({ email: '', password: '', username: '' })
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    const res = await fetch('/api/v1/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form)
    })
    // 处理响应...
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit}>
      <input placeholder="邮箱" type="email" required />
      <input placeholder="用户名" required />
      <input placeholder="密码" type="password" required />
      <button disabled={loading}>注册</button>
    </form>
  )
}
```""",
        }

        return mock_outputs.get(task.role, f"[{task.title}] 已完成")
