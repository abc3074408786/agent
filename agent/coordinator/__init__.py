"""
Multi-Agent Coordinator - 多Agent协调器

参考 Claude Code 的 Coordinator 模式:
- Coordinator (协调者): 分解任务、派发工作、合成结果
- Worker (工作者): 独立执行子任务
- 并行任务执行
- Worker 间通信
- 任务生命周期管理
"""

import asyncio
import uuid
import time
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool

from agent.observability import get_logger, get_tracer

logger = get_logger("coordinator")
tracer = get_tracer("coordinator")


# ============ 任务状态 ============

class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"         # 等待执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消
    TIMEOUT = "timeout"         # 超时


class WorkerRole(str, Enum):
    """Worker 角色"""
    RESEARCHER = "researcher"       # 研究者: 收集信息
    IMPLEMENTER = "implementer"     # 实现者: 编写代码
    VERIFIER = "verifier"           # 验证者: 测试验证
    GENERAL = "general"             # 通用


# ============ 数据结构 ============

@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    output: Optional[str] = None
    error: Optional[str] = None
    messages: List[BaseMessage] = field(default_factory=list)
    usage: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_notification(self) -> str:
        """转为通知格式 (类似 Claude Code 的 <task-notification>)"""
        parts = [
            f"<task-notification>",
            f"  <task-id>{self.task_id}</task-id>",
            f"  <status>{self.status.value}</status>",
        ]
        if self.output:
            parts.append(f"  <result>{self.output}</result>")
        if self.error:
            parts.append(f"  <error>{self.error}</error>")
        if self.usage:
            parts.append(f"  <usage>")
            for k, v in self.usage.items():
                parts.append(f"    <{k}>{v}</{k}>")
            parts.append(f"  </usage>")
        parts.append(f"  <duration_ms>{self.duration_ms:.0f}</duration_ms>")
        parts.append(f"</task-notification>")
        return "\n".join(parts)


@dataclass
class WorkerTask:
    """Worker 任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    description: str = ""
    prompt: str = ""
    role: WorkerRole = WorkerRole.GENERAL
    tools: Optional[List[BaseTool]] = None
    system_prompt: Optional[str] = None
    max_iterations: int = 10
    timeout_seconds: float = 300.0
    # 依赖
    depends_on: List[str] = field(default_factory=list)
    # 状态
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_complete(self) -> bool:
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT,
        )


@dataclass
class CoordinatorState:
    """协调器状态"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tasks: Dict[str, WorkerTask] = field(default_factory=dict)
    active_workers: Set[str] = field(default_factory=set)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    messages: List[BaseMessage] = field(default_factory=list)
    total_usage: Dict[str, int] = field(default_factory=lambda: {
        "total_tokens": 0,
        "tool_uses": 0,
        "total_duration_ms": 0,
    })


# ============ Worker 执行器 ============

