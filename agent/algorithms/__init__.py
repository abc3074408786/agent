"""
Algorithms - Claude Code 核心算法实现

包含:
- token_estimator: 高级 Token 估算 (文件类型感知, 混合策略)
- cache: Stale-While-Revalidate + LRU + Cold-miss 去重
- priority_queue: 优先级消息队列
- streaming_executor: 流式工具并行执行器
- advanced_retry: 持久重试 + 模型降级 + 上下文溢出恢复
- context_compaction: API轮次分组 + PTL恢复 + Micro-compact
"""

from agent.algorithms.token_estimator import (
    HybridTokenEstimator,
    rough_token_count,
    rough_token_count_for_file,
    estimate_message_tokens,
    estimate_messages_tokens,
    parse_token_budget,
    bytes_per_token_for_file_type,
)

from agent.algorithms.cache import (
    SWRCache,
    LRUCache,
    AsyncDeduplicatedCache,
    swr_cached,
    lru_cached,
)

from agent.algorithms.priority_queue import (
    Priority,
    QueueItem,
    PriorityMessageQueue,
)

from agent.algorithms.streaming_executor import (
    StreamingToolExecutor,
    ToolExecutionState,
    ToolCallAccumulator,
)

from agent.algorithms.advanced_retry import (
    AdvancedRetryExecutor,
    RetryMode,
    QuerySource,
    RetryDecision,
    calculate_backoff_delay,
    with_advanced_retry,
)

from agent.algorithms.context_compaction import (
    group_messages_by_api_round,
    truncate_head_for_ptl,
    micro_compact,
    MicroCompactConfig,
    AutoCompactor,
)

__all__ = [
    # Token 估算
    "HybridTokenEstimator",
    "rough_token_count",
    "rough_token_count_for_file",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "parse_token_budget",
    "bytes_per_token_for_file_type",
    # 缓存
    "SWRCache",
    "LRUCache",
    "AsyncDeduplicatedCache",
    "swr_cached",
    "lru_cached",
    # 优先级队列
    "Priority",
    "QueueItem",
    "PriorityMessageQueue",
    # 流式执行器
    "StreamingToolExecutor",
    "ToolExecutionState",
    "ToolCallAccumulator",
    # 高级重试
    "AdvancedRetryExecutor",
    "RetryMode",
    "QuerySource",
    "RetryDecision",
    "calculate_backoff_delay",
    "with_advanced_retry",
    # 上下文压缩
    "group_messages_by_api_round",
    "truncate_head_for_ptl",
    "micro_compact",
    "MicroCompactConfig",
    "AutoCompactor",
]
