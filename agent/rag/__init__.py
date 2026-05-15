"""
RAG 知识检索模块

提供简单的文本检索功能（不依赖外部向量数据库）:
- Document 数据类: 文档表示 (content, metadata, source)
- SimpleVectorStore: 基于 TF-IDF 的简单向量存储（仅用标准库）
- add_documents, search, clear
- rag_search_tool: LangChain 工具包装
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ============ 数据模型 ============

@dataclass
class Document:
    """
    文档数据类
    
    Attributes:
        content: 文档文本内容
        metadata: 文档元数据（如标题、作者、创建时间等）
        source: 文档来源（文件路径、URL 等）
        doc_id: 文档唯一标识
    """
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    doc_id: str = ""

    def __post_init__(self):
        if not self.doc_id:
            # 基于内容生成简单 ID
            import hashlib
            self.doc_id = hashlib.md5(
                self.content[:200].encode("utf-8")
            ).hexdigest()[:12]


@dataclass
class SearchResult:
    """搜索结果"""
    document: Document
    score: float
    highlights: List[str] = field(default_factory=list)


# ============ TF-IDF 向量存储 ============

class SimpleVectorStore:
    """
    基于 TF-IDF 的简单向量存储
    
    使用 Python 标准库实现，不依赖任何外部向量数据库或 ML 库。
    适合小规模文档检索场景。
    
    算法:
    - TF (Term Frequency): 词在文档中出现的频率
    - IDF (Inverse Document Frequency): 词在所有文档中的逆文档频率
    - 相似度: 余弦相似度
    """

    def __init__(self):
        self._documents: List[Document] = []
        self._tf_vectors: List[Dict[str, float]] = []  # 每个文档的 TF 向量
        self._idf: Dict[str, float] = {}  # IDF 值
        self._vocabulary: set = set()  # 词汇表
        self._dirty = True  # IDF 是否需要重新计算

    @property
    def document_count(self) -> int:
        """文档数量"""
        return len(self._documents)

    def _tokenize(self, text: str) -> List[str]:
        """
        分词
        
        简单分词策略:
        - 英文按空格和标点分割，转小写
        - 中文按字符分割
        - 过滤停用词和过短的词
        """
        # 转小写
        text = text.lower()
        
        # 提取英文单词和中文字符
        tokens = []
        
        # 英文单词 (至少2个字符)
        english_words = re.findall(r"[a-z][a-z0-9_]{1,}", text)
        tokens.extend(english_words)
        
        # 中文字符（单字和双字组合）
        chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
        tokens.extend(chinese_chars)
        
        # 中文双字组合 (bigrams)
        for i in range(len(chinese_chars) - 1):
            tokens.append(chinese_chars[i] + chinese_chars[i + 1])
        
        # 过滤停用词
        stop_words = {
            "the", "is", "at", "of", "on", "and", "or", "to", "in", "for",
            "it", "an", "as", "be", "by", "if", "no", "so", "up", "do",
            "的", "了", "是", "在", "有", "和", "不", "这", "我", "他",
        }
        
        tokens = [t for t in tokens if t not in stop_words]
        
        return tokens

    def _compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """计算 TF (词频)"""
        if not tokens:
            return {}
        
        counter = Counter(tokens)
        total = len(tokens)
        
        return {word: count / total for word, count in counter.items()}

    def _compute_idf(self) -> None:
        """计算 IDF (逆文档频率)"""
        if not self._documents:
            self._idf = {}
            return
        
        n = len(self._documents)
        df = Counter()  # 文档频率
        
        for tf_vector in self._tf_vectors:
            for word in tf_vector:
                df[word] += 1
        
        # IDF = log(N / (df + 1)) + 1 (平滑处理)
        self._idf = {
            word: math.log(n / (freq + 1)) + 1
            for word, freq in df.items()
        }
        
        self._dirty = False

    def _cosine_similarity(
        self, vec_a: Dict[str, float], vec_b: Dict[str, float]
    ) -> float:
        """计算余弦相似度"""
        # 计算点积
        common_words = set(vec_a.keys()) & set(vec_b.keys())
        if not common_words:
            return 0.0
        
        dot_product = sum(vec_a[w] * vec_b[w] for w in common_words)
        
        # 计算模长
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)

    def _get_tfidf_vector(self, tf_vector: Dict[str, float]) -> Dict[str, float]:
        """将 TF 向量转换为 TF-IDF 向量"""
        if self._dirty:
            self._compute_idf()
        
        return {
            word: tf * self._idf.get(word, 1.0)
            for word, tf in tf_vector.items()
        }

    def add_documents(self, documents: List[Document]) -> int:
        """
        添加文档到存储
        
        Args:
            documents: 文档列表
            
        Returns:
            成功添加的文档数量
        """
        added = 0
        
        for doc in documents:
            if not doc.content.strip():
                continue
            
            # 检查重复
            existing_ids = {d.doc_id for d in self._documents}
            if doc.doc_id in existing_ids:
                continue
            
            # 分词并计算 TF
            tokens = self._tokenize(doc.content)
            tf_vector = self._compute_tf(tokens)
            
            # 更新词汇表
            self._vocabulary.update(tf_vector.keys())
            
            # 添加文档
            self._documents.append(doc)
            self._tf_vectors.append(tf_vector)
            self._dirty = True
            added += 1
        
        return added

    def add_document(self, content: str, metadata: Optional[Dict[str, Any]] = None, source: str = "") -> str:
        """
        添加单个文档
        
        Args:
            content: 文档内容
            metadata: 元数据
            source: 来源
            
        Returns:
            文档 ID
        """
        doc = Document(content=content, metadata=metadata or {}, source=source)
        self.add_documents([doc])
        return doc.doc_id

    def search(self, query: str, top_k: int = 5, min_score: float = 0.0) -> List[SearchResult]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回前 K 个结果
            min_score: 最低相似度阈值
            
        Returns:
            搜索结果列表（按相似度降序排列）
        """
        if not self._documents:
            return []
        
        # 确保 IDF 是最新的
        if self._dirty:
            self._compute_idf()
        
        # 计算查询向量
        query_tokens = self._tokenize(query)
        query_tf = self._compute_tf(query_tokens)
        query_tfidf = self._get_tfidf_vector(query_tf)
        
        if not query_tfidf:
            return []
        
        # 计算与所有文档的相似度
        results: List[Tuple[int, float]] = []
        
        for idx, tf_vector in enumerate(self._tf_vectors):
            doc_tfidf = self._get_tfidf_vector(tf_vector)
            score = self._cosine_similarity(query_tfidf, doc_tfidf)
            
            if score > min_score:
                results.append((idx, score))
        
        # 排序
        results.sort(key=lambda x: x[1], reverse=True)
        
        # 构建结果
        search_results = []
        for idx, score in results[:top_k]:
            doc = self._documents[idx]
            
            # 提取高亮片段
            highlights = self._extract_highlights(doc.content, query_tokens)
            
            search_results.append(SearchResult(
                document=doc,
                score=score,
                highlights=highlights,
            ))
        
        return search_results

    def _extract_highlights(self, content: str, query_tokens: List[str], max_highlights: int = 3) -> List[str]:
        """提取包含查询词的文本片段"""
        sentences = re.split(r"[。！？.!?\n]+", content)
        
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or len(sentence) < 5:
                continue
            
            # 计算句子中包含的查询词数量
            sentence_lower = sentence.lower()
            match_count = sum(1 for token in query_tokens if token in sentence_lower)
            
            if match_count > 0:
                scored_sentences.append((sentence[:200], match_count))
        
        # 按匹配数排序
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        
        return [s[0] for s in scored_sentences[:max_highlights]]

    def clear(self) -> None:
        """清空所有文档"""
        self._documents.clear()
        self._tf_vectors.clear()
        self._idf.clear()
        self._vocabulary.clear()
        self._dirty = True

    def remove_document(self, doc_id: str) -> bool:
        """
        移除指定文档
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            是否移除成功
        """
        for idx, doc in enumerate(self._documents):
            if doc.doc_id == doc_id:
                self._documents.pop(idx)
                self._tf_vectors.pop(idx)
                self._dirty = True
                return True
        return False

    def get_document(self, doc_id: str) -> Optional[Document]:
        """获取指定文档"""
        for doc in self._documents:
            if doc.doc_id == doc_id:
                return doc
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        return {
            "document_count": len(self._documents),
            "vocabulary_size": len(self._vocabulary),
            "total_content_length": sum(len(d.content) for d in self._documents),
        }


