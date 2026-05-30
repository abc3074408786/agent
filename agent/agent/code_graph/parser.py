"""
多语言代码解析器 - 基于 tree-sitter 的统一符号提取接口

支持语言:
- Python (优先用 ast 模块, 更精确; tree-sitter 作为备选)
- TypeScript / JavaScript
- Go
- Rust
- Java
- Ruby
- Swift
- C/C++

安装依赖:
    pip install tree-sitter tree-sitter-python tree-sitter-javascript \
        tree-sitter-typescript tree-sitter-go tree-sitter-rust \
        tree-sitter-java tree-sitter-ruby tree-sitter-swift

如果 tree-sitter 未安装，非 Python 文件将使用基于正则的简单解析器（提取精度较低）。
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

logger = logging.getLogger(__name__)



# ==============================================================================
# tree-sitter 可用性检测
# ==============================================================================

HAS_TREE_SITTER = False
_TS_LANGUAGES: Dict[str, Any] = {}

try:
    import tree_sitter
    HAS_TREE_SITTER = True
    logger.info("tree-sitter 已加载")
except ImportError:
    logger.info(
        "tree-sitter 未安装，非 Python 文件将使用正则解析器。"
        "完整支持请运行: pip install tree-sitter tree-sitter-python "
        "tree-sitter-javascript tree-sitter-typescript tree-sitter-go"
    )


def _load_ts_language(lang_name: str):
    """懒加载 tree-sitter 语言 grammar"""
    if lang_name in _TS_LANGUAGES:
        return _TS_LANGUAGES[lang_name]

    if not HAS_TREE_SITTER:
        return None

    try:
        if lang_name == "python":
            import tree_sitter_python as tsp
            lang = tree_sitter.Language(tsp.language())
        elif lang_name == "javascript":
            import tree_sitter_javascript as tsjs
            lang = tree_sitter.Language(tsjs.language())
        elif lang_name == "typescript":
            import tree_sitter_typescript as tsts
            lang = tree_sitter.Language(tsts.language_typescript())
        elif lang_name == "tsx":
            import tree_sitter_typescript as tsts
            lang = tree_sitter.Language(tsts.language_tsx())
        elif lang_name == "go":
            import tree_sitter_go as tsgo
            lang = tree_sitter.Language(tsgo.language())
        elif lang_name == "rust":
            import tree_sitter_rust as tsrust
            lang = tree_sitter.Language(tsrust.language())
        elif lang_name == "java":
            import tree_sitter_java as tsjava
            lang = tree_sitter.Language(tsjava.language())
        elif lang_name == "ruby":
            import tree_sitter_ruby as tsruby
            lang = tree_sitter.Language(tsruby.language())
        elif lang_name == "swift":
            import tree_sitter_swift as tsswift
            lang = tree_sitter.Language(tsswift.language())
        elif lang_name == "c":
            import tree_sitter_c as tsc
            lang = tree_sitter.Language(tsc.language())
        elif lang_name == "cpp":
            import tree_sitter_cpp as tscpp
            lang = tree_sitter.Language(tscpp.language())
        else:
            return None

        _TS_LANGUAGES[lang_name] = lang
        logger.debug(f"已加载 tree-sitter 语言: {lang_name}")
        return lang
    except (ImportError, Exception) as e:
        logger.debug(f"tree-sitter 语言 {lang_name} 不可用: {e}")
        _TS_LANGUAGES[lang_name] = None
        return None



# ==============================================================================
# 统一数据结构
# ==============================================================================

@dataclass
class ParsedSymbol:
    """从源代码中提取的符号"""
    name: str
    qualified_name: str
    type: str            # function / class / module / method / interface
    line: int
    end_line: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class ParsedEdge:
    """从源代码中提取的关系"""
    source_name: str
    target_name: str
    type: str            # calls / imports / inherits / implements


@dataclass
class ParseResult:
    """单个文件的解析结果"""
    language: str
    filepath: str
    symbols: List[ParsedSymbol] = field(default_factory=list)
    edges: List[ParsedEdge] = field(default_factory=list)
    success: bool = True
    error: Optional[str] = None


# ==============================================================================
# 文件扩展名 → 语言映射
# ==============================================================================

EXTENSION_MAP: Dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".swift": "swift",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
}

SUPPORTED_EXTENSIONS = set(EXTENSION_MAP.keys())


def detect_language(filepath: str) -> Optional[str]:
    """根据文件扩展名检测编程语言"""
    ext = Path(filepath).suffix.lower()
    return EXTENSION_MAP.get(ext)



# ==============================================================================
# tree-sitter 查询模式（每种语言的 AST 节点类型）
# ==============================================================================

# tree-sitter query patterns for symbol extraction
_TS_QUERIES: Dict[str, Dict[str, str]] = {
    "javascript": {
        "functions": """
            (function_declaration name: (identifier) @name) @func
            (method_definition name: (property_identifier) @name) @method
            (arrow_function) @arrow
            (variable_declarator
                name: (identifier) @name
                value: [(arrow_function) (function_expression)]) @func_var
        """,
        "classes": """
            (class_declaration name: (identifier) @name) @class
        """,
        "imports": """
            (import_statement source: (string) @source) @import
            (import_statement
                (import_clause
                    (named_imports (import_specifier name: (identifier) @name)))) @named_import
        """,
    },
    "typescript": {
        "functions": """
            (function_declaration name: (identifier) @name) @func
            (method_definition name: (property_identifier) @name) @method
            (arrow_function) @arrow
            (variable_declarator
                name: (identifier) @name
                value: [(arrow_function) (function_expression)]) @func_var
        """,
        "classes": """
            (class_declaration name: (type_identifier) @name) @class
            (interface_declaration name: (type_identifier) @name) @interface
            (type_alias_declaration name: (type_identifier) @name) @type_alias
        """,
        "imports": """
            (import_statement source: (string) @source) @import
        """,
    },
    "go": {
        "functions": """
            (function_declaration name: (identifier) @name) @func
            (method_declaration
                name: (field_identifier) @name
                receiver: (parameter_list
                    (parameter_declaration type: (_) @receiver_type))) @method
        """,
        "classes": """
            (type_declaration
                (type_spec name: (type_identifier) @name
                    type: (struct_type))) @struct
            (type_declaration
                (type_spec name: (type_identifier) @name
                    type: (interface_type))) @interface
        """,
        "imports": """
            (import_spec path: (interpreted_string_literal) @path) @import
        """,
    },
    "rust": {
        "functions": """
            (function_item name: (identifier) @name) @func
            (impl_item
                (declaration_list
                    (function_item name: (identifier) @name) @method))
        """,
        "classes": """
            (struct_item name: (type_identifier) @name) @struct
            (enum_item name: (type_identifier) @name) @enum
            (trait_item name: (type_identifier) @name) @trait
            (impl_item type: (type_identifier) @name) @impl
        """,
        "imports": """
            (use_declaration argument: (_) @path) @import
        """,
    },
    "java": {
        "functions": """
            (method_declaration name: (identifier) @name) @method
            (constructor_declaration name: (identifier) @name) @constructor
        """,
        "classes": """
            (class_declaration name: (identifier) @name) @class
            (interface_declaration name: (identifier) @name) @interface
            (enum_declaration name: (identifier) @name) @enum
        """,
        "imports": """
            (import_declaration (scoped_identifier) @path) @import
        """,
    },
}

# tsx 复用 typescript 的 queries
_TS_QUERIES["tsx"] = _TS_QUERIES["typescript"]



# ==============================================================================
# tree-sitter 解析器
# ==============================================================================

class TreeSitterParser:
    """tree-sitter 统一解析器"""

    def parse_file(self, filepath: str, source: bytes, language: str) -> ParseResult:
        """使用 tree-sitter 解析文件"""
        result = ParseResult(language=language, filepath=filepath)

        lang = _load_ts_language(language)
        if lang is None:
            result.success = False
            result.error = f"tree-sitter language '{language}' not available"
            return result

        try:
            parser = tree_sitter.Parser(lang)
            tree = parser.parse(source)
            root = tree.root_node

            module_name = Path(filepath).stem
            self._extract_symbols(root, source, filepath, module_name, language, result)
            return result
        except Exception as e:
            result.success = False
            result.error = str(e)
            return result

    def _extract_symbols(
        self, root, source: bytes, filepath: str,
        module_name: str, language: str, result: ParseResult
    ):
        """从 AST 中提取符号和关系"""
        # 使用递归遍历而非 query (更通用)
        if language in ("javascript", "typescript", "tsx"):
            self._extract_js_ts(root, source, filepath, module_name, result)
        elif language == "go":
            self._extract_go(root, source, filepath, module_name, result)
        elif language == "rust":
            self._extract_rust(root, source, filepath, module_name, result)
        elif language == "java":
            self._extract_java(root, source, filepath, module_name, result)
        else:
            # 通用提取（基于节点类型名称猜测）
            self._extract_generic(root, source, filepath, module_name, result)

    def _node_text(self, node, source: bytes) -> str:
        """获取节点的文本内容"""
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _find_children(self, node, type_name: str) -> list:
        """查找特定类型的子节点"""
        return [c for c in node.children if c.type == type_name]

    def _find_child(self, node, type_name: str):
        """查找第一个特定类型的子节点"""
        for c in node.children:
            if c.type == type_name:
                return c
        return None



    # ──── JavaScript / TypeScript ────

    def _extract_js_ts(self, root, source: bytes, filepath: str,
                       module_name: str, result: ParseResult):
        """提取 JS/TS 符号"""
        self._walk_js_ts(root, source, filepath, module_name, [], result)

    def _walk_js_ts(self, node, source: bytes, filepath: str,
                    module_name: str, scope: list, result: ParseResult):
        """递归遍历 JS/TS AST"""
        for child in node.children:
            # 函数声明
            if child.type in ("function_declaration", "generator_function_declaration"):
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    params = self._find_child(child, "formal_parameters")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))
                    # 递归进入函数体
                    body = self._find_child(child, "statement_block")
                    if body:
                        self._extract_calls_js(body, source, qname, result)

            # 类声明
            elif child.type == "class_declaration":
                name_node = (self._find_child(child, "type_identifier")
                            or self._find_child(child, "identifier"))
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))
                    # 提取继承
                    heritage = self._find_child(child, "class_heritage")
                    if heritage:
                        for hc in heritage.children:
                            if hc.type == "identifier" or hc.type == "type_identifier":
                                parent_name = self._node_text(hc, source)
                                result.edges.append(ParsedEdge(
                                    source_name=qname, target_name=parent_name,
                                    type="inherits",
                                ))
                    # 递归进入类体
                    body = self._find_child(child, "class_body")
                    if body:
                        self._walk_js_ts(body, source, filepath,
                                        module_name, scope + [name], result)

            # 方法定义
            elif child.type == "method_definition":
                name_node = self._find_child(child, "property_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    params = self._find_child(child, "formal_parameters")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            # 接口声明 (TypeScript)
            elif child.type == "interface_declaration":
                name_node = self._find_child(child, "type_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="interface",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            # 类型别名 (TypeScript)
            elif child.type == "type_alias_declaration":
                name_node = self._find_child(child, "type_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            # import 语句
            elif child.type == "import_statement":
                source_node = self._find_child(child, "string")
                if source_node:
                    import_path = self._node_text(source_node, source).strip("'\"")
                    result.edges.append(ParsedEdge(
                        source_name=module_name, target_name=import_path,
                        type="imports",
                    ))

            # export 语句中的声明
            elif child.type in ("export_statement", "lexical_declaration"):
                self._walk_js_ts(child, source, filepath, module_name, scope, result)

            # 变量声明中的箭头函数
            elif child.type == "variable_declarator":
                name_node = self._find_child(child, "identifier")
                value_node = (self._find_child(child, "arrow_function")
                             or self._find_child(child, "function_expression"))
                if name_node and value_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    params = self._find_child(value_node, "formal_parameters")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            else:
                # 递归其他节点
                if child.child_count > 0:
                    self._walk_js_ts(child, source, filepath, module_name, scope, result)

    def _extract_calls_js(self, node, source: bytes, caller: str, result: ParseResult):
        """提取 JS/TS 中的函数调用"""
        for child in node.children:
            if child.type == "call_expression":
                func_node = child.children[0] if child.children else None
                if func_node:
                    callee = self._node_text(func_node, source)
                    # 过滤掉太长的（通常是链式调用）
                    if len(callee) < 60 and "\n" not in callee:
                        result.edges.append(ParsedEdge(
                            source_name=caller, target_name=callee, type="calls",
                        ))
            if child.child_count > 0:
                self._extract_calls_js(child, source, caller, result)



    # ──── Go ────

    def _extract_go(self, root, source: bytes, filepath: str,
                    module_name: str, result: ParseResult):
        """提取 Go 符号"""
        for child in root.children:
            # 函数声明
            if child.type == "function_declaration":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    params = self._find_child(child, "parameter_list")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=name, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            # 方法声明 (带 receiver)
            elif child.type == "method_declaration":
                name_node = self._find_child(child, "field_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    # 尝试获取 receiver 类型
                    receiver_list = self._find_child(child, "parameter_list")
                    receiver_type = ""
                    if receiver_list and receiver_list.children:
                        for param in receiver_list.children:
                            if param.type == "parameter_declaration":
                                type_node = param.children[-1] if param.children else None
                                if type_node:
                                    receiver_type = self._node_text(type_node, source)
                                    receiver_type = receiver_type.strip("*")
                                    break
                    qname = f"{receiver_type}.{name}" if receiver_type else name
                    params_nodes = [c for c in child.children if c.type == "parameter_list"]
                    sig = ""
                    if len(params_nodes) > 1:
                        sig = self._node_text(params_nodes[1], source)
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            # 类型声明 (struct / interface)
            elif child.type == "type_declaration":
                for spec in child.children:
                    if spec.type == "type_spec":
                        name_node = self._find_child(spec, "type_identifier")
                        type_body = spec.children[-1] if spec.children else None
                        if name_node:
                            name = self._node_text(name_node, source)
                            sym_type = "class"
                            if type_body and type_body.type == "interface_type":
                                sym_type = "interface"
                            result.symbols.append(ParsedSymbol(
                                name=name, qualified_name=name, type=sym_type,
                                line=spec.start_point[0] + 1,
                                end_line=spec.end_point[0] + 1,
                            ))

            # import 声明
            elif child.type == "import_declaration":
                for spec in self._walk_find(child, "import_spec"):
                    path_node = self._find_child(spec, "interpreted_string_literal")
                    if path_node:
                        import_path = self._node_text(path_node, source).strip('"')
                        result.edges.append(ParsedEdge(
                            source_name=module_name, target_name=import_path,
                            type="imports",
                        ))

    def _walk_find(self, node, type_name: str) -> list:
        """递归查找所有指定类型的节点"""
        found = []
        if node.type == type_name:
            found.append(node)
        for child in node.children:
            found.extend(self._walk_find(child, type_name))
        return found



    # ──── Rust ────

    def _extract_rust(self, root, source: bytes, filepath: str,
                      module_name: str, result: ParseResult):
        """提取 Rust 符号"""
        self._walk_rust(root, source, filepath, module_name, [], result)

    def _walk_rust(self, node, source: bytes, filepath: str,
                   module_name: str, scope: list, result: ParseResult):
        """递归遍历 Rust AST"""
        for child in node.children:
            if child.type == "function_item":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    params = self._find_child(child, "parameters")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            elif child.type == "struct_item":
                name_node = self._find_child(child, "type_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=name, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            elif child.type == "enum_item":
                name_node = self._find_child(child, "type_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=name, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            elif child.type == "trait_item":
                name_node = self._find_child(child, "type_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=name, type="interface",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            elif child.type == "impl_item":
                type_node = self._find_child(child, "type_identifier")
                if type_node:
                    impl_name = self._node_text(type_node, source)
                    # 递归进入 impl 块提取方法
                    decl_list = self._find_child(child, "declaration_list")
                    if decl_list:
                        self._walk_rust(decl_list, source, filepath,
                                       module_name, [impl_name], result)

            elif child.type == "use_declaration":
                arg = child.children[1] if len(child.children) > 1 else None
                if arg:
                    path = self._node_text(arg, source)
                    result.edges.append(ParsedEdge(
                        source_name=module_name, target_name=path, type="imports",
                    ))

            elif child.child_count > 0 and child.type not in ("string_literal", "comment"):
                self._walk_rust(child, source, filepath, module_name, scope, result)



    # ──── Java ────

    def _extract_java(self, root, source: bytes, filepath: str,
                      module_name: str, result: ParseResult):
        """提取 Java 符号"""
        self._walk_java(root, source, filepath, module_name, [], result)

    def _walk_java(self, node, source: bytes, filepath: str,
                   module_name: str, scope: list, result: ParseResult):
        """递归遍历 Java AST"""
        for child in node.children:
            if child.type == "class_declaration":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))
                    # 继承
                    superclass = self._find_child(child, "superclass")
                    if superclass:
                        for sc in superclass.children:
                            if sc.type == "type_identifier":
                                result.edges.append(ParsedEdge(
                                    source_name=qname,
                                    target_name=self._node_text(sc, source),
                                    type="inherits",
                                ))
                    # 接口实现
                    interfaces = self._find_child(child, "super_interfaces")
                    if interfaces:
                        for iface in self._walk_find(interfaces, "type_identifier"):
                            result.edges.append(ParsedEdge(
                                source_name=qname,
                                target_name=self._node_text(iface, source),
                                type="implements",
                            ))
                    # 递归类体
                    body = self._find_child(child, "class_body")
                    if body:
                        self._walk_java(body, source, filepath,
                                       module_name, scope + [name], result)

            elif child.type == "interface_declaration":
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="interface",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            elif child.type in ("method_declaration", "constructor_declaration"):
                name_node = self._find_child(child, "identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    params = self._find_child(child, "formal_parameters")
                    sig = self._node_text(params, source) if params else "()"
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        signature=sig,
                    ))

            elif child.type == "import_declaration":
                scoped = self._find_child(child, "scoped_identifier")
                if scoped:
                    path = self._node_text(scoped, source)
                    result.edges.append(ParsedEdge(
                        source_name=module_name, target_name=path, type="imports",
                    ))

            elif child.type == "program" or child.child_count > 0:
                self._walk_java(child, source, filepath, module_name, scope, result)

    # ──── 通用提取 ────

    def _extract_generic(self, root, source: bytes, filepath: str,
                         module_name: str, result: ParseResult):
        """通用提取（遍历 AST 查找常见节点类型）"""
        self._walk_generic(root, source, module_name, [], result)

    def _walk_generic(self, node, source: bytes, module_name: str,
                      scope: list, result: ParseResult):
        """递归通用遍历"""
        for child in node.children:
            # 基于节点类型名推断
            if "function" in child.type or "method" in child.type:
                name_node = self._find_child(child, "identifier")
                if not name_node:
                    name_node = self._find_child(child, "field_identifier")
                if name_node:
                    name = self._node_text(name_node, source)
                    qname = ".".join(scope + [name])
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=qname, type="function",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))
            elif "class" in child.type or "struct" in child.type:
                name_node = (self._find_child(child, "type_identifier")
                            or self._find_child(child, "identifier"))
                if name_node:
                    name = self._node_text(name_node, source)
                    result.symbols.append(ParsedSymbol(
                        name=name, qualified_name=name, type="class",
                        line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                    ))

            if child.child_count > 0:
                self._walk_generic(child, source, module_name, scope, result)



# ==============================================================================
# 正则回退解析器（tree-sitter 不可用时的降级方案）
# ==============================================================================

class RegexParser:
    """基于正则表达式的简单解析器 (降级方案)
    
    当 tree-sitter 未安装时，使用正则表达式提取基本的函数/类定义。
    精度不如 tree-sitter，但无需额外依赖。
    """

    # 各语言的正则模式
    _PATTERNS: Dict[str, Dict[str, re.Pattern]] = {
        "javascript": {
            "function": re.compile(
                r"(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)",
                re.MULTILINE,
            ),
            "class": re.compile(
                r"(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?",
                re.MULTILINE,
            ),
            "arrow": re.compile(
                r"(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
                re.MULTILINE,
            ),
            "import": re.compile(
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                re.MULTILINE,
            ),
            "method": re.compile(
                r"^\s+(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{",
                re.MULTILINE,
            ),
        },
        "typescript": {},  # 复用 javascript
        "tsx": {},          # 复用 javascript
        "go": {
            "function": re.compile(
                r"^func\s+(\w+)\s*\(([^)]*)\)",
                re.MULTILINE,
            ),
            "method": re.compile(
                r"^func\s+\(\w+\s+\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)",
                re.MULTILINE,
            ),
            "struct": re.compile(
                r"^type\s+(\w+)\s+struct\s*\{",
                re.MULTILINE,
            ),
            "interface": re.compile(
                r"^type\s+(\w+)\s+interface\s*\{",
                re.MULTILINE,
            ),
            "import": re.compile(
                r'"([^"]+)"',
                re.MULTILINE,
            ),
        },
        "rust": {
            "function": re.compile(
                r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(<[^>]*>)?\s*\(([^)]*)\)",
                re.MULTILINE,
            ),
            "struct": re.compile(
                r"(?:pub\s+)?struct\s+(\w+)",
                re.MULTILINE,
            ),
            "enum": re.compile(
                r"(?:pub\s+)?enum\s+(\w+)",
                re.MULTILINE,
            ),
            "trait": re.compile(
                r"(?:pub\s+)?trait\s+(\w+)",
                re.MULTILINE,
            ),
            "impl": re.compile(
                r"impl(?:<[^>]*>)?\s+(\w+)",
                re.MULTILINE,
            ),
            "import": re.compile(
                r"use\s+([^;]+);",
                re.MULTILINE,
            ),
        },
        "java": {
            "class": re.compile(
                r"(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)"
                r"(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?",
                re.MULTILINE,
            ),
            "interface": re.compile(
                r"(?:public\s+)?interface\s+(\w+)",
                re.MULTILINE,
            ),
            "method": re.compile(
                r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(([^)]*)\)",
                re.MULTILINE,
            ),
            "import": re.compile(
                r"import\s+([\w.]+);",
                re.MULTILINE,
            ),
        },
        "ruby": {
            "class": re.compile(r"class\s+(\w+)(?:\s*<\s*(\w+))?", re.MULTILINE),
            "method": re.compile(r"def\s+(\w+[?!]?)(?:\(([^)]*)\))?", re.MULTILINE),
            "import": re.compile(r"require\s+['\"]([^'\"]+)['\"]", re.MULTILINE),
        },
        "swift": {
            "class": re.compile(r"class\s+(\w+)(?:\s*:\s*([^{]+))?", re.MULTILINE),
            "struct": re.compile(r"struct\s+(\w+)", re.MULTILINE),
            "function": re.compile(r"func\s+(\w+)\s*\(([^)]*)\)", re.MULTILINE),
            "import": re.compile(r"import\s+(\w+)", re.MULTILINE),
        },
        "c": {
            "function": re.compile(
                r"^(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(([^)]*)\)\s*\{",
                re.MULTILINE,
            ),
            "struct": re.compile(r"(?:typedef\s+)?struct\s+(\w+)", re.MULTILINE),
        },
        "cpp": {},  # 复用 c
    }

    # 复用规则
    _PATTERNS["typescript"] = _PATTERNS["javascript"]
    _PATTERNS["tsx"] = _PATTERNS["javascript"]
    _PATTERNS["cpp"] = _PATTERNS["c"]

    def parse_file(self, filepath: str, source: str, language: str) -> ParseResult:
        """使用正则解析文件"""
        result = ParseResult(language=language, filepath=filepath)
        module_name = Path(filepath).stem

        patterns = self._PATTERNS.get(language, {})
        if not patterns:
            result.success = False
            result.error = f"No regex patterns for language: {language}"
            return result

        lines = source.split("\n")

        # 提取函数
        for pat_name in ("function", "arrow", "method"):
            pattern = patterns.get(pat_name)
            if not pattern:
                continue
            for match in pattern.finditer(source):
                name = match.group(1)
                line = source[:match.start()].count("\n") + 1
                sig = match.group(2) if match.lastindex >= 2 else ""
                result.symbols.append(ParsedSymbol(
                    name=name,
                    qualified_name=name,
                    type="function",
                    line=line,
                    signature=f"({sig})" if sig else "",
                ))

        # 提取类/结构体
        for pat_name in ("class", "struct", "interface", "enum", "trait"):
            pattern = patterns.get(pat_name)
            if not pattern:
                continue
            for match in pattern.finditer(source):
                name = match.group(1)
                line = source[:match.start()].count("\n") + 1
                sym_type = "interface" if pat_name in ("interface", "trait") else "class"
                result.symbols.append(ParsedSymbol(
                    name=name, qualified_name=name, type=sym_type, line=line,
                ))
                # 继承关系
                if match.lastindex >= 2 and match.group(2):
                    parent = match.group(2).strip()
                    if parent and parent != "{":
                        result.edges.append(ParsedEdge(
                            source_name=name, target_name=parent, type="inherits",
                        ))

        # 提取 Go 方法 (特殊处理)
        if language == "go" and "method" in patterns:
            for match in patterns["method"].finditer(source):
                receiver_type = match.group(1)
                method_name = match.group(2)
                line = source[:match.start()].count("\n") + 1
                result.symbols.append(ParsedSymbol(
                    name=method_name,
                    qualified_name=f"{receiver_type}.{method_name}",
                    type="function",
                    line=line,
                ))

        # 提取导入
        if "import" in patterns:
            for match in patterns["import"].finditer(source):
                import_path = match.group(1)
                result.edges.append(ParsedEdge(
                    source_name=module_name, target_name=import_path, type="imports",
                ))

        return result



# ==============================================================================
# 统一入口
# ==============================================================================

# 全局解析器实例
_ts_parser: Optional[TreeSitterParser] = None
_regex_parser: Optional[RegexParser] = None


def get_parser(language: str) -> Tuple[str, Any]:
    """获取适合指定语言的解析器
    
    Returns:
        (parser_type, parser_instance)
        parser_type: "ast" / "tree-sitter" / "regex"
    """
    global _ts_parser, _regex_parser

    # Python 优先用内置 ast（更精确）
    if language == "python":
        return ("ast", None)

    # 非 Python：尝试 tree-sitter
    if HAS_TREE_SITTER:
        lang = _load_ts_language(language)
        if lang is not None:
            if _ts_parser is None:
                _ts_parser = TreeSitterParser()
            return ("tree-sitter", _ts_parser)

    # 回退到正则
    if _regex_parser is None:
        _regex_parser = RegexParser()
    return ("regex", _regex_parser)


def parse_file(filepath: str) -> ParseResult:
    """解析任意支持的源代码文件
    
    自动根据文件扩展名选择解析器:
    - .py → Python ast 模块
    - .ts/.js/.go/.rs/.java → tree-sitter (如果可用)
    - 回退 → 正则表达式
    
    Args:
        filepath: 源代码文件路径
        
    Returns:
        ParseResult 包含提取的符号和关系
    """
    language = detect_language(filepath)
    if language is None:
        return ParseResult(
            language="unknown", filepath=filepath,
            success=False, error=f"Unsupported file type: {Path(filepath).suffix}"
        )

    # 读取文件
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            source_str = f.read()
    except (IOError, OSError) as e:
        return ParseResult(
            language=language, filepath=filepath,
            success=False, error=f"Cannot read file: {e}"
        )

    parser_type, parser = get_parser(language)

    if parser_type == "ast":
        # Python 用 ast 模块，由 CodeGraphAnalyzer 自己处理
        # 这里返回一个空结果，标记语言为 python
        return ParseResult(language="python", filepath=filepath, success=True)

    elif parser_type == "tree-sitter":
        source_bytes = source_str.encode("utf-8")
        return parser.parse_file(filepath, source_bytes, language)

    elif parser_type == "regex":
        return parser.parse_file(filepath, source_str, language)

    else:
        return ParseResult(
            language=language, filepath=filepath,
            success=False, error="No parser available"
        )


# ==============================================================================
# 公开 API
# ==============================================================================

__all__ = [
    "HAS_TREE_SITTER",
    "SUPPORTED_EXTENSIONS",
    "EXTENSION_MAP",
    "detect_language",
    "parse_file",
    "get_parser",
    "ParseResult",
    "ParsedSymbol",
    "ParsedEdge",
    "TreeSitterParser",
    "RegexParser",
]