class Worker:
    """
    Worker - 独立执行子任务

    每个 Worker 有独立的:
    - LLM 实例
    - 工具集
    - 上下文
    - 执行循环
    """

    def __init__(
        self,
        worker_id: str,
        llm: BaseChatModel,
        tools: Optional[List[BaseTool]] = None,
        system_prompt: Optional[str] = None,
        max_iterations: int = 10,
    ):
        self.worker_id = worker_id
        self._llm = llm
        self._tools = tools or []
        self._system_prompt = system_prompt or self._default_system_prompt()
        self._max_iterations = max_iterations
        self._messages: List[BaseMessage] = []
        self._is_running = False
        self._cancel_event = asyncio.Event()

        # 如果有工具，绑定到 LLM
        if self._tools:
            self._llm = llm.bind_tools(self._tools)

    def _default_system_prompt(self) -> str:
        return (
            "你是一个专注的工作者。你的任务是完成分配给你的特定工作。\n"
            "- 完成后报告结果\n"
            "- 遇到问题时清晰描述错误\n"
            "- 不要偏离分配的任务\n"
            "- 使用可用的工具来完成工作"
        )

    @tracer.trace("worker.execute")
    async def execute(self, task: WorkerTask) -> TaskResult:
        """执行任务"""
        self._is_running = True
        self._cancel_event.clear()
        start_time = time.perf_counter()

        logger.info(
            f"Worker executing task",
            worker_id=self.worker_id,
            task_id=task.task_id,
            description=task.description,
        )

        try:
            # 构建初始消息
            self._messages = [
                SystemMessage(content=self._system_prompt),
                HumanMessage(content=task.prompt),
            ]

            iteration = 0
            final_content = ""

            while iteration < self._max_iterations:
                if self._cancel_event.is_set():
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.CANCELLED,
                        output="Task was cancelled",
                        duration_ms=(time.perf_counter() - start_time) * 1000,
                    )

                # 超时检查
                elapsed = time.perf_counter() - start_time
                if elapsed > task.timeout_seconds:
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.TIMEOUT,
                        output=final_content or "Task timed out",
                        duration_ms=elapsed * 1000,
                    )

                # 调用 LLM
                response = await self._llm.ainvoke(self._messages)
                self._messages.append(response)

                # 检查是否有工具调用
                if hasattr(response, "tool_calls") and response.tool_calls:
                    # 执行工具
                    tool_results = await self._execute_tools(response.tool_calls)
                    self._messages.extend(tool_results)
                    iteration += 1
                else:
                    # 没有工具调用，任务完成
                    final_content = response.content if response.content else ""
                    break

            duration_ms = (time.perf_counter() - start_time) * 1000

            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                output=final_content,
                messages=self._messages,
                duration_ms=duration_ms,
                usage={
                    "iterations": iteration,
                    "message_count": len(self._messages),
                },
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Worker task failed",
                worker_id=self.worker_id,
                task_id=task.task_id,
                error=str(e),
            )
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                duration_ms=duration_ms,
            )
        finally:
            self._is_running = False

    async def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> List[BaseMessage]:
        """执行工具调用"""
        from langchain_core.messages import ToolMessage

        results = []
        for tc in tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            tool_id = tc.get("id", str(uuid.uuid4()))

            # 查找工具
            tool = next((t for t in self._tools if t.name == tool_name), None)
            if not tool:
                results.append(ToolMessage(
                    content=f"Error: Tool '{tool_name}' not found",
                    tool_call_id=tool_id,
                ))
                continue

            try:
                if asyncio.iscoroutinefunction(tool.invoke):
                    result = await tool.ainvoke(tool_args)
                else:
                    result = await asyncio.to_thread(tool.invoke, tool_args)

                results.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                ))
            except Exception as e:
                results.append(ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                ))

        return results

    def cancel(self) -> None:
        """取消任务"""
        self._cancel_event.set()

    async def send_message(self, message: str) -> TaskResult:
        """向 Worker 发送后续消息 (continue)"""
        self._messages.append(HumanMessage(content=message))
        task = WorkerTask(
            description="Follow-up message",
            prompt=message,
        )
        return await self.execute(task)


# ============ 协调器 ============

class Coordinator:
    """
    多 Agent 协调器

    工作流:
    1. 接收用户任务
    2. 分解为子任务
    3. 创建 Workers 并行执行
    4. 收集结果
    5. 合成最终响应

    并发规则:
    - 只读任务 (研究) → 并行
    - 写入任务 (实现) → 串行或按文件分区并行
    - 验证任务 → 实现完成后并行
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Optional[List[BaseTool]] = None,
        max_concurrent_workers: int = 5,
        worker_timeout: float = 300.0,
        coordinator_system_prompt: Optional[str] = None,
    ):
        self._llm = llm
        self._tools = tools or []
        self._max_concurrent = max_concurrent_workers
        self._worker_timeout = worker_timeout
        self._workers: Dict[str, Worker] = {}
        self._state = CoordinatorState()
        self._semaphore = asyncio.Semaphore(max_concurrent_workers)
        self._system_prompt = coordinator_system_prompt or self._default_coordinator_prompt()

    def _default_coordinator_prompt(self) -> str:
        return """你是一个任务协调者。你的职责是:
1. 分析用户需求并分解为子任务
2. 决定哪些任务可以并行执行
3. 将子任务分配给 Workers
4. 合成 Worker 的结果为最终答案

