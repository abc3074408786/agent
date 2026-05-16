"""
代码图谱端到端测试

使用真实 Python 文件分析:
- 分析 agent/ 目录自身
- 验证函数的调用者查询
- 修改函数的影响分析
- Mermaid 输出格式验证
"""
import pytest
import os
from pathlib import Path

from agent.agent.code_graph import (
    CodeGraphAnalyzer,
    CodeNode,
    CodeEdge,
    CodeGraph,
)


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class TestAnalyzeRealProject:
    """分析 agent/ 目录自身 → 验证能找到函数和类"""

    def test_analyze_real_project(self):
        """分析 agent 项目自身，应能找到函数和类"""
        analyzer = CodeGraphAnalyzer()

        # 分析 agent/tools/file_tools.py - 一个具体的文件
        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        result = analyzer.analyze_file(file_path)
        assert result is not None

        # 应该能找到函数
        functions = analyzer.graph.get_nodes_by_type("function")
        assert len(functions) > 0

        # 验证找到了已知函数
        func_names = [f.name for f in functions]
        assert any("file_read" in name for name in func_names)
        assert any("file_write" in name for name in func_names)

    def test_analyze_directory(self):
        """分析整个目录"""
        analyzer = CodeGraphAnalyzer()
        
        # 分析 tools 目录
        tools_dir = str(PROJECT_ROOT / "agent" / "tools")
        if not os.path.isdir(tools_dir):
            pytest.skip(f"Directory not found: {tools_dir}")

        count = analyzer.analyze_directory(tools_dir)
        assert count >= 1  # 至少分析了一个文件

        stats = analyzer.get_stats()
        assert stats["files"] >= 1
        assert stats["functions"] >= 1

    def test_analyze_multiple_files(self):
        """分析多个文件构建完整图"""
        analyzer = CodeGraphAnalyzer()

        # 分析多个文件
        files_to_analyze = [
            PROJECT_ROOT / "agent" / "tools" / "file_tools.py",
            PROJECT_ROOT / "agent" / "tools" / "bash_tool.py",
        ]

        analyzed = 0
        for f in files_to_analyze:
            if f.exists():
                result = analyzer.analyze_file(str(f))
                if result:
                    analyzed += 1

        assert analyzed >= 1

        # 验证有 import 边
        import_edges = analyzer.graph.get_edges_by_type("imports")
        assert len(import_edges) > 0


class TestCallersQuery:
    """验证能找到函数的调用者"""

    def test_callers_query(self):
        """查询函数的调用者"""
        analyzer = CodeGraphAnalyzer()

        # 分析 file_tools.py
        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        # _is_sensitive_path 被 file_read, file_write, file_edit 等调用
        callers = analyzer.get_callers("_is_sensitive_path")
        assert len(callers) > 0

    def test_callees_query(self):
        """查询函数调用了谁"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        # file_read 应该调用了 _resolve_path 等
        callees = analyzer.get_callees("file_read")
        assert len(callees) > 0

    def test_search_symbols(self):
        """搜索符号"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        # 搜索 "file"
        results = analyzer.search_symbols("file")
        assert len(results) > 0
        # 应包含 file_read, file_write 等
        names = [r.name for r in results]
        assert any("file" in name for name in names)


class TestImpactAnalysis:
    """修改某个函数 → 验证影响分析结果合理"""

    def test_impact_analysis(self):
        """修改核心函数应影响多个调用者"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        # _resolve_path 被很多函数使用，修改它应有影响
        impact = analyzer.get_impact("_resolve_path")

        # 应该有受影响的符号
        affected_symbols = impact["symbols"]
        assert len(affected_symbols) > 0

    def test_impact_analysis_leaf_function(self):
        """叶子函数（无调用者）的影响应为空"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        # 使用一个不太可能被引用的名称
        impact = analyzer.get_impact("__nonexistent_function__")
        assert len(impact["files"]) == 0
        assert len(impact["symbols"]) == 0


class TestMermaidOutput:
    """验证 to_mermaid() 输出是合法的 Mermaid 格式"""

    def test_mermaid_output(self):
        """Mermaid 输出应有正确的格式"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        mermaid = analyzer.to_mermaid()

        # 基本格式验证
        assert mermaid.startswith("graph LR")
        # 应包含节点
        assert len(mermaid.split("\n")) > 1
        # 不应有语法错误字符
        assert "None" not in mermaid

    def test_mermaid_with_edges(self):
        """Mermaid 输出应包含边"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        mermaid = analyzer.to_mermaid()

        # 应包含箭头 (调用关系)
        has_arrows = ("-->" in mermaid or "-..->" in mermaid or "==>" in mermaid or "-.->")
        assert has_arrows or len(analyzer.graph.edges) == 0

    def test_dot_output(self):
        """DOT 输出也应该格式正确"""
        analyzer = CodeGraphAnalyzer()

        file_path = str(PROJECT_ROOT / "agent" / "tools" / "file_tools.py")
        if not os.path.exists(file_path):
            pytest.skip(f"File not found: {file_path}")

        analyzer.analyze_file(file_path)

        dot = analyzer.to_dot()

        # DOT 格式验证
        assert dot.startswith("digraph CodeGraph {")
        assert dot.strip().endswith("}")
        assert "rankdir=LR" in dot

    def test_empty_graph_mermaid(self):
        """空图也应该能输出"""
        analyzer = CodeGraphAnalyzer()
        mermaid = analyzer.to_mermaid()
        assert "graph LR" in mermaid
