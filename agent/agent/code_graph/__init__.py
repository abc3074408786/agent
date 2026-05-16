"""
代码图谱分析模块 - 基于 Python AST 的代码结构分析器

功能:
- 解析 Python 源代码，提取函数、类、导入关系
- 构建调用图、导入图、继承图
- 支持影响分析和符号查询
- 导出为 DOT/Mermaid 格式
"""

import ast
import os
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# 数据结构
# ==============================================================================


@dataclass
class CodeNode:
    """代码节点 - 表示一个代码符号"""
    name: str
    type: str  # "function", "class", "module"
    file: str
    line: int
    docstring: Optional[str] = None

    @property
    def qualified_name(self) -> str:
        """返回完全限定名"""
        module = Path(self.file).stem if self.file else ""
        if self.type == "module":
            return self.name
        return f"{module}.{self.name}"

    def __hash__(self):
        return hash((self.name, self.type, self.file, self.line))

    def __eq__(self, other):
        if not isinstance(other, CodeNode):
            return False
        return (self.name == other.name and self.type == other.type
                and self.file == other.file and self.line == other.line)


@dataclass
class CodeEdge:
    """关系边 - 表示两个符号之间的关系"""
    source: str  # 源符号名
    target: str  # 目标符号名
    type: str  # "calls", "imports", "inherits", "uses"
    source_file: str = ""
    target_file: str = ""

    def __hash__(self):
        return hash((self.source, self.target, self.type))

    def __eq__(self, other):
        if not isinstance(other, CodeEdge):
            return False
        return (self.source == other.source and self.target == other.target
                and self.type == other.type)


@dataclass
class CodeGraph:
    """图数据结构 - 存储所有节点和边"""
    nodes: Dict[str, CodeNode] = field(default_factory=dict)
    edges: List[CodeEdge] = field(default_factory=list)
    _edge_set: Set[Tuple[str, str, str]] = field(default_factory=set)

    def add_node(self, node: CodeNode):
        """添加节点"""
        key = f"{node.file}::{node.name}"
        self.nodes[key] = node

    def add_edge(self, edge: CodeEdge):
        """添加边（去重）"""
        edge_key = (edge.source, edge.target, edge.type)
        if edge_key not in self._edge_set:
            self._edge_set.add(edge_key)
            self.edges.append(edge)

    def get_nodes_by_type(self, node_type: str) -> List[CodeNode]:
        """按类型获取节点"""
        return [n for n in self.nodes.values() if n.type == node_type]

    def get_edges_by_type(self, edge_type: str) -> List[CodeEdge]:
        """按类型获取边"""
        return [e for e in self.edges if e.type == edge_type]

    def get_outgoing_edges(self, source: str) -> List[CodeEdge]:
        """获取从某个节点出发的所有边"""
        return [e for e in self.edges if e.source == source]

    def get_incoming_edges(self, target: str) -> List[CodeEdge]:
        """获取指向某个节点的所有边"""
        return [e for e in self.edges if e.target == target]


# ==============================================================================
# AST 访问器
# ==============================================================================