规则:
- 研究类任务可以并行
- 实现类任务按文件分区并行
- 验证在实现完成后进行
- 始终向 Worker 提供完整的上下文信息"""

    @tracer.trace("coordinator.dispatch")
    async def dispatch(
        self,
        tasks: List[WorkerTask],
        parallel: bool = True,
    ) -> List[TaskResult]:
        """
        派发任务

        Args:
            tasks: 任务列表
            parallel: 是否并行执行（无依赖的任务）
        """
        logger.info(
            f"Dispatching tasks",
            task_count=len(tasks),
            parallel=parallel,
        )

        # 注册任务
        for task in tasks:
            self._state.tasks[task.task_id] = task

        if parallel:
            return await self._execute_parallel(tasks)
        else:
            return await self._execute_sequential(tasks)

    async def _execute_parallel(self, tasks: List[WorkerTask]) -> List[TaskResult]:
        """并行执行任务"""
        # 分离有依赖和无依赖的任务
        independent = [t for t in tasks if not t.depends_on]
        dependent = [t for t in tasks if t.depends_on]

        results: Dict[str, TaskResult] = {}

        # 先执行无依赖的任务
        if independent:
            independent_results = await asyncio.gather(
                *[self._run_worker(task) for task in independent],
                return_exceptions=True,
            )
            for task, result in zip(independent, independent_results):
                if isinstance(result, Exception):
                    results[task.task_id] = TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.FAILED,
                        error=str(result),
                    )
                else:
                    results[task.task_id] = result

        # 然后执行有依赖的任务
        for task in dependent:
            # 检查依赖是否都完成了
            deps_met = all(
                dep_id in results and results[dep_id].status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )
            if deps_met:
                result = await self._run_worker(task)
                results[task.task_id] = result
            else:
                results[task.task_id] = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error="Dependencies not met",
                )

        return list(results.values())

    async def _execute_sequential(self, tasks: List[WorkerTask]) -> List[TaskResult]:
        """串行执行任务"""
        results = []
        for task in tasks:
            result = await self._run_worker(task)
            results.append(result)
            if result.status == TaskStatus.FAILED:
                logger.warning(f"Task failed, stopping sequential execution", task_id=task.task_id)
                # 标记后续任务为取消
                break
        return results

    async def _run_worker(self, task: WorkerTask) -> TaskResult:
        """运行单个 Worker"""
        async with self._semaphore:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now(timezone.utc)
            self._state.active_workers.add(task.task_id)

            # 创建 Worker
            worker = Worker(
                worker_id=task.task_id,
                llm=self._llm,
                tools=task.tools or self._tools,
                system_prompt=task.system_prompt,
                max_iterations=task.max_iterations,
            )
            self._workers[task.task_id] = worker

            try:
                # 执行带超时
                result = await asyncio.wait_for(
                    worker.execute(task),
                    timeout=task.timeout_seconds or self._worker_timeout,
                )
            except asyncio.TimeoutError:
                result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.TIMEOUT,
                    error=f"Task timed out after {task.timeout_seconds}s",
                )
            except Exception as e:
                result = TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.FAILED,
                    error=str(e),
                )

            # 更新状态
            task.status = result.status
            task.result = result
            task.completed_at = datetime.now(timezone.utc)
            self._state.active_workers.discard(task.task_id)

            if result.status == TaskStatus.COMPLETED:
                self._state.completed_tasks.append(task.task_id)
            else:
                self._state.failed_tasks.append(task.task_id)

            # 累积 usage
            if result.usage:
                for key, value in result.usage.items():
                    if key in self._state.total_usage:
                        self._state.total_usage[key] += value if isinstance(value, int) else 0

            logger.info(
                f"Worker completed",
                task_id=task.task_id,
                status=result.status.value,
                duration_ms=result.duration_ms,
            )

            return result

    async def send_message_to_worker(self, task_id: str, message: str) -> Optional[TaskResult]:
        """向现有 Worker 发送消息 (继续执行)"""
        worker = self._workers.get(task_id)
        if not worker:
            logger.warning(f"Worker not found", task_id=task_id)
            return None
        return await worker.send_message(message)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        worker = self._workers.get(task_id)
        if worker:
            worker.cancel()
            task = self._state.tasks.get(task_id)
            if task:
                task.status = TaskStatus.CANCELLED
            return True
        return False

    def cancel_all(self) -> int:
        """取消所有运行中的任务"""
        cancelled = 0
        for task_id, worker in self._workers.items():
            if task_id in self._state.active_workers:
                worker.cancel()
                cancelled += 1
        return cancelled

    def get_state(self) -> CoordinatorState:
        """获取当前状态"""
        return self._state

    def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """获取任务结果"""
        task = self._state.tasks.get(task_id)
        if task:
            return task.result
        return None

    @property
    def active_count(self) -> int:
        return len(self._state.active_workers)

    @property
    def completed_count(self) -> int:
        return len(self._state.completed_tasks)


# ============ 任务分解器 ============

class TaskDecomposer:
    """
    任务分解器 - 使用 LLM 将复杂任务分解为子任务
    """

    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    @tracer.trace("decompose_task")
    async def decompose(
        self,
        user_request: str,
        available_tools: List[str],
        max_subtasks: int = 5,
    ) -> List[WorkerTask]:
        """
        分解用户请求为子任务

        使用 LLM 分析请求并生成结构化的子任务列表
        """
        decompose_prompt = f"""分析以下用户请求，将其分解为可并行执行的子任务。

