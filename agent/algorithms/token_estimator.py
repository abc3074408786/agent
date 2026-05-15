"""
高级 Token 估算器 - 参考 Claude Code 的 tokenEstimation.ts

特性:
- 文件类型感知的 bytes_per_token 比率
- 粗略估算 (快速) + API 精确计数 (准确)
- 混合策略: 最近 API 返回 usage + 新消息粗略估算
- 并行工具调用兄弟检测
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from agent.observability import get_logger

logger = get_logger("token_estimator")


# ============ 文件类型 bytes_per_token 映射 ============

# 参考 Claude Code: JSON 密度高(很多单字符 token)，比率更低
FILE_TYPE_BYTES_PER_TOKEN: Dict[str, float] = {
    # 密集格式 (很多单字符标点 {, }, :, ", 逗号)
    "json": 2.0,
    "jsonl": 2.0,
    "jsonc": 2.0,
    # 标记语言
    "xml": 2.5,
    "html": 2.5,
    "svg": 2.5,
    # 代码 (平均)
    "py": 3.5,
    "ts": 3.5,
    "js": 3.5,
    "tsx": 3.5,
    "jsx": 3.5,
    "java": 3.5,
    "go": 3.5,
    "rs": 3.5,
    "c": 3.5,
    "cpp": 3.5,
    "rb": 3.5,
    # 自然语言 (中文字符约 1.5-2 token/字符)
    "md": 4.0,
    "txt": 4.0,
    "rst": 4.0,
    # YAML/TOML (结构化但不像 JSON 那么密集)
    "yaml": 3.0,
    "yml": 3.0,
    "toml": 3.0,
    # CSS/SCSS
    "css": 3.0,
    "scss": 3.0,
    # 压缩/混淆代码
    "min.js": 2.0,
    "min.css": 2.0,
}

DEFAULT_BYTES_PER_TOKEN = 4.0
CHINESE_CHARS_PER_TOKEN = 1.5  # 中文约 1.5 字符/token


def bytes_per_token_for_file_type(extension: str) -> float:
    """
    获取文件类型的 bytes_per_token 比率
    
    参考 Claude Code: bytesPerTokenForFileType()
    """
    ext = extension.lstrip(".")
    return FILE_TYPE_BYTES_PER_TOKEN.get(ext, DEFAULT_BYTES_PER_TOKEN)


# ============ 粗略估算 ============

def rough_token_count(
    content: str,
    bytes_per_token: float = DEFAULT_BYTES_PER_TOKEN,
) -> int:
    """
    粗略 Token 估算
    
    参考 Claude Code: roughTokenCountEstimation()
    考虑中文字符的特殊处理
    """
    if not content:
        return 0

    # 检测中文字符
    chinese_chars = sum(1 for c in content if '\u4e00' <= c <= '\u9fff')
    other_chars = len(content) - chinese_chars

    # 中文部分用中文比率，其他用通用比率
    chinese_tokens = chinese_chars / CHINESE_CHARS_PER_TOKEN
    other_tokens = other_chars / bytes_per_token

    return max(1, round(chinese_tokens + other_tokens))


def rough_token_count_for_file(content: str, file_path: str) -> int:
    """对文件内容进行类型感知的 Token 估算"""
    # 提取文件扩展名
    ext = ""
    if "." in file_path:
        ext = file_path.rsplit(".", 1)[-1]
        # 处理 .min.js 等
        if file_path.endswith(".min.js"):
            ext = "min.js"
        elif file_path.endswith(".min.css"):
            ext = "min.css"

    bpt = bytes_per_token_for_file_type(ext)
    return rough_token_count(content, bpt)


# ============ 消息 Token 估算 ============

# 消息格式开销 (role + formatting)
MESSAGE_OVERHEAD_TOKENS = 4
CONVERSATION_OVERHEAD_TOKENS = 3
TOOL_CALL_OVERHEAD_TOKENS = 8  # name + id + formatting


def estimate_message_tokens(message: BaseMessage) -> int:
    """
    估算单条消息的 token 数
    
    包含:
    - 消息内容 token
    - 消息格式开销
    - 工具调用 token (如果有)
    """
    tokens = MESSAGE_OVERHEAD_TOKENS

    # 内容
    if isinstance(message.content, str):
        tokens += rough_token_count(message.content)
    elif isinstance(message.content, list):
        # 多模态内容
        for block in message.content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    tokens += rough_token_count(block.get("text", ""))
                elif block.get("type") == "image":
                    tokens += 1000  # 图片固定估算
                elif block.get("type") == "tool_result":
                    content = block.get("content", "")
                    if isinstance(content, str):
                        tokens += rough_token_count(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get("type") == "text":
                                tokens += rough_token_count(item.get("text", ""))
            elif isinstance(block, str):
                tokens += rough_token_count(block)

    # 工具调用
    if hasattr(message, "tool_calls") and message.tool_calls:
        for tc in message.tool_calls:
            tokens += TOOL_CALL_OVERHEAD_TOKENS
            tokens += rough_token_count(tc.get("name", ""))
            args = tc.get("args", {})
            if isinstance(args, dict):
                tokens += rough_token_count(json.dumps(args, ensure_ascii=False))
            elif isinstance(args, str):
                tokens += rough_token_count(args)

    # ToolMessage 的 tool_call_id
    if isinstance(message, ToolMessage):
        tokens += 4  # tool_call_id overhead

    return tokens


def estimate_messages_tokens(messages: List[BaseMessage]) -> int:
    """
    估算消息列表的总 token 数
    
    参考 Claude Code: tokenCountWithEstimation()
    """
    total = CONVERSATION_OVERHEAD_TOKENS
    for msg in messages:
        total += estimate_message_tokens(msg)
    return total


# ============ 混合估算器 ============

@dataclass
class UsageSnapshot:
    """API 返回的 usage 快照"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_tokens: int = 0
    message_index: int = -1  # 对应的消息索引