class _ASTVisitor(ast.NodeVisitor):
    """AST 访问器 - 提取代码结构信息"""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.module_name = Path(filepath).stem
        self.functions: List[CodeNode] = []
        self.classes: List[CodeNode] = []
        self.imports: List[Dict[str, Any]] = []
        self.calls: List[Dict[str, str]] = []
        self.inheritances: List[Dict[str, str]] = []
        self._current_scope: List[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """访问函数定义"""
        name = ".".join(self._current_scope + [node.name])
        docstring = ast.get_docstring(node)
        self.functions.append(CodeNode(
            name=name,
            type="function",
            file=self.filepath,
            line=node.lineno,
            docstring=docstring,
        ))
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
        self.classes.append(CodeNode(
            name=name,
            type="class",
            file=self.filepath,
            line=node.lineno,
            docstring=docstring,
        ))
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
                "level": 0,
            })

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """访问 from ... import 语句"""
        module = node.module or ""
        level = node.level or 0
        import_type = "relative" if level > 0 else "absolute"
        for alias in (node.names or []):
            self.imports.append({
                "module": module,
                "name": alias.name,
                "alias": alias.asname or alias.name,
                "type": import_type,
                "level": level,
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



# ==============================================================================
# 代码图谱分析器
# ==============================================================================

# 需要跳过的目录
_SKIP_DIRS = {"__pycache__", ".venv", "venv", "node_modules", ".git", ".tox", "dist", "build", "egg-info"}


class CodeGraphAnalyzer:
    """Python 代码图谱分析器
    
    基于 AST 解析 Python 源代码，构建代码结构的图表示。
    支持调用图、导入图、继承图的构建和查询。
    """

    def __init__(self):
        self.graph = CodeGraph()
        self._file_modules: Dict[str, str] = {}  # filepath -> module_name
        self._symbol_index: Dict[str, List[CodeNode]] = {}  # symbol_name -> nodes

    def analyze_file(self, filepath: str) -> Optional[CodeNode]:
        """解析单个 Python 文件，提取所有函数、类、导入
        
        Args:
            filepath: Python 文件路径
            
        Returns:
            模块节点，解析失败则返回 None
        """
        filepath = str(Path(filepath).resolve())
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
        except (IOError, OSError) as e:
            logger.warning(f"无法读取文件 {filepath}: {e}")
            return None

        try:
            tree = ast.parse(source, filename=filepath)
        except SyntaxError as e:
            logger.warning(f"语法错误，跳过文件 {filepath}: {e}")
            return None

        # 创建模块节点
        module_name = Path(filepath).stem
        module_docstring = ast.get_docstring(tree)
        module_node = CodeNode(
            name=module_name,
            type="module",
            file=filepath,
            line=1,
            docstring=module_docstring,
        )
        self.graph.add_node(module_node)
        self._file_modules[filepath] = module_name

        # 使用 AST 访问器提取信息
        visitor = _ASTVisitor(filepath)
        visitor.visit(tree)

        # 添加函数节点
        for func_node in visitor.functions:
            self.graph.add_node(func_node)
            self._index_symbol(func_node)

        # 添加类节点
        for class_node in visitor.classes:
            self.graph.add_node(class_node)
            self._index_symbol(class_node)

        # 存储调用信息（稍后构建调用图时使用）
        for call_info in visitor.calls:
            self.graph.add_edge(CodeEdge(
                source=call_info["caller"],
                target=call_info["callee"],
                type="calls",
                source_file=filepath,
            ))

        # 存储导入信息
        for imp in visitor.imports:
            self.graph.add_edge(CodeEdge(
                source=module_name,
                target=imp["module"] if imp["module"] else imp["name"],
                type="imports",
                source_file=filepath,
            ))

        # 存储继承信息
        for inh in visitor.inheritances:
            self.graph.add_edge(CodeEdge(
                source=inh["child"],
                target=inh["parent"],
                type="inherits",
                source_file=filepath,
            ))

        logger.debug(f"已分析文件: {filepath} "
                     f"(函数: {len(visitor.functions)}, "
                     f"类: {len(visitor.classes)}, "
                     f"导入: {len(visitor.imports)})")
        return module_node

    def analyze_directory(self, directory: str, pattern: str = "**/*.py") -> int:
        """递归分析整个目录
        
        Args:
            directory: 目录路径
            pattern: 文件匹配模式，默认为所有 Python 文件
            
        Returns:
            成功分析的文件数量
        """
        directory = Path(directory).resolve()
        count = 0

        for filepath in directory.glob(pattern):
            # 跳过特定目录
            parts = filepath.parts
            if any(skip in parts for skip in _SKIP_DIRS):
                continue

            if filepath.is_file():
                result = self.analyze_file(str(filepath))
                if result is not None:
                    count += 1

        logger.info(f"目录分析完成: {directory}, 共分析 {count} 个文件")
        return count

    def build_call_graph(self) -> List[CodeEdge]:
        """构建函数调用关系图
        
        Returns:
            调用关系边列表
        """
        return self.graph.get_edges_by_type("calls")

    def build_import_graph(self) -> List[CodeEdge]:
        """构建模块导入关系图
        
        Returns:
            导入关系边列表
        """
        return self.graph.get_edges_by_type("imports")

    def build_inheritance_graph(self) -> List[CodeEdge]:
        """构建类继承关系图
        
        Returns:
            继承关系边列表
        """
        return self.graph.get_edges_by_type("inherits")

    # ==========================================================================
    # 查询方法
    # ==========================================================================

    def get_callers(self, func_name: str) -> List[str]:
        """谁调用了这个函数
        
        Args:
            func_name: 函数名
            
        Returns:
            调用者名称列表
        """
        callers = set()
        for edge in self.graph.edges:
            if edge.type == "calls" and edge.target == func_name:
                callers.add(edge.source)
            # 支持部分匹配（如搜索 "foo" 也能匹配 "module.foo"）
            elif edge.type == "calls" and edge.target.endswith(f".{func_name}"):
                callers.add(edge.source)
        return sorted(callers)

    def get_callees(self, func_name: str) -> List[str]:
        """这个函数调用了谁
        
        Args:
            func_name: 函数名
            
        Returns:
            被调用者名称列表
        """
        callees = set()
        for edge in self.graph.edges:
            if edge.type == "calls" and edge.source == func_name:
                callees.add(edge.target)
            elif edge.type == "calls" and edge.source.endswith(f".{func_name}"):
                callees.add(edge.target)
        return sorted(callees)

    def get_dependents(self, module: str) -> List[str]:
        """谁依赖了这个模块
        
        Args:
            module: 模块名
            
        Returns:
            依赖此模块的模块名列表
        """
        dependents = set()
        for edge in self.graph.edges:
            if edge.type == "imports" and (
                edge.target == module or edge.target.startswith(f"{module}.")
            ):
                dependents.add(edge.source)
        return sorted(dependents)

    def get_dependencies(self, module: str) -> List[str]:
        """这个模块依赖谁
        
        Args:
            module: 模块名
            
        Returns:
            此模块依赖的模块名列表
        """
        dependencies = set()
        for edge in self.graph.edges:
            if edge.type == "imports" and edge.source == module:
                dependencies.add(edge.target)
        return sorted(dependencies)

    def get_impact(self, symbol_name: str) -> Dict[str, Set[str]]:
        """修改这个符号会影响哪些文件（递归向上追溯）
        
        Args:
            symbol_name: 符号名
            
        Returns:
            {"files": 受影响文件集合, "symbols": 受影响符号集合}
        """
        affected_files: Set[str] = set()
        affected_symbols: Set[str] = set()
        visited: Set[str] = set()

        def _trace_impact(name: str):
            if name in visited:
                return
            visited.add(name)

            # 查找所有引用此符号的边
            for edge in self.graph.edges:
                if edge.target == name or edge.target.endswith(f".{name}"):
                    affected_symbols.add(edge.source)
                    if edge.source_file:
                        affected_files.add(edge.source_file)
                    # 递归追溯
                    _trace_impact(edge.source)

        _trace_impact(symbol_name)
        return {"files": affected_files, "symbols": affected_symbols}

    def get_symbol_at(self, file: str, line: int) -> Optional[CodeNode]:
        """获取某行的符号信息
        
        Args:
            file: 文件路径
            line: 行号
            
        Returns:
            该行所在的最近符号节点
        """
        file = str(Path(file).resolve())
        best_match: Optional[CodeNode] = None
        best_distance = float("inf")

        for node in self.graph.nodes.values():
            if node.file == file and node.type != "module":
                if node.line <= line:
                    distance = line - node.line
                    if distance < best_distance:
                        best_distance = distance
                        best_match = node

        return best_match

    def search_symbols(self, query: str) -> List[CodeNode]:
        """模糊搜索符号名
        
        Args:
            query: 搜索关键字（支持正则表达式）
            
        Returns:
            匹配的节点列表
        """
        results = []
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            # 如果正则无效，退回到简单子串匹配
            pattern = None

        for node in self.graph.nodes.values():
            if node.type == "module":
                continue
            if pattern:
                if pattern.search(node.name):
                    results.append(node)
            else:
                if query.lower() in node.name.lower():
                    results.append(node)

        return results

    # ==========================================================================
    # 可视化
    # ==========================================================================

    def to_dot(self) -> str:
        """导出为 Graphviz DOT 格式
        
        Returns:
            DOT 格式字符串
        """
        lines = ["digraph CodeGraph {"]
        lines.append("    rankdir=LR;")
        lines.append("    node [shape=box, style=filled];")
        lines.append("")

        # 节点样式
        colors = {
            "function": "#a8d8ea",
            "class": "#ffcfdf",
            "module": "#fefdca",
        }

        # 添加节点
        for key, node in self.graph.nodes.items():
            safe_key = key.replace("::", "_").replace(".", "_").replace("/", "_")
            color = colors.get(node.type, "#ffffff")
            label = f"{node.name}\\n({node.type})"
            lines.append(f'    "{safe_key}" [label="{label}", fillcolor="{color}"];')

        lines.append("")

        # 边样式
        edge_styles = {
            "calls": "solid",
            "imports": "dashed",
            "inherits": "bold",
            "uses": "dotted",
        }
        edge_colors = {
            "calls": "#333333",
            "imports": "#0066cc",
            "inherits": "#cc0000",
            "uses": "#009900",
        }

        # 添加边
        for edge in self.graph.edges:
            src = edge.source.replace(".", "_").replace("/", "_")
            tgt = edge.target.replace(".", "_").replace("/", "_")
            style = edge_styles.get(edge.type, "solid")
            color = edge_colors.get(edge.type, "#000000")
            lines.append(f'    "{src}" -> "{tgt}" [style={style}, color="{color}", label="{edge.type}"];')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """导出为 Mermaid 图表格式
        
        Returns:
            Mermaid 格式字符串
        """
        lines = ["graph LR"]

        # 节点形状
        node_shapes = {
            "function": ("([", "])"),  # 圆角矩形
            "class": ("[[", "]]"),     # 双框
            "module": ("[", "]"),      # 矩形
        }

        # 添加节点
        seen_nodes: Set[str] = set()
        for key, node in self.graph.nodes.items():
            if node.type == "module":
                continue
            safe_id = node.name.replace(".", "_").replace(" ", "_")
            if safe_id in seen_nodes:
                continue
            seen_nodes.add(safe_id)
            left, right = node_shapes.get(node.type, ("[", "]"))
            lines.append(f"    {safe_id}{left}{node.name}{right}")

        # 边样式
        edge_arrows = {
            "calls": "-->",
            "imports": "-.->",
            "inherits": "==>",
            "uses": "-->",
        }

        # 添加边
        for edge in self.graph.edges:
            src = edge.source.replace(".", "_").replace(" ", "_")
            tgt = edge.target.replace(".", "_").replace(" ", "_")
            arrow = edge_arrows.get(edge.type, "-->")
            lines.append(f"    {src} {arrow}|{edge.type}| {tgt}")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息
        
        Returns:
            包含文件数、函数数、类数、边数等信息的字典
        """
        modules = self.graph.get_nodes_by_type("module")
        functions = self.graph.get_nodes_by_type("function")
        classes = self.graph.get_nodes_by_type("class")

        call_edges = self.graph.get_edges_by_type("calls")
        import_edges = self.graph.get_edges_by_type("imports")
        inherit_edges = self.graph.get_edges_by_type("inherits")

        return {
            "files": len(modules),
            "functions": len(functions),
            "classes": len(classes),
            "total_nodes": len(self.graph.nodes),
            "call_edges": len(call_edges),
            "import_edges": len(import_edges),
            "inherit_edges": len(inherit_edges),
            "total_edges": len(self.graph.edges),
        }

    # ==========================================================================
    # 内部辅助方法
    # ==========================================================================

    def _index_symbol(self, node: CodeNode):
        """索引符号用于快速查找"""
        name = node.name.split(".")[-1]  # 取最后一段作为短名
        if name not in self._symbol_index:
            self._symbol_index[name] = []
        self._symbol_index[name].append(node)



# ==============================================================================
# LangChain 工具集成
# ==============================================================================

# 全局分析器实例（懒初始化）
_global_analyzer: Optional[CodeGraphAnalyzer] = None


def _get_analyzer() -> CodeGraphAnalyzer:
    """获取全局分析器实例"""
    global _global_analyzer
    if _global_analyzer is None:
        _global_analyzer = CodeGraphAnalyzer()
    return _global_analyzer


def code_graph_query_tool(query_type: str, symbol_name: str) -> str:
    """查询代码图谱
    
    Args:
        query_type: 查询类型，支持:
            - "callers": 谁调用了这个函数
            - "callees": 这个函数调用了谁
            - "dependents": 谁依赖了这个模块
            - "dependencies": 这个模块依赖谁
            - "search": 搜索符号
            - "stats": 获取统计信息
        symbol_name: 符号名称
        
    Returns:
        查询结果的字符串表示
    """
    analyzer = _get_analyzer()

    try:
        if query_type == "callers":
            results = analyzer.get_callers(symbol_name)
            if not results:
                return f"没有找到调用 '{symbol_name}' 的函数"
            return f"调用 '{symbol_name}' 的函数:\n" + "\n".join(f"  - {r}" for r in results)

        elif query_type == "callees":
            results = analyzer.get_callees(symbol_name)
            if not results:
                return f"'{symbol_name}' 没有调用其他函数"
            return f"'{symbol_name}' 调用的函数:\n" + "\n".join(f"  - {r}" for r in results)

        elif query_type == "dependents":
            results = analyzer.get_dependents(symbol_name)
            if not results:
                return f"没有模块依赖 '{symbol_name}'"
            return f"依赖 '{symbol_name}' 的模块:\n" + "\n".join(f"  - {r}" for r in results)

        elif query_type == "dependencies":
            results = analyzer.get_dependencies(symbol_name)
            if not results:
                return f"'{symbol_name}' 没有依赖其他模块"
            return f"'{symbol_name}' 依赖的模块:\n" + "\n".join(f"  - {r}" for r in results)

        elif query_type == "search":
            nodes = analyzer.search_symbols(symbol_name)
            if not nodes:
                return f"没有找到匹配 '{symbol_name}' 的符号"
            lines = [f"匹配 '{symbol_name}' 的符号:"]
            for node in nodes[:20]:  # 限制结果数量
                lines.append(f"  - {node.name} ({node.type}) @ {node.file}:{node.line}")
            if len(nodes) > 20:
                lines.append(f"  ... 还有 {len(nodes) - 20} 个结果")
            return "\n".join(lines)

        elif query_type == "stats":
            stats = analyzer.get_stats()
            lines = ["代码图谱统计:"]
            lines.append(f"  文件数: {stats['files']}")
            lines.append(f"  函数数: {stats['functions']}")
            lines.append(f"  类数: {stats['classes']}")
            lines.append(f"  总节点数: {stats['total_nodes']}")
            lines.append(f"  调用边数: {stats['call_edges']}")
            lines.append(f"  导入边数: {stats['import_edges']}")
            lines.append(f"  继承边数: {stats['inherit_edges']}")
            lines.append(f"  总边数: {stats['total_edges']}")
            return "\n".join(lines)

        else:
            return (f"不支持的查询类型: '{query_type}'。"
                    f"支持: callers, callees, dependents, dependencies, search, stats")

    except Exception as e:
        logger.error(f"代码图谱查询出错: {e}")
        return f"查询出错: {str(e)}"


def code_graph_impact_tool(symbol_name: str) -> str:
    """影响分析 - 修改某个符号会影响哪些文件和函数
    
    Args:
        symbol_name: 要分析影响的符号名称
        
    Returns:
        受影响文件和函数的列表
    """
    analyzer = _get_analyzer()

    try:
        impact = analyzer.get_impact(symbol_name)
        affected_files = impact["files"]
        affected_symbols = impact["symbols"]

        if not affected_files and not affected_symbols:
            return f"修改 '{symbol_name}' 不会影响其他已分析的代码"

        lines = [f"修改 '{symbol_name}' 的影响分析:"]
        
        if affected_files:
            lines.append(f"\n受影响的文件 ({len(affected_files)}):")
            for f in sorted(affected_files):
                lines.append(f"  - {f}")

        if affected_symbols:
            lines.append(f"\n受影响的符号 ({len(affected_symbols)}):")
            for s in sorted(affected_symbols):
                lines.append(f"  - {s}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"影响分析出错: {e}")
        return f"影响分析出错: {str(e)}"


def register_code_graph_tools(registry) -> None:
    """注册代码图谱工具到工具注册表
    
    Args:
        registry: 工具注册表对象，需要支持 register() 方法
    """
    tools = [
        {
            "name": "code_graph_query",
            "description": (
                "查询代码图谱。支持查询类型: callers(谁调用了该函数), "
                "callees(该函数调用了谁), dependents(谁依赖该模块), "
                "dependencies(该模块依赖谁), search(搜索符号), stats(统计信息)"
            ),
            "parameters": {
                "query_type": {
                    "type": "string",
                    "description": "查询类型: callers/callees/dependents/dependencies/search/stats",
                    "enum": ["callers", "callees", "dependents", "dependencies", "search", "stats"],
                },
                "symbol_name": {
                    "type": "string",
                    "description": "要查询的符号名称",
                },
            },
            "required": ["query_type", "symbol_name"],
            "func": code_graph_query_tool,
        },
        {
            "name": "code_graph_impact",
            "description": (
                "代码影响分析。输入一个符号名称，返回修改该符号会影响哪些文件和函数。"
                "通过递归追溯调用链和依赖关系，找出所有受影响的代码。"
            ),
            "parameters": {
                "symbol_name": {
                    "type": "string",
                    "description": "要分析影响的符号名称（函数名、类名或模块名）",
                },
            },
            "required": ["symbol_name"],
            "func": code_graph_impact_tool,
        },
    ]

    for tool_def in tools:
        try:
            registry.register(tool_def)
            logger.info(f"已注册代码图谱工具: {tool_def['name']}")
        except Exception as e:
            logger.warning(f"注册工具 {tool_def['name']} 失败: {e}")


# ==============================================================================
# 公开 API
# ==============================================================================

__all__ = [
    # 数据结构
    "CodeNode",
    "CodeEdge",
    "CodeGraph",
    # 分析器
    "CodeGraphAnalyzer",
    # 工具函数
    "code_graph_query_tool",
    "code_graph_impact_tool",
    "register_code_graph_tools",
]
