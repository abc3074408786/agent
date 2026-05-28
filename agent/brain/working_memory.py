"""
有限工作记忆（Working Memory）

模拟前额叶皮层的工作记忆系统：
- 容量有限（7±2 个 chunk） — 这不是缺陷，是特性
- 强制压缩 — 信息超出容量时必须抽象化
- 注意力聚焦 — 同时只能关注有限信息
- 衰减机制 — 不被关注的信息自然消失

为什么限制容量是关键：
    人脑工作记忆只有 ~7 个槽位，这迫使我们：
    1. 把具体细节压缩成抽象概念（chunking）
    2. 只关注真正重要的信息（注意力）
    3. 形成层次化的知识结构

    当前 AI 的 context window 是"平"的——所有 token 等权处理。
    有限工作记忆强制信息分层，逼出真正的理解和抽象。

使用示例:
    wm = WorkingMemory(capacity=7)

    # 添加信息
    wm.push("用户要修改 login 模块")
    wm.push("login.py 有 200 行")
    wm.push("依赖 auth_service")
    ...

    # 容量满了，自动压缩
    wm.push("还需要修改 tests")
    # → 之前的细节被压缩为："login 模块修改：200行，依赖 auth"

    # 获取当前关注的信息
    focus = wm.get_focus()
"""

import time
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class MemoryChunk:
    """
    工作记忆中的一个 chunk（记忆块）

    参照 Miller's Law：人脑通过 "chunking" 将多个信息
    压缩成一个有意义的单元来扩展工作记忆。
    """
    content: str                    # 记忆内容
    importance: float = 0.5         # 重要度 0.0-1.0
    activation: float = 1.0         # 激活度 0.0-1.0（随时间衰减）
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0           # 被访问次数
    category: str = "general"       # 类别：task, context, result, insight
    compressed_from: List[str] = field(default_factory=list)  # 压缩来源
    is_compressed: bool = False     # 是否是压缩后的块

    @property
    def effective_importance(self) -> float:
        """有效重要度 = 基础重要度 × 激活度"""
        return self.importance * self.activation

    def access(self) -> None:
        """访问此块（提升激活度）"""
        self.last_accessed = time.time()
        self.access_count += 1
        self.activation = min(1.0, self.activation + 0.2)

    def decay(self, rate: float = 0.05) -> None:
        """衰减激活度"""
        time_since = time.time() - self.last_accessed
        decay_amount = rate * (time_since / 60.0)  # 每分钟衰减 rate
        self.activation = max(0.0, self.activation - decay_amount)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryChunk":
        return cls(**data)


