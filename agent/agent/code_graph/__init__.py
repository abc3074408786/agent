"""
代码图谱分析模块 - 基于 Python AST + SQLite 持久化的代码结构分析器

功能:
- 解析 Python 源代码，提取函数、类、导入关系
- 构建调用图、导入图、继承图（持久化到 SQLite）
- FTS5 全文搜索符号
- 基于文件 hash 的增量更新（只重新解析变更文件）
- 影响分析和符号查询
- 导出为 DOT/Mermaid 格式
"""

import ast
import os
import logging
import time
from pathlib import Path
from typing import List, Dict, Set, Optional, Any

from .storage import (
    CodeGraphStorage,
    SymbolRecord,
    EdgeRecord,
    get_storage,
    reset_storage,
)

logger = logging.getLogger(__name__)

# ==============================================================================
# AST 访问器
# ==============================================================================


class _ASTVisitor(ast.NodeVisitor):
    """AST 访问器 - 提取代码结构信息"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.module_name = Path(filepath).stem
        self.functions: List[Dict[str, Any]] = []
        self.classes: List[Dict[str, Any]] = []
        self.imports: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, str]] = []
        self.inheritances: List[Dict[str, str]] = []
        self._current_scope: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        name = ".".join(self._current_scope + [node.name])
        docstring = ast.get_docstring(node)
        signature = self._get_signature(node)

        self.functions.append({
            "name": node.name,
            "qualified_name": name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "docstring": docstring,
            "signature": signature,
        })

        # 提取函数内的调用
        self._current_scope.append(node.name)
        self._extract_calls(node, name)
        self.generic_visit(node)
        self._current_scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        """访问类定义"""
        name = ".".join(self._current_scope + [node.name])
        docstring = ast.get_docstring(node)

        self.classes.append({
            "name": node.name,
            "qualified_name": name,
            "line": node.lineno,
            "end_line": node.end_lineno,
            "docstring": docstring,
        })

        # 提取继承关系
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name:
                self.inheritances.append({
                    "child": name,
                    "parent": base_name,
                })

        self._current_scope.append(node.name)
        self.generic_visit(node)
        self._current_scope.pop()

    def visit_Import(self, node: ast.Import):
        """访问 import 语句"""
        for alias in node.names:
            self.imports.append({
                "module": alias.name,
                "name": alias.asname or alias.name,
                "type": "absolute",
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """访问 from ... import 语句"""
        module = node.module or ""
        level = node.level or 0
        for alias in (node.names or []):
            self.imports.append({
                "module": module,
                "name": alias.name,
                "type": "relative" if level > 0 else "absolute",
            })

    def _extract_calls(self, node: ast.AST, scope_name: str):
        """提取函数调用"""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = self._get_call_name(child)
                if func_name:
                    self.calls.append({
                        "caller": scope_name,
                        "callee": func_name,
                    })

    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """获取调用的函数名"""
        return self._get_name(node.func)

    def _get_name(self, node: ast.AST) -> Optional[str]:
        """从 AST 节点获取名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Subscript):
            return self._get_name(node.value)
        return None

    def _get_signature(self, node: ast.FunctionDef) -> str:
        """提取函数签名"""
        try:
            args = []
            for arg in node.args.args:
                arg_str = arg.arg
                if arg.annotation:
                    ann = ast.unparse(arg.annotation)
                    arg_str += f": {ann}"
                args.append(arg_str)

            # 默认值
            defaults = node.args.defaults
            num_defaults = len(defaults)
            if num_defaults > 0:
                start = len(args) - num_defaults
                for i, default in enumerate(defaults):
                    args[start + i] += f"={ast.unparse(default)}"

            ret = ""
            if node.returns:
                ret = f" -> {ast.unparse(node.returns)}"

            return f"({', '.join(args)}){ret}"
        except Exception:
            return ""


# ==============================================================================
# 需要跳过的目录
# ==============================================================================

_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", "node_modules", ".git",
    ".tox", "dist", "build", "egg-info", ".codegraph",
}


# ==============================================================================
# 代码图谱分析器（SQLite 持久化版）
# ==============================================================================