# ============ LangChain 工具包装 ============

class RAGSearchInput(BaseModel):
    """RAG 搜索输入"""
    query: str = Field(description="搜索查询文本")
    top_k: int = Field(default=5, description="返回结果数量")
    min_score: float = Field(default=0.01, description="最低相似度阈值 (0-1)")


# 全局向量存储实例
_global_store = SimpleVectorStore()


def rag_search(query: str, top_k: int = 5, min_score: float = 0.01) -> str:
    """
    RAG 知识检索
    
    在已索引的文档中搜索与查询相关的内容。
    基于 TF-IDF 相似度进行排序。
    """
    results = _global_store.search(query, top_k=top_k, min_score=min_score)
    
    if not results:
        return "未找到相关文档。请确保已添加文档到知识库。"
    
    output_parts = [f"找到 {len(results)} 个相关文档:\n"]
    
    for i, result in enumerate(results, 1):
        doc = result.document
        source = doc.source or "未知来源"
        score = f"{result.score:.3f}"
        
        output_parts.append(f"--- 结果 {i} (相似度: {score}) ---")
        output_parts.append(f"来源: {source}")
        
        # 显示内容摘要（最多 500 字符）
        content_preview = doc.content[:500]
        if len(doc.content) > 500:
            content_preview += "..."
        output_parts.append(f"内容: {content_preview}")
        
        # 显示高亮
        if result.highlights:
            output_parts.append(f"相关片段: {' | '.join(result.highlights[:2])}")
        
        output_parts.append("")
    
    return "\n".join(output_parts)


def get_global_store() -> SimpleVectorStore:
    """获取全局向量存储实例"""
    return _global_store


def add_to_knowledge_base(content: str, source: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
    """向知识库添加文档"""
    doc_id = _global_store.add_document(content=content, source=source, metadata=metadata or {})
    return doc_id


# ============ 创建 LangChain 工具 ============

# 延迟导入以避免循环依赖
def create_rag_tool():
    """创建 RAG 搜索工具"""
    from agent.tools import create_tool
    
    return create_tool(
        name="rag_search",
        description=(
            "在知识库中搜索相关文档。"
            "基于 TF-IDF 文本相似度进行检索。"
            "适合搜索项目文档、代码注释、技术文档等已索引的内容。"
        ),
        func=rag_search,
        args_schema=RAGSearchInput,
    )


# 延迟创建工具实例
rag_search_tool = None


def get_rag_search_tool():
    """获取或创建 RAG 搜索工具（延迟初始化）"""
    global rag_search_tool
    if rag_search_tool is None:
        rag_search_tool = create_rag_tool()
    return rag_search_tool


__all__ = [
    "Document",
    "SearchResult",
    "SimpleVectorStore",
    "RAGSearchInput",
    "rag_search",
    "get_global_store",
    "add_to_knowledge_base",
    "get_rag_search_tool",
    "create_rag_tool",
]
