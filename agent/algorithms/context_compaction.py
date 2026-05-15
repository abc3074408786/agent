"""
高级上下文压缩 - 参考 Claude Code 的 compact/ 模块

特性:
- API 轮次分组 (按 assistant message.id 边界)
- PTL (Prompt-Too-Long) 恢复: 逐组丢弃最老消息
- Micro-compact: 只清理旧工具结果，保留缓存前缀
- 断路器: 连续失败后停止重试
- 工具结果大小限制
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from agent.observability import get_logger
from agent.algorithms.token_estimator import estimate_message_tokens, estimate_messages_tokens

logger = get_logger("context_compaction")


# ============ 常量 ============

AUTOCOMPACT_BUFFER_TOKENS = 13_000
MAX_CONSECUTIVE_FAILURES = 3
MAX_TOOL_RESULT_CHARS = 5000  # Micro-compact 阈值
CLEARED_MESSAGE = "[Old tool result content cleared]"


# ============ API 轮次分组 ============

def group_messages_by_api_round(messages: List[BaseMessage]) -> List[List[BaseMessage]]:
    """
    按 API 轮次分组消息
    
    参考 Claude Code: groupMessagesByApiRound()
    
    边界条件: 当新的 AIMessage 出现时开始新的组
    (同一个 API 调用的流式 chunks 有相同的 id)
    """
    groups: List[List[BaseMessage]] = []
    current: List[BaseMessage] = []
    last_ai_id: Optional[str] = None

    for msg in messages:
        # 检测新的 AI 响应 (新的轮次边界)
        if isinstance(msg, AIMessage):
            msg_id = getattr(msg, "id", None) or id(msg)
            if msg_id != last_ai_id and current:
                groups.append(current)
                current = [msg]
            else:
                current.append(msg)
            last_ai_id = msg_id
        else:
            current.append(msg)

    if current:
        groups.append(current)

    return groups


# ============ PTL 恢复 ============

def truncate_head_for_ptl(
    messages: List[BaseMessage],
    token_gap: Optional[int] = None,
    drop_percentage: float = 0.2,
) -> Optional[List[BaseMessage]]:
    """
    PTL (Prompt-Too-Long) 恢复
    
    参考 Claude Code: truncateHeadForPTLRetry()
    
    策略:
    1. 如果知道 token gap，逐组丢弃直到覆盖
    2. 如果不知道，丢弃 20% 的组
    3. 始终保留系统消息和最后一组
    
    Args:
        messages: 消息列表
        token_gap: 需要释放的 token 数 (None = 用百分比)
        drop_percentage: 未知 gap 时丢弃的百分比
        
    Returns:
        压缩后的消息列表，或 None (无法压缩)
    """
    groups = group_messages_by_api_round(messages)

    if len(groups) < 2:
        return None  # 至少需要 2 组才能丢弃

    if token_gap:
        # 精确丢弃: 逐组丢弃直到覆盖 gap
        tokens_freed = 0
        drop_count = 0

        for i, group in enumerate(groups[:-1]):  # 不丢弃最后一组
            group_tokens = sum(estimate_message_tokens(m) for m in group)
            tokens_freed += group_tokens
            drop_count += 1

            if tokens_freed >= token_gap:
                break
    else:
        # 百分比丢弃
        drop_count = max(1, int(len(groups) * drop_percentage))
        # 不能丢弃最后一组
        drop_count = min(drop_count, len(groups) - 1)

    if drop_count == 0:
        return None

    # 保留的组
    remaining_groups = groups[drop_count:]

    # 构建结果
    result: List[BaseMessage] = []

    # 保留系统消息 (始终在最前面)
    system_messages = [m for m in messages if isinstance(m, SystemMessage)]
    result.extend(system_messages)

    # 添加压缩标记
    removed_msg_count = sum(len(g) for g in groups[:drop_count])
    result.append(SystemMessage(
        content=f"[Context compacted: {removed_msg_count} messages from "
                f"{drop_count} API rounds were removed to fit context window]"
    ))

    # 添加剩余消息 (排除已添加的系统消息)
    for group in remaining_groups:
        for msg in group:
            if not isinstance(msg, SystemMessage):
                result.append(msg)

    logger.info(
        f"PTL recovery: dropped {drop_count} groups ({removed_msg_count} messages)",
        token_gap=token_gap,
    )

    return result


# ============ Micro-Compact ============

@dataclass
class MicroCompactConfig:
    """Micro-compact 配置"""
    max_tool_result_chars: int = MAX_TOOL_RESULT_CHARS
    keep_recent_tool_results: int = 5  # 保留最近 N 个工具结果
    compactable_tools: Optional[set] = None  # 可压缩的工具名 (None=全部)


@dataclass
class MicroCompactResult:
    """Micro-compact 结果"""
    messages: List[BaseMessage]
    cleared_count: int = 0
    tokens_saved_estimate: int = 0


def micro_compact(
    messages: List[BaseMessage],
    config: Optional[MicroCompactConfig] = None,
) -> MicroCompactResult:
    """
    Micro-compact: 清理旧的大工具结果
    
    参考 Claude Code 的 microCompact:
    - 保留最近 N 个工具结果
    - 清理超过阈值的旧工具结果
    - 不改变消息结构，只替换内容
    
    这比完整压缩轻量得多，不失效缓存前缀
    """
    config = config or MicroCompactConfig()
    result_messages = list(messages)
    cleared_count = 0
    tokens_saved = 0

    # 找到所有 ToolMessage 的索引 (从旧到新)
    tool_indices = [
        i for i, m in enumerate(result_messages)
        if isinstance(m, ToolMessage)
    ]

    if len(tool_indices) <= config.keep_recent_tool_results:
        return MicroCompactResult(messages=result_messages)

    # 需要清理的 (排除最近 N 个)
    indices_to_clear = tool_indices[:-config.keep_recent_tool_results]

    for idx in indices_to_clear:
        msg = result_messages[idx]
        if not isinstance(msg, ToolMessage):
            continue

        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)

        # 只清理超过阈值的
        if len(content) > config.max_tool_result_chars:
            old_tokens = estimate_message_tokens(msg)

            # 替换为占位符
            result_messages[idx] = ToolMessage(
                content=CLEARED_MESSAGE,
                tool_call_id=msg.tool_call_id,
            )

            new_tokens = estimate_message_tokens(result_messages[idx])
            tokens_saved += old_tokens - new_tokens
            cleared_count += 1

    if cleared_count > 0:
        logger.info(
            f"Micro-compact cleared {cleared_count} tool results",
            tokens_saved_estimate=tokens_saved,
        )

    return MicroCompactResult(
        messages=result_messages,
        cleared_count=cleared_count,
        tokens_saved_estimate=tokens_saved,
    )


# ============ 带断路器的自动压缩 ============

class AutoCompactor:
    """
    带断路器的自动压缩器
    
    参考 Claude Code:
    - 连续失败 3 次后停止尝试
    - 先尝试 micro-compact，不够则完整压缩
    """

    def __init__(
        self,
        context_window: int = 200000,
        buffer_tokens: int = AUTOCOMPACT_BUFFER_TOKENS,
        max_consecutive_failures: int = MAX_CONSECUTIVE_FAILURES,
    ):
        self._context_window = context_window
        self._buffer = buffer_tokens
        self._max_failures = max_consecutive_failures
        self._consecutive_failures = 0
        self._compaction_count = 0

    @property
    def threshold(self) -> int:
        """压缩触发阈值"""
        return self._context_window - self._buffer

    @property
    def is_circuit_open(self) -> bool:
        """断路器是否打开 (停止重试)"""
        return self._consecutive_failures >= self._max_failures

    def should_compact(self, messages: List[BaseMessage]) -> bool:
        """是否应该触发压缩"""
        if self.is_circuit_open:
            return False
        current_tokens = estimate_messages_tokens(messages)
        return current_tokens >= self.threshold

    def compact(
        self,
        messages: List[BaseMessage],
        micro_compact_config: Optional[MicroCompactConfig] = None,
    ) -> Tuple[List[BaseMessage], bool]:
        """
        执行压缩 (先 micro-compact，不够则 PTL)
        
        Returns:
            (压缩后消息, 是否成功)
        """
        if self.is_circuit_open:
            logger.warning("Auto-compact circuit breaker open, skipping")
            return messages, False

        try:
            # 第一步: Micro-compact
            mc_result = micro_compact(messages, micro_compact_config)
            current_tokens = estimate_messages_tokens(mc_result.messages)

            if current_tokens < self.threshold:
                self._consecutive_failures = 0
                self._compaction_count += 1
                return mc_result.messages, True

            # 第二步: PTL 恢复
            token_gap = current_tokens - self.threshold + self._buffer
            ptl_result = truncate_head_for_ptl(
                mc_result.messages, token_gap=token_gap
            )

            if ptl_result:
                self._consecutive_failures = 0
                self._compaction_count += 1
                return ptl_result, True

            # 失败
            self._consecutive_failures += 1
            logger.warning(
                f"Auto-compact failed",
                consecutive_failures=self._consecutive_failures,
                max=self._max_failures,
            )
            return messages, False

        except Exception as e:
            self._consecutive_failures += 1
            logger.error(f"Auto-compact error: {e}")
            return messages, False

    def reset(self) -> None:
        """重置断路器"""
        self._consecutive_failures = 0


__all__ = [
    # 函数
    "group_messages_by_api_round",
    "truncate_head_for_ptl",
    "micro_compact",
    # 数据类
    "MicroCompactConfig",
    "MicroCompactResult",
    # 类
    "AutoCompactor",
]