class CodeGraphAnalyzer:
    """Python 代码图谱分析器（SQLite 持久化版）
    
    基于 AST 解析 Python 源代码，将代码结构持久化到 SQLite 数据库。
    支持增量更新（基于文件 hash），FTS5 全文搜索，结构化图查询。
    
    用法:
        analyzer = CodeGraphAnalyzer("/path/to/project")
        analyzer.index()  # 首次全量索引
        # 后续调用会自动增量更新
        
        # 查询
        results = analyzer.search("calculator")
        callers = analyzer.get_callers("execute")
        impact = analyzer.get_impact("config")
    """

    def __init__(self, project_root: str = ".", db_path: Optional[str] = None):
        """初始化分析器
        
        Args:
            project_root: 项目根目录
            db_path: 数据库路径，默认为 {project_root}/.codegraph/index.db
        """
        self.project_root = str(Path(project_root).resolve())
        if db_path is None:
            db_path = os.path.join(self.project_root, ".codegraph", "index.db")
        self.storage = CodeGraphStorage(db_path)
        self._indexed_count = 0
        self._skipped_count = 0

    # ==========================================================================
    # 索引方法
    # ==========================================================================

    def index(self, pattern: str = "**/*.py", force: bool = False) -> Dict[str, int]:
        """索引项目（增量模式，只重新解析变更文件）
        
        Args:
            pattern: 文件匹配模式
            force: 强制全量重新索引
            
        Returns:
            {"indexed": 新索引数, "skipped": 跳过数, "total_files": 总文件数, "elapsed_ms": 耗时}
        """
        start_time = time.time()
        self._indexed_count = 0
        self._skipped_count = 0

        root = Path(self.project_root)
        total_files = 0

        for filepath in root.glob(pattern):
            # 跳过特定目录
            parts = filepath.parts
            if any(skip in parts for skip in _SKIP_DIRS):
                continue
            if not filepath.is_file():
                continue

            total_files += 1
            filepath_str = str(filepath.resolve())

            if not force and not self.storage.file_needs_reindex(filepath_str):
                self._skipped_count += 1
                continue

            self._index_file(filepath_str)

        elapsed_ms = int((time.time() - start_time) * 1000)
        result = {
            "indexed": self._indexed_count,
            "skipped": self._skipped_count,
            "total_files": total_files,
            "elapsed_ms": elapsed_ms,
        }
        logger.info(
            f"索引完成: {self._indexed_count} 个文件已索引, "
            f"{self._skipped_count} 个跳过 (未变更), "
            f"耗时 {elapsed_ms}ms"
        )
        return result

    def index_file(self, filepath: str) -> bool:
        """索引单个文件（增量：hash 未变则跳过）
        
        Args:
            filepath: 文件路径
            
        Returns:
            True 如果文件被重新索引
        """
        filepath = str(Path(filepath).resolve())
        if not self.storage.file_needs_reindex(filepath):
            return False
        self._index_file(filepath)
        return True

    def reindex_file(self, filepath: str):
        """强制重新索引单个文件（不检查 hash）"""
        filepath = str(Path(filepath).resolve())
        self._index_file(filepath)

    def _index_file(self, filepath: str):
        """内部方法：解析并存储单个文件"""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except (IOError, OSError) as e:
            logger.warning(f"无法读取文件 {filepath}: {e}")
            return

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            logger.warning(f"语法错误，跳过 {filepath}: {e}")
            return

        # 计算文件 hash 并更新文件记录
        file_hash = self.storage.compute_file_hash(filepath)
        file_size = os.path.getsize(filepath)

        # 先清除旧数据
        self.storage.remove_file(filepath)

        # 插入/更新文件记录
        file_id = self.storage.upsert_file(filepath, file_hash, file_size)

        # 使用 AST 访问器提取信息
        visitor = _ASTVisitor(filepath)
        visitor.visit(tree)

        module_name = Path(filepath).stem
        module_docstring = ast.get_docstring(tree)

        # 收集所有符号
        symbols: List[SymbolRecord] = []
        edges: List[EdgeRecord] = []

        # 模块节点
        symbols.append(SymbolRecord(
            name=module_name,
            qualified_name=module_name,
            type="module",
            file_id=file_id,
            file_path=filepath,
            line=1,
            docstring=module_docstring,
        ))

        # 函数节点
        for func in visitor.functions:
            symbols.append(SymbolRecord(
                name=func["name"],
                qualified_name=func["qualified_name"],
                type="function",
                file_id=file_id,
                file_path=filepath,
                line=func["line"],
                end_line=func.get("end_line"),
                signature=func.get("signature"),
                docstring=func.get("docstring"),
            ))

        # 类节点
        for cls in visitor.classes:
            symbols.append(SymbolRecord(
                name=cls["name"],
                qualified_name=cls["qualified_name"],
                type="class",
                file_id=file_id,
                file_path=filepath,
                line=cls["line"],
                end_line=cls.get("end_line"),
                docstring=cls.get("docstring"),
            ))

        # 批量插入符号
        self.storage.insert_symbols_batch(symbols)

        # 调用边
        for call in visitor.calls:
            edges.append(EdgeRecord(
                source_name=call["caller"],
                target_name=call["callee"],
                type="calls",
                source_file=filepath,
            ))

        # 导入边
        for imp in visitor.imports:
            target = imp["module"] if imp["module"] else imp["name"]
            edges.append(EdgeRecord(
                source_name=module_name,
                target_name=target,
                type="imports",
                source_file=filepath,
            ))

        # 继承边
        for inh in visitor.inheritances:
            edges.append(EdgeRecord(
                source_name=inh["child"],
                target_name=inh["parent"],
                type="inherits",
                source_file=filepath,
            ))

        # 批量插入边
        self.storage.insert_edges_batch(edges)

        self._indexed_count += 1
        logger.debug(
            f"已索引: {filepath} "
            f"(符号: {len(symbols)}, 边: {len(edges)})"
        )

    # ==========================================================================
    # 查询方法
    # ==========================================================================

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """FTS5 全文搜索符号
        
        Args:
            query: 搜索关键字（支持 FTS5 语法：前缀 "calc*"、短语、布尔 OR/AND）
            limit: 最大返回数
            
        Returns:
            匹配的符号列表
        """
        results = self.storage.search(query, limit)
        return [
            {
                "name": s.name,
                "qualified_name": s.qualified_name,
                "type": s.type,
                "file": s.file_path,
                "line": s.line,
                "signature": s.signature,
                "docstring": s.docstring[:100] if s.docstring else None,
            }
            for s in results
        ]

    def get_callers(self, func_name: str) -> List[Dict[str, str]]:
        """谁调用了这个函数"""
        return self.storage.get_callers(func_name)

    def get_callees(self, func_name: str) -> List[Dict[str, str]]:
        """这个函数调用了谁"""
        return self.storage.get_callees(func_name)

    def get_dependents(self, module_name: str) -> List[Dict[str, str]]:
        """谁依赖了这个模块"""
        return self.storage.get_dependents(module_name)

    def get_dependencies(self, module_name: str) -> List[Dict[str, str]]:
        """这个模块依赖谁"""
        return self.storage.get_dependencies(module_name)

    def get_impact(self, symbol_name: str) -> Dict[str, Any]:
        """影响分析 — 修改某符号会影响哪些文件和符号
        
        Args:
            symbol_name: 符号名
            
        Returns:
            {"files": [...], "symbols": [...], "count": int}
        """
        result = self.storage.get_impact(symbol_name)
        return {
            "files": sorted(result["files"]),
            "symbols": sorted(result["symbols"]),
            "file_count": len(result["files"]),
            "symbol_count": len(result["symbols"]),
        }

    def get_symbol_at(self, filepath: str, line: int) -> Optional[Dict[str, Any]]:
        """获取某行所在的符号"""
        filepath = str(Path(filepath).resolve())
        record = self.storage.get_symbol_at_line(filepath, line)
        if record:
            return {
                "name": record.name,
                "qualified_name": record.qualified_name,
                "type": record.type,
                "file": record.file_path,
                "line": record.line,
            }
        return None

    def get_context(self, symbol_name: str) -> Dict[str, Any]:
        """获取符号的完整上下文（定义 + 调用者 + 被调用者）
        
        这是 CodeGraph 风格的 "一次调用获取全部上下文" 接口。
        
        Args:
            symbol_name: 符号名
            
        Returns:
            包含定义、调用者、被调用者、影响范围的完整上下文
        """
        # 符号定义
        symbols = self.storage.get_symbol_by_name(symbol_name)
        definitions = [
            {
                "name": s.name,
                "qualified_name": s.qualified_name,
                "type": s.type,
                "file": s.file_path,
                "line": s.line,
                "signature": s.signature,
                "docstring": s.docstring[:200] if s.docstring else None,
            }
            for s in symbols if s.type != "module"
        ]

        # 调用关系
        callers = self.storage.get_callers(symbol_name)
        callees = self.storage.get_callees(symbol_name)

        # 影响分析
        impact = self.storage.get_impact(symbol_name, max_depth=3)

        return {
            "symbol": symbol_name,
            "definitions": definitions,
            "callers": callers[:20],
            "callees": callees[:20],
            "impact": {
                "files": sorted(impact["files"])[:10],
                "symbols": sorted(impact["symbols"])[:20],
            },
        }

    # ==========================================================================
    # 统计和导出
    # ==========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """获取图谱统计信息"""
        stats = self.storage.get_stats()
        stats["db_size"] = self.storage.get_db_size()
        stats["project_root"] = self.project_root
        return stats

    def to_mermaid(self, edge_type: str = "calls", limit: int = 50) -> str:
        """导出为 Mermaid 格式
        
        Args:
            edge_type: 边类型 (calls/imports/inherits)
            limit: 最大边数
        """
        edges = self.storage.get_edges_by_type(edge_type)[:limit]
        lines = ["graph LR"]

        arrow = {"calls": "-->", "imports": "-.->", "inherits": "==>"}
        arrow_str = arrow.get(edge_type, "-->")

        seen: Set[str] = set()
        for e in edges:
            src = e.source_name.replace(".", "_").replace(" ", "_")
            tgt = e.target_name.replace(".", "_").replace(" ", "_")
            edge_line = f"    {src} {arrow_str}|{edge_type}| {tgt}"
            if edge_line not in seen:
                seen.add(edge_line)
                lines.append(edge_line)

        return "\n".join(lines)

    def to_dot(self, edge_type: str = "calls", limit: int = 50) -> str:
        """导出为 Graphviz DOT 格式"""
        edges = self.storage.get_edges_by_type(edge_type)[:limit]

        lines = ["digraph CodeGraph {"]
        lines.append("    rankdir=LR;")
        lines.append("    node [shape=box, style=filled, fillcolor=\"#a8d8ea\"];")
        lines.append("")

        edge_styles = {"calls": "solid", "imports": "dashed", "inherits": "bold"}
        style = edge_styles.get(edge_type, "solid")

        seen: Set[str] = set()
        for e in edges:
            src = e.source_name.replace(".", "_").replace("/", "_")
            tgt = e.target_name.replace(".", "_").replace("/", "_")
            line = f'    "{src}" -> "{tgt}" [style={style}];'
            if line not in seen:
                seen.add(line)
                lines.append(line)

        lines.append("}")
        return "\n".join(lines)

    # ==========================================================================
    # 生命周期
    # ==========================================================================

    def close(self):
        """关闭数据库连接"""
        self.storage.close()

    def reset(self):
        """清空所有数据，重新开始"""
        self.storage.clear()