class HybridTokenEstimator:
    """
    混合 Token 估算器
    
    策略 (参考 Claude Code 的 tokenCountWithEstimation):
    1. 使用最近一次 API 响应的实际 usage 作为基准
    2. 对基准之后的新消息使用粗略估算
    3. 两者相加得到当前估算
    
    这样既有 API 的准确性，又有本地估算的即时性
    """

    def __init__(self, context_window: int = 200000):
        self._context_window = context_window
        self._last_usage: Optional[UsageSnapshot] = None
        self._tiktoken_encoder = None
        self._try_load_tiktoken()

    def _try_load_tiktoken(self) -> None:
        try:
            import tiktoken
            self._tiktoken_encoder = tiktoken.encoding_for_model("gpt-4")
        except (ImportError, KeyError):
            pass

    def count_tokens_precise(self, text: str) -> int:
        """精确计数 (如果 tiktoken 可用)"""
        if self._tiktoken_encoder:
            return len(self._tiktoken_encoder.encode(text))
        return rough_token_count(text)

    def update_usage(self, usage: Dict[str, int], message_index: int) -> None:
        """
        从 API 响应更新 usage 快照
        
        每次收到 API 响应时调用，更新基准
        """
        self._last_usage = UsageSnapshot(
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            message_index=message_index,
        )

    def estimate_current_tokens(self, messages: List[BaseMessage]) -> int:
        """
        混合估算当前总 token 数
        
        如果有 API usage 快照:
          total = last_api_input_tokens + estimate(new_messages_since_snapshot)
        否则:
          total = rough_estimate(all_messages)
        """
        if self._last_usage and self._last_usage.message_index >= 0:
            # 基准: API 返回的 input_tokens (包含了到该点的所有上下文)
            base_tokens = self._last_usage.input_tokens + self._last_usage.output_tokens

            # 新消息: 基准之后的消息
            new_messages = messages[self._last_usage.message_index + 1:]
            new_tokens = sum(estimate_message_tokens(m) for m in new_messages)

            return base_tokens + new_tokens
        else:
            # 纯粗略估算
            return estimate_messages_tokens(messages)

    def get_usage_ratio(self, messages: List[BaseMessage]) -> float:
        """获取上下文使用率"""
        current = self.estimate_current_tokens(messages)
        return current / self._context_window if self._context_window > 0 else 0

    def should_compact(
        self,
        messages: List[BaseMessage],
        buffer_tokens: int = 13000,
    ) -> bool:
        """
        是否应该触发压缩
        
        参考 Claude Code: threshold = contextWindow - maxOutput - buffer
        """
        current = self.estimate_current_tokens(messages)
        threshold = self._context_window - buffer_tokens
        return current >= threshold

    def get_warning_state(
        self,
        messages: List[BaseMessage],
        warning_buffer: int = 20000,
        error_buffer: int = 20000,
    ) -> Optional[str]:
        """
        获取 token 警告状态
        
        参考 Claude Code: calculateTokenWarningState()
        """
        current = self.estimate_current_tokens(messages)
        threshold = self._context_window

        if current >= threshold - error_buffer:
            return "critical"
        elif current >= threshold - warning_buffer:
            return "warning"
        return None


# ============ Token 预算解析 ============

# 参考 Claude Code: parseTokenBudget()
_SHORTHAND_START_RE = re.compile(r'^\s*\+(\d+(?:\.\d+)?)\s*(k|m|b)\b', re.IGNORECASE)
_SHORTHAND_END_RE = re.compile(r'\s\+(\d+(?:\.\d+)?)\s*(k|m|b)\s*[.!?]?\s*$', re.IGNORECASE)
_VERBOSE_RE = re.compile(r'\b(?:use|spend|用)\s*(\d+(?:\.\d+)?)\s*(k|m|b)\s*tokens?\b', re.IGNORECASE)

_MULTIPLIERS = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}


def parse_token_budget(text: str) -> Optional[int]:
    """
    从用户输入解析 token 预算
    
    支持:
    - "+500k" (开头/结尾)
    - "use 2M tokens"
    - "用 1m tokens"
    
    参考 Claude Code: parseTokenBudget()
    """
    # 开头简写
    match = _SHORTHAND_START_RE.match(text)
    if match:
        return int(float(match.group(1)) * _MULTIPLIERS[match.group(2).lower()])

    # 结尾简写
    match = _SHORTHAND_END_RE.search(text)
    if match:
        return int(float(match.group(1)) * _MULTIPLIERS[match.group(2).lower()])

    # 详细格式
    match = _VERBOSE_RE.search(text)
    if match:
        return int(float(match.group(1)) * _MULTIPLIERS[match.group(2).lower()])

    return None


__all__ = [
    # 常量
    "FILE_TYPE_BYTES_PER_TOKEN",
    "DEFAULT_BYTES_PER_TOKEN",
    # 函数
    "bytes_per_token_for_file_type",
    "rough_token_count",
    "rough_token_count_for_file",
    "estimate_message_tokens",
    "estimate_messages_tokens",
    "parse_token_budget",
    # 类
    "UsageSnapshot",
    "HybridTokenEstimator",
]