用户请求: {user_request}

可用工具: {', '.join(available_tools)}

请以 JSON 格式返回子任务列表，每个子任务包含:
- description: 简短描述
- prompt: 给 worker 的详细指令
- role: researcher/implementer/verifier/general
- can_parallel: 是否可以和其他任务并行
- depends_on: 依赖的任务索引列表 (从0开始)

最多 {max_subtasks} 个子任务。返回纯 JSON 数组。"""

        try:
            response = await self._llm.ainvoke([HumanMessage(content=decompose_prompt)])
            content = response.content

            # 解析 JSON
            import json
            # 尝试从 markdown code block 中提取
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            subtasks_data = json.loads(content.strip())

            tasks = []
            for i, st in enumerate(subtasks_data[:max_subtasks]):
                task = WorkerTask(
                    description=st.get("description", f"Subtask {i+1}"),
                    prompt=st.get("prompt", ""),
                    role=WorkerRole(st.get("role", "general")),
                    depends_on=[
                        tasks[dep_idx].task_id
                        for dep_idx in st.get("depends_on", [])
                        if dep_idx < len(tasks)
                    ],
                )
                tasks.append(task)

            return tasks

        except Exception as e:
            logger.warning(f"Task decomposition failed, using single task", error=str(e))
            return [
                WorkerTask(
                    description="Execute user request",
                    prompt=user_request,
                    role=WorkerRole.GENERAL,
                )
            ]


# ============ 便捷函数 ============

def create_coordinator(
    llm: BaseChatModel,
    tools: Optional[List[BaseTool]] = None,
    max_workers: int = 5,
    timeout: float = 300.0,
) -> Coordinator:
    """创建协调器"""
    return Coordinator(
        llm=llm,
        tools=tools,
        max_concurrent_workers=max_workers,
        worker_timeout=timeout,
    )


async def run_parallel_tasks(
    llm: BaseChatModel,
    tasks: List[Dict[str, str]],
    tools: Optional[List[BaseTool]] = None,
) -> List[TaskResult]:
    """
    快速并行执行多个任务

    Args:
        llm: 语言模型
        tasks: [{"description": "...", "prompt": "..."}]
        tools: 工具列表
    """
    coordinator = create_coordinator(llm, tools)
    worker_tasks = [
        WorkerTask(
            description=t.get("description", ""),
            prompt=t.get("prompt", t.get("description", "")),
        )
        for t in tasks
    ]
    return await coordinator.dispatch(worker_tasks, parallel=True)


__all__ = [
    # 枚举
    "TaskStatus",
    "WorkerRole",
    # 数据类
    "TaskResult",
    "WorkerTask",
    "CoordinatorState",
    # 类
    "Worker",
    "Coordinator",
    "TaskDecomposer",
    # 便捷函数
    "create_coordinator",
    "run_parallel_tasks",
]
