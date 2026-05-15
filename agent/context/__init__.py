"""
Context Management - 上下文压缩和 Token 管理

参考 Claude Code 的 Auto-Compact 机制:
- Token 计数追踪
- 自动上下文压缩
- 消息摘要生成
- 滑动窗口策略
- 上下文预算管理
"""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from agent.observability import get_logger, get_tracer

logger = get_logger("context")
tracer = get_tracer("context")


# ============ Token 估算 ============

class TokenEstimator:
    """
    Token 估算器

    支持多种估算方式:
    - 粗略估算 (字符数/4)
    - tiktoken (如果可用)
    """

    def __init__(self, model: str = "gpt-4"):
        self._model = model
        self._encoder = None
        self._try_load_tiktoken()

    def _try_load_tiktoken(self) -> None:
        try:
            import tiktoken
            self._encoder = tiktoken.encoding_for_model(self._model)
        except (ImportError, KeyError):
            self._encoder = None
            logger.debug("tiktoken not available, using rough estimation")

    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数"""
        if self._encoder:
            return len(self._encoder.encode(text))
        # 粗略估算: 英文约 4 字符/token, 中文约 2 字符/token
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return chinese_chars + (other_chars // 4)

    def count_message_tokens(self, message: BaseMessage) -> int:
        """计算消息的 token 数"""
        tokens = 4  # 消息开销
        content = message.content if isinstance(message.content, str) else json.dumps(message.content)
        tokens += self.count_tokens(content)

        # 工具调用的额外 token
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                tokens += self.count_tokens(tc.get("name", ""))
                tokens += self.count_tokens(json.dumps(tc.get("args", {})))

        return tokens

    def count_messages_tokens(self, messages: List[BaseMessage]) -> int:
        """计算消息列表的 token 数"""
        total = 3  # 对话开销
        for msg in messages:
            total += self.count_message_tokens(msg)
        return total


# ============ 压缩策略 ============

class CompactionStrategy(str, Enum):
    """压缩策略"""
    SUMMARIZE = "summarize"          # 用 LLM 生成摘要
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口，保留最近消息
    HYBRID = "hybrid"                 # 混合: 摘要 + 滑动窗口
    TRIM_TOOLS = "trim_tools"         # 修剪工具结果


@dataclass
class CompactionConfig:
    """压缩配置"""
    max_tokens: int = 128000           # 最大 token 数
    target_tokens: int = 80000         # 压缩目标 token 数
    warning_threshold: float = 0.8     # 警告阈值 (80% 时警告)
    compact_threshold: float = 0.9     # 自动压缩阈值 (90% 时压缩)
    strategy: CompactionStrategy = CompactionStrategy.HYBRID
    # 保留设置
    keep_system_messages: bool = True  # 始终保留系统消息
    keep_recent_messages: int = 10    # 保留最近 N 条消息
    max_tool_result_length: int = 2000  # 工具结果最大长度
    # 摘要设置
    summary_max_tokens: int = 500     # 摘要最大 token 数


@dataclass
class CompactionResult:
    """压缩结果"""
    original_tokens: int
    compacted_tokens: int
    messages_removed: int
    messages_remaining: int
    summary: Optional[str] = None
    strategy_used: CompactionStrategy = CompactionStrategy.HYBRID

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.compacted_tokens

    @property
    def compression_ratio(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return 1 - (self.compacted_tokens / self.original_tokens)


# ============ 上下文压缩器 ============

class ContextCompactor:
    """
    上下文压缩器

    支持多种压缩策略，自动管理上下文窗口
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        config: Optional[CompactionConfig] = None,
        estimator: Optional[TokenEstimator] = None,
    ):
        self._llm = llm
        self._config = config or CompactionConfig()
        self._estimator = estimator or TokenEstimator()
        self._compaction_count = 0

    @property
    def config(self) -> CompactionConfig:
        return self._config

    def get_token_count(self, messages: List[BaseMessage]) -> int:
        """获取消息的 token 数"""
        return self._estimator.count_messages_tokens(messages)

    def should_compact(self, messages: List[BaseMessage]) -> bool:
        """检查是否需要压缩"""
        current_tokens = self.get_token_count(messages)
        threshold = self._config.max_tokens * self._config.compact_threshold
        return current_tokens >= threshold

    def get_warning_state(self, messages: List[BaseMessage]) -> Optional[str]:
        """获取警告状态"""
        current_tokens = self.get_token_count(messages)
        ratio = current_tokens / self._config.max_tokens

        if ratio >= self._config.compact_threshold:
            return "critical"
        elif ratio >= self._config.warning_threshold:
            return "warning"
        return None

    @tracer.trace("context.compact")
    async def compact(
        self,
        messages: List[BaseMessage],
        strategy: Optional[CompactionStrategy] = None,
    ) -> Tuple[List[BaseMessage], CompactionResult]:
        """
        执行压缩

        Args:
            messages: 消息列表
            strategy: 覆盖默认策略

        Returns:
            (压缩后的消息列表, 压缩结果)
        """
        strategy = strategy or self._config.strategy
        original_tokens = self.get_token_count(messages)

        logger.info(
            f"Starting context compaction",
            strategy=strategy.value,
            original_tokens=original_tokens,
            target_tokens=self._config.target_tokens,
        )

        if strategy == CompactionStrategy.SUMMARIZE:
            result_messages = await self._compact_summarize(messages)
        elif strategy == CompactionStrategy.SLIDING_WINDOW:
            result_messages = self._compact_sliding_window(messages)
        elif strategy == CompactionStrategy.TRIM_TOOLS:
            result_messages = self._compact_trim_tools(messages)
        else:  # HYBRID
            result_messages = await self._compact_hybrid(messages)

        compacted_tokens = self.get_token_count(result_messages)
        self._compaction_count += 1

        result = CompactionResult(
            original_tokens=original_tokens,
            compacted_tokens=compacted_tokens,
            messages_removed=len(messages) - len(result_messages),
            messages_remaining=len(result_messages),
            strategy_used=strategy,
        )

        logger.info(
            f"Compaction complete",
            tokens_saved=result.tokens_saved,
            compression_ratio=f"{result.compression_ratio:.1%}",
            messages_removed=result.messages_removed,
        )

        return result_messages, result

    def _compact_sliding_window(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """滑动窗口压缩"""
        keep_recent = self._config.keep_recent_messages
        result = []

        # 保留系统消息
        if self._config.keep_system_messages:
            system_messages = [m for m in messages if isinstance(m, SystemMessage)]
            result.extend(system_messages)

        # 保留最近 N 条消息
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        recent = non_system[-keep_recent:] if len(non_system) > keep_recent else non_system

        # 添加压缩标记
        if len(non_system) > keep_recent:
            removed_count = len(non_system) - keep_recent
            result.append(SystemMessage(
                content=f"[上下文压缩: 已移除 {removed_count} 条历史消息以节省 token]"
            ))

        result.extend(recent)
        return result

    def _compact_trim_tools(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """修剪工具结果"""
        max_len = self._config.max_tool_result_length
        result = []

        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
                if len(content) > max_len:
                    trimmed = content[:max_len] + f"\n... [已截断，原始长度: {len(content)} 字符]"
                    result.append(ToolMessage(
                        content=trimmed,
                        tool_call_id=msg.tool_call_id,
                    ))
                else:
                    result.append(msg)
            else:
                result.append(msg)

        return result

    async def _compact_summarize(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """摘要压缩"""
        if not self._llm:
            logger.warning("No LLM available for summarization, falling back to sliding window")
            return self._compact_sliding_window(messages)

        result = []

        # 保留系统消息
        if self._config.keep_system_messages:
            system_messages = [m for m in messages if isinstance(m, SystemMessage)]
            result.extend(system_messages)

        # 分离要摘要的和要保留的
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        keep_recent = self._config.keep_recent_messages
        to_summarize = non_system[:-keep_recent] if len(non_system) > keep_recent else []
        to_keep = non_system[-keep_recent:] if len(non_system) > keep_recent else non_system

        if to_summarize:
            # 生成摘要
            summary = await self._generate_summary(to_summarize)
            result.append(SystemMessage(
                content=f"[对话摘要]\n{summary}\n[摘要结束 - 以下是最近的对话]"
            ))

        result.extend(to_keep)
        return result

    async def _compact_hybrid(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """混合压缩: 先修剪工具结果，不够则摘要"""
        # 第一步: 修剪工具结果
        trimmed = self._compact_trim_tools(messages)
        current_tokens = self.get_token_count(trimmed)

        if current_tokens <= self._config.target_tokens:
            return trimmed

        # 第二步: 摘要压缩
        return await self._compact_summarize(trimmed)

    async def _generate_summary(self, messages: List[BaseMessage]) -> str:
        """用 LLM 生成对话摘要"""
        # 构建摘要请求
        conversation_text = ""
        for msg in messages:
            role = msg.__class__.__name__.replace("Message", "")
            content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "..."
            conversation_text += f"[{role}]: {content}\n"

        summary_prompt = f"""请用简洁的中文总结以下对话的关键信息。保留:
- 用户的主要需求和意图
- 做出的关键决策
- 重要的事实和数据
- 当前任务的进展状态

对话内容:
{conversation_text}

请在 {self._config.summary_max_tokens} tokens 内完成摘要:"""

        try:
            response = await self._llm.ainvoke([HumanMessage(content=summary_prompt)])
            return response.content
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"[摘要生成失败，保留最近 {self._config.keep_recent_messages} 条消息]"


# ============ 上下文管理器 ============

class ContextManager:
    """
    上下文管理器 - 统一管理对话上下文

    负责:
    - 消息存储和管理
    - 自动触发压缩
    - Token 预算追踪
    - 上下文窗口优化
    """

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        config: Optional[CompactionConfig] = None,
    ):
        self._compactor = ContextCompactor(llm=llm, config=config)
        self._messages: List[BaseMessage] = []
        self._compaction_history: List[CompactionResult] = []
        self._auto_compact_enabled = True

    @property
    def messages(self) -> List[BaseMessage]:
        return self._messages.copy()

    @property
    def token_count(self) -> int:
        return self._compactor.get_token_count(self._messages)

    @property
    def compaction_count(self) -> int:
        return len(self._compaction_history)

    def add_message(self, message: BaseMessage) -> None:
        """添加消息"""
        self._messages.append(message)

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """批量添加消息"""
        self._messages.extend(messages)

    def set_messages(self, messages: List[BaseMessage]) -> None:
        """设置消息 (替换)"""
        self._messages = list(messages)

    async def check_and_compact(self) -> Optional[CompactionResult]:
        """检查并自动压缩"""
        if not self._auto_compact_enabled:
            return None

        if self._compactor.should_compact(self._messages):
            self._messages, result = await self._compactor.compact(self._messages)
            self._compaction_history.append(result)
            return result

        return None

    async def force_compact(
        self, strategy: Optional[CompactionStrategy] = None
    ) -> CompactionResult:
        """强制压缩"""
        self._messages, result = await self._compactor.compact(
            self._messages, strategy=strategy
        )
        self._compaction_history.append(result)
        return result

    def get_status(self) -> Dict[str, Any]:
        """获取上下文状态"""
        config = self._compactor.config
        current_tokens = self.token_count
        return {
            "current_tokens": current_tokens,
            "max_tokens": config.max_tokens,
            "usage_ratio": current_tokens / config.max_tokens if config.max_tokens > 0 else 0,
            "message_count": len(self._messages),
            "warning_state": self._compactor.get_warning_state(self._messages),
            "compaction_count": self.compaction_count,
            "auto_compact_enabled": self._auto_compact_enabled,
        }

    def enable_auto_compact(self, enabled: bool = True) -> None:
        """启用/禁用自动压缩"""
        self._auto_compact_enabled = enabled

    def clear(self) -> None:
        """清除所有消息"""
        self._messages.clear()


# ============ 便捷函数 ============

def create_context_manager(
    llm: Optional[BaseChatModel] = None,
    max_tokens: int = 128000,
    strategy: CompactionStrategy = CompactionStrategy.HYBRID,
) -> ContextManager:
    """创建上下文管理器"""
    config = CompactionConfig(
        max_tokens=max_tokens,
        target_tokens=int(max_tokens * 0.6),
        strategy=strategy,
    )
    return ContextManager(llm=llm, config=config)


__all__ = [
    # 类
    "TokenEstimator",
    "ContextCompactor",
    "ContextManager",
    # 配置
    "CompactionConfig",
    "CompactionResult",
    "CompactionStrategy",
    # 便捷函数
    "create_context_manager",
]