# ==============================================================================
# LangChain / MCP 工具集成
# ==============================================================================

# 全局分析器实例（懒初始化）
_global_analyzer: Optional[CodeGraphAnalyzer] = None


def get_analyzer(project_root: str = ".") -> CodeGraphAnalyzer:
    """获取全局分析器实例"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = CodeGraphAnalyzer(project_root)
    return _global_analyzer


def code_graph_index_tool(path: str = ".", force: bool = False) -> str:
    """索引代码库
    
    Args:
        path: 项目路径
        force: 是否强制全量索引
        
    Returns:
        索引结果摘要
    """
    analyzer = get_analyzer(path)
    result = analyzer.index(force=force)
    return (
        f"索引完成:\n"
        f"  新索引: {result['indexed']} 个文件\n"
        f"  跳过 (未变更): {result['skipped']} 个文件\n"
        f"  总文件: {result['total_files']}\n"
        f"  耗时: {result['elapsed_ms']}ms"
    )


def code_graph_search_tool(query: str, path: str = ".") -> str:
    """FTS5 全文搜索符号
    
    Args:
        query: 搜索关键字
        path: 项目路径
    """
    analyzer = get_analyzer(path)
    results = analyzer.search(query)
    if not results:
        return f"没有找到匹配 '{query}' 的符号"
    lines = [f"搜索 '{query}' 的结果 ({len(results)} 个):"]
    for r in results:
        sig = f" {r['signature']}" if r.get("signature") else ""
        lines.append(f"  {r['type']:8s} {r['qualified_name']}{sig}")
        lines.append(f"           @ {r['file']}:{r['line']}")
    return "\n".join(lines)


def code_graph_context_tool(symbol: str, path: str = ".") -> str:
    """获取符号的完整上下文（一次调用获取定义+调用者+被调用者+影响）
    
    Args:
        symbol: 符号名
        path: 项目路径
    """
    analyzer = get_analyzer(path)
    ctx = analyzer.get_context(symbol)

    lines = [f"=== 符号上下文: {symbol} ===\n"]

    # 定义
    if ctx["definitions"]:
        lines.append("📍 定义:")
        for d in ctx["definitions"]:
            sig = f" {d['signature']}" if d.get("signature") else ""
            lines.append(f"  [{d['type']}] {d['qualified_name']}{sig}")
            lines.append(f"    文件: {d['file']}:{d['line']}")
            if d.get("docstring"):
                lines.append(f"    文档: {d['docstring']}")
    else:
        lines.append("📍 定义: 未找到")

    # 调用者
    lines.append(f"\n📞 调用者 ({len(ctx['callers'])}):")
    for c in ctx["callers"][:10]:
        lines.append(f"  ← {c['name']}  @ {c.get('file', '')}:{c.get('line', '')}")

    # 被调用
    lines.append(f"\n📤 调用的函数 ({len(ctx['callees'])}):")
    for c in ctx["callees"][:10]:
        lines.append(f"  → {c['name']}")

    # 影响
    impact = ctx["impact"]
    if impact["files"]:
        lines.append(f"\n💥 影响范围 ({len(impact['files'])} 文件, {len(impact['symbols'])} 符号):")
        for f in impact["files"][:5]:
            lines.append(f"  📁 {f}")

    return "\n".join(lines)


def code_graph_impact_tool(symbol_name: str, path: str = ".") -> str:
    """影响分析
    
    Args:
        symbol_name: 符号名
        path: 项目路径
    """
    analyzer = get_analyzer(path)
    impact = analyzer.get_impact(symbol_name)

    if not impact["files"] and not impact["symbols"]:
        return f"修改 '{symbol_name}' 不会影响其他已分析的代码"

    lines = [f"修改 '{symbol_name}' 的影响分析:"]
    lines.append(f"\n受影响的文件 ({impact['file_count']}):")
    for f in impact["files"][:20]:
        lines.append(f"  📁 {f}")

    lines.append(f"\n受影响的符号 ({impact['symbol_count']}):")
    for s in impact["symbols"][:30]:
        lines.append(f"  🔗 {s}")

    return "\n".join(lines)


def code_graph_stats_tool(path: str = ".") -> str:
    """获取图谱统计"""
    analyzer = get_analyzer(path)
    stats = analyzer.get_stats()
    return (
        f"代码图谱统计:\n"
        f"  项目路径: {stats['project_root']}\n"
        f"  数据库大小: {stats['db_size']}\n"
        f"  ─────────────────\n"
        f"  文件数: {stats['files']}\n"
        f"  符号总数: {stats['symbols']}\n"
        f"    函数: {stats['functions']}\n"
        f"    类: {stats['classes']}\n"
        f"    模块: {stats['modules']}\n"
        f"  ─────────────────\n"
        f"  边总数: {stats['edges']}\n"
        f"    调用边: {stats['call_edges']}\n"
        f"    导入边: {stats['import_edges']}\n"
        f"    继承边: {stats['inherit_edges']}"
    )


# ==============================================================================
# 公开 API
# ==============================================================================

__all__ = [
    # 分析器
    "CodeGraphAnalyzer",
    "get_analyzer",
    # 存储
    "CodeGraphStorage",
    "SymbolRecord",
    "EdgeRecord",
    "get_storage",
    "reset_storage",
    # 工具函数
    "code_graph_index_tool",
    "code_graph_search_tool",
    "code_graph_context_tool",
    "code_graph_impact_tool",
    "code_graph_stats_tool",
]