class WorkingMemory:
    """
    有限容量的工作记忆系统

    核心规则:
    1. 容量限制：最多持有 capacity 个 chunk
    2. 满了怎么办：压缩最不重要的 chunks → 形成一个抽象 chunk
    3. 衰减机制：长时间不被访问的 chunk 激活度下降
    4. 注意力聚焦：get_focus() 返回当前最活跃的 chunks
    """

    DEFAULT_CAPACITY = 7    # Miller's Number
    COMPRESSION_TRIGGER = 2  # 超出容量多少时触发压缩

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        """
        Args:
            capacity: 工作记忆容量（默认7，取 Miller's Number）
        """
        self._capacity = max(3, min(capacity, 15))  # 限制 3-15
        self._chunks: List[MemoryChunk] = []
        self._archive: List[MemoryChunk] = []  # 被淘汰的 chunk 存档（可检索）
        self._compression_count = 0             # 压缩次数（反映抽象能力使用情况）

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def size(self) -> int:
        return len(self._chunks)

    @property
    def is_full(self) -> bool:
        return len(self._chunks) >= self._capacity

    @property
    def utilization(self) -> float:
        """工作记忆使用率"""
        return len(self._chunks) / self._capacity

    @property
    def compression_count(self) -> int:
        """总压缩次数 — 反映系统做了多少次抽象"""
        return self._compression_count

    # ==================== 核心操作 ====================

    def push(
        self,
        content: str,
        importance: float = 0.5,
        category: str = "general",
    ) -> Optional[MemoryChunk]:
        """
        推入新信息到工作记忆

        如果超出容量，会触发压缩策略：
        - 把最不重要的几个 chunk 压缩成一个摘要 chunk
        - 腾出空间给新信息

        Args:
            content: 信息内容
            importance: 重要度 0.0-1.0
            category: 类别

        Returns:
            被压缩生成的 chunk（如果触发了压缩），否则 None
        """
        # 先衰减所有 chunk
        self._decay_all()

        new_chunk = MemoryChunk(
            content=content,
            importance=importance,
            category=category,
        )

        compressed_chunk = None

        # 检查是否需要压缩
        if len(self._chunks) >= self._capacity:
            compressed_chunk = self._compress_least_important()

        self._chunks.append(new_chunk)

        logger.debug(
            f"[WorkingMemory] push: '{content[:30]}...' "
            f"(usage: {self.size}/{self._capacity})"
        )

        return compressed_chunk

    def get_focus(self, top_n: int = 3) -> List[MemoryChunk]:
        """
        获取当前注意力聚焦的 chunks

        返回激活度最高的 top_n 个 chunk。
        这模拟人类"当前在想什么"。

        Args:
            top_n: 返回前几个最活跃的

        Returns:
            按激活度排序的 chunk 列表
        """
        self._decay_all()
        sorted_chunks = sorted(
            self._chunks,
            key=lambda c: c.effective_importance,
            reverse=True,
        )
        # 访问返回的 chunk（提升激活度）
        for chunk in sorted_chunks[:top_n]:
            chunk.access()
        return sorted_chunks[:top_n]

    def get_all(self) -> List[MemoryChunk]:
        """获取所有工作记忆内容"""
        return list(self._chunks)

    def search(self, keyword: str) -> List[MemoryChunk]:
        """搜索工作记忆（简单关键词匹配）"""
        results = []
        keyword_lower = keyword.lower()
        for chunk in self._chunks:
            if keyword_lower in chunk.content.lower():
                chunk.access()  # 搜到即访问
                results.append(chunk)
        return results

    def boost(self, keyword: str, amount: float = 0.3) -> int:
        """
        提升包含关键词的 chunk 的重要度

        模拟"注意力转移" — 当任务方向改变时，
        相关信息的激活度上升。

        Returns:
            被提升的 chunk 数量
        """
        boosted = 0
        keyword_lower = keyword.lower()
        for chunk in self._chunks:
            if keyword_lower in chunk.content.lower():
                chunk.importance = min(1.0, chunk.importance + amount)
                chunk.activation = min(1.0, chunk.activation + amount)
                boosted += 1
        return boosted

    def clear(self) -> None:
        """清空工作记忆（类似"切换任务"）"""
        # 转移到存档
        self._archive.extend(self._chunks)
        self._chunks.clear()
        logger.debug("[WorkingMemory] cleared")

    def get_summary(self) -> str:
        """
        获取工作记忆的摘要视图

        返回当前工作记忆的人类可读摘要，
        包括各 chunk 的内容和状态。
        """
        if not self._chunks:
            return "工作记忆为空"

        lines = [f"工作记忆 ({self.size}/{self._capacity} slots):"]
        for i, chunk in enumerate(sorted(self._chunks, key=lambda c: c.effective_importance, reverse=True)):
            status = "★" if chunk.activation > 0.7 else "☆" if chunk.activation > 0.3 else "·"
            compressed = " [压缩]" if chunk.is_compressed else ""
            lines.append(
                f"  {status} [{chunk.category}] {chunk.content[:60]}"
                f" (重要度:{chunk.importance:.1f}, 激活:{chunk.activation:.1f}){compressed}"
            )

        if self._compression_count > 0:
            lines.append(f"\n  累计压缩 {self._compression_count} 次")

        return "\n".join(lines)

    def to_context_string(self) -> str:
        """
        将工作记忆转化为可注入 LLM prompt 的字符串

        按重要度排序，输出为 Agent 可以理解的上下文格式。
        """
        if not self._chunks:
            return ""

        focus = self.get_focus(top_n=self._capacity)
        lines = ["[当前工作记忆]"]
        for chunk in focus:
            lines.append(f"- {chunk.content}")
        return "\n".join(lines)

    # ==================== 压缩策略 ====================

    def _compress_least_important(self) -> MemoryChunk:
        """
        压缩最不重要的 chunks

        策略：
        1. 找到激活度最低的 2-3 个 chunk
        2. 把它们的内容合并为一个摘要
        3. 这个摘要就是一个新的"抽象 chunk"
        4. 原始 chunks 移入存档

        这模拟人类的 chunking 过程：
        "记住那三个具体步骤"→ "记住需要做部署"
        """
        # 按有效重要度排序，找最不重要的
        sorted_chunks = sorted(
            self._chunks,
            key=lambda c: c.effective_importance,
        )

        # 取最不重要的 2-3 个来压缩
        n_to_compress = min(3, max(2, len(sorted_chunks) - self._capacity + 2))
        to_compress = sorted_chunks[:n_to_compress]

        # 从工作记忆中移除
        for chunk in to_compress:
            self._chunks.remove(chunk)
            self._archive.append(chunk)

        # 生成压缩摘要
        contents = [c.content for c in to_compress]
        compressed_content = self._generate_compression(contents)

        # 创建压缩后的 chunk
        compressed = MemoryChunk(
            content=compressed_content,
            importance=max(c.importance for c in to_compress) * 0.8,
            activation=0.6,
            category="compressed",
            compressed_from=contents,
            is_compressed=True,
        )

        self._chunks.append(compressed)
        self._compression_count += 1

        logger.info(
            f"[WorkingMemory] 压缩 {n_to_compress} 个 chunk → '{compressed_content[:50]}...'"
        )

        return compressed

    def _generate_compression(self, contents: List[str]) -> str:
        """
        生成压缩摘要

        当前使用简单规则：取各内容的关键词拼接。
        TODO: 未来可接入 LLM 做更智能的抽象。
        """
        if len(contents) == 1:
            return contents[0][:80]

        # 简单策略：提取每条内容的核心（前30字符）+ 标记来源数量
        summaries = [c[:30].strip() for c in contents]
        return f"[摘要/{len(contents)}条] " + "; ".join(summaries)

    def _decay_all(self) -> None:
        """衰减所有 chunk 的激活度"""
        for chunk in self._chunks:
            chunk.decay(rate=0.02)

        # 移除激活度极低的 chunk
        dead_chunks = [c for c in self._chunks if c.activation < 0.05]
        for chunk in dead_chunks:
            self._chunks.remove(chunk)
            self._archive.append(chunk)
            logger.debug(f"[WorkingMemory] chunk 自然衰减消失: '{chunk.content[:30]}...'")

    # ==================== 存档检索 ====================

    def recall_from_archive(self, keyword: str, limit: int = 3) -> List[MemoryChunk]:
        """
        从存档中回忆（类似"啊我想起来了"）

        被淘汰的信息不会完全消失，
        当遇到相关线索时可以重新激活。

        Args:
            keyword: 触发回忆的关键词
            limit: 最多回忆几个

        Returns:
            从存档中找回的 chunks
        """
        keyword_lower = keyword.lower()
        matches = [
            chunk for chunk in self._archive
            if keyword_lower in chunk.content.lower()
        ]
        # 按原始重要度排序
        matches.sort(key=lambda c: c.importance, reverse=True)
        return matches[:limit]

    def reactivate(self, chunk: MemoryChunk) -> bool:
        """
        将存档中的 chunk 重新激活到工作记忆

        Returns:
            是否成功（如果工作记忆已满且新 chunk 不够重要，可能失败）
        """
        if chunk in self._archive:
            self._archive.remove(chunk)
            chunk.activation = 0.7  # 重新激活
            chunk.last_accessed = time.time()

            if self.is_full:
                # 需要和现有最不重要的比较
                least = min(self._chunks, key=lambda c: c.effective_importance)
                if chunk.importance > least.importance:
                    self._chunks.remove(least)
                    self._archive.append(least)
                    self._chunks.append(chunk)
                    return True
                else:
                    self._archive.append(chunk)  # 放回去
                    return False
            else:
                self._chunks.append(chunk)
                return True
        return False
