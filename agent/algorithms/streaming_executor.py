"""
流式工具并行执行器 - 参考 Claude Code 的 StreamingToolExecutor

核心思想:
- 在 LLM 流式输出工具调用时，不等待整个响应完成
- 一旦收到完整的 tool_call，立即开始并行执行
- 支持多个工具调用并发执行
- 结果按原始顺序收集
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from agent.observability import get_logger, get_tracer

logger = get_logger("streaming_executor")
tracer = get_tracer("streaming_executor")


class ToolExecutionState(str, Enum):
    """工具执行状态"""
    PENDING = "pending"         # 等待参数完成
    READY = "ready"             # 参数已完成，准备执行
    RUNNING = "running"         # 执行中
    COMPLETED = "completed"     # 完成
    FAILED = "failed"           # 失败


@dataclass
class ToolCallAccumulator:
    """工具调用累加器 - 累积流式 tool_call chunks"""
    index: int
    tool_call_id: str = ""
    name: str = ""
    args_buffer: str = ""
    state: ToolExecutionState = ToolExecutionState.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    task: Optional[asyncio.Task] = None

    @property
    def is_name_complete(self) -> bool:
        return bool(self.name)

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0


class StreamingToolExecutor:
    """
    流式工具并行执行器
    
    参考 Claude Code 的 StreamingToolExecutor:
    - LLM 流式输出时，实时解析 tool_call chunks
    - tool_call 参数完成后立即开始执行（不等待其他 tool_calls）
    - 多个工具并发执行
    - 控制最大并发数
    
    使用方式:
        executor = StreamingToolExecutor(tools, max_concurrent=3)
        
        # 在流式处理中调用
        async for chunk in llm.astream(messages):
            if chunk.tool_call_chunks:
                for tc_chunk in chunk.tool_call_chunks:
                    executor.feed_chunk(tc_chunk)
            
            # 检查已完成的结果
            results = executor.collect_completed()
        
        # 等待所有完成
        all_results = await executor.wait_all()
    """

    def __init__(
        self,
        tools: List[BaseTool],
        max_concurrent: int = 5,
        timeout_seconds: float = 60.0,
    ):
        self._tools: Dict[str, BaseTool] = {t.name: t for t in tools}
        self._max_concurrent = max_concurrent
        self._timeout = timeout_seconds
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._accumulators: Dict[int, ToolCallAccumulator] = {}
        self._completed: List[ToolCallAccumulator] = []
        self._running_tasks: Dict[int, asyncio.Task] = {}

    @property
    def active_count(self) -> int:
        """当前执行中的工具数"""
        return sum(
            1 for a in self._accumulators.values()
            if a.state == ToolExecutionState.RUNNING
        )

    @property
    def pending_count(self) -> int:
        """等待参数的工具数"""
        return sum(
            1 for a in self._accumulators.values()
            if a.state == ToolExecutionState.PENDING
        )

    def feed_chunk(self, tool_call_chunk: Dict[str, Any]) -> Optional[str]:
        """
        喂入一个 tool_call chunk
        
        当工具参数完成时 (收到完整 JSON)，自动触发执行
        
        Returns:
            如果触发了新的工具执行，返回工具名称
        """
        index = tool_call_chunk.get("index", 0)

        # 新的 tool_call
        if index not in self._accumulators:
            self._accumulators[index] = ToolCallAccumulator(
                index=index,
                tool_call_id=tool_call_chunk.get("id", f"call_{index}"),
            )

        acc = self._accumulators[index]

        # 累积名称
        name = tool_call_chunk.get("name", "")
        if name:
            acc.name = name

        # 累积参数
        args = tool_call_chunk.get("args", "")
        if args:
            acc.args_buffer += args

        return None  # 流式中不自动触发

    def mark_complete(self, index: int) -> None:
        """标记某个 tool_call 的参数已完成"""
        if index in self._accumulators:
            self._accumulators[index].state = ToolExecutionState.READY

    def mark_all_complete(self) -> None:
        """标记所有 tool_call 参数已完成 (流结束时调用)"""
        for acc in self._accumulators.values():
            if acc.state == ToolExecutionState.PENDING:
                acc.state = ToolExecutionState.READY

    async def execute_ready(self) -> List[str]:
        """
        执行所有准备好的工具 (非阻塞)
        
        Returns:
            已启动执行的工具名称列表
        """
        started = []
        for idx, acc in self._accumulators.items():
            if acc.state == ToolExecutionState.READY:
                acc.state = ToolExecutionState.RUNNING
                acc.start_time = time.perf_counter()
                task = asyncio.create_task(self._execute_tool(acc))
                self._running_tasks[idx] = task
                acc.task = task
                started.append(acc.name)
                logger.debug(f"Started tool execution: {acc.name}", index=idx)

        return started

    async def _execute_tool(self, acc: ToolCallAccumulator) -> None:
        """执行单个工具"""
        async with self._semaphore:
            try:
                tool = self._tools.get(acc.name)
                if not tool:
                    acc.error = f"Tool '{acc.name}' not found"
                    acc.state = ToolExecutionState.FAILED
                    return

                # 解析参数
                import json
                try:
                    args = json.loads(acc.args_buffer) if acc.args_buffer else {}
                except json.JSONDecodeError:
                    args = {"input": acc.args_buffer}

                # 执行 (带超时)
                result = await asyncio.wait_for(
                    self._invoke_tool(tool, args),
                    timeout=self._timeout,
                )

                acc.result = str(result)
                acc.state = ToolExecutionState.COMPLETED

            except asyncio.TimeoutError:
                acc.error = f"Tool '{acc.name}' timed out after {self._timeout}s"
                acc.state = ToolExecutionState.FAILED
            except Exception as e:
                acc.error = f"Tool '{acc.name}' failed: {str(e)}"
                acc.state = ToolExecutionState.FAILED
            finally:
                acc.end_time = time.perf_counter()
                self._completed.append(acc)

    async def _invoke_tool(self, tool: BaseTool, args: Dict[str, Any]) -> Any:
        """调用工具"""
        if asyncio.iscoroutinefunction(tool.ainvoke):
            return await tool.ainvoke(args)
        else:
            return await asyncio.to_thread(tool.invoke, args)

    def collect_completed(self) -> List[ToolMessage]:
        """收集已完成的结果 (按原始顺序)"""
        messages = []
        for acc in sorted(self._completed, key=lambda a: a.index):
            if acc.state == ToolExecutionState.COMPLETED:
                messages.append(ToolMessage(
                    content=acc.result or "",
                    tool_call_id=acc.tool_call_id,
                ))
            elif acc.state == ToolExecutionState.FAILED:
                messages.append(ToolMessage(
                    content=acc.error or "Unknown error",
                    tool_call_id=acc.tool_call_id,
                ))
        self._completed.clear()
        return messages

    async def wait_all(self) -> List[ToolMessage]:
        """等待所有工具执行完成"""
        # 先执行所有 READY 的
        await self.execute_ready()

        # 等待所有任务
        tasks = [t for t in self._running_tasks.values() if not t.done()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        return self.collect_completed()

    def get_results_as_messages(self) -> List[ToolMessage]:
        """获取所有结果为 ToolMessage 列表 (按索引排序)"""
        all_accs = sorted(self._accumulators.values(), key=lambda a: a.index)
        messages = []
        for acc in all_accs:
            if acc.state == ToolExecutionState.COMPLETED:
                messages.append(ToolMessage(
                    content=acc.result or "",
                    tool_call_id=acc.tool_call_id,
                ))
            elif acc.state == ToolExecutionState.FAILED:
                messages.append(ToolMessage(
                    content=acc.error or "Unknown error",
                    tool_call_id=acc.tool_call_id,
                ))
        return messages

    def reset(self) -> None:
        """重置执行器"""
        for task in self._running_tasks.values():
            if not task.done():
                task.cancel()
        self._accumulators.clear()
        self._completed.clear()
        self._running_tasks.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        completed = [a for a in self._accumulators.values() if a.state in (
            ToolExecutionState.COMPLETED, ToolExecutionState.FAILED
        )]
        return {
            "total": len(self._accumulators),
            "completed": sum(1 for a in completed if a.state == ToolExecutionState.COMPLETED),
            "failed": sum(1 for a in completed if a.state == ToolExecutionState.FAILED),
            "running": self.active_count,
            "pending": self.pending_count,
            "total_duration_ms": sum(a.duration_ms for a in completed),
            "avg_duration_ms": (
                sum(a.duration_ms for a in completed) / len(completed)
                if completed else 0
            ),
        }


__all__ = [
    "ToolExecutionState",
    "ToolCallAccumulator",
    "StreamingToolExecutor",
]
