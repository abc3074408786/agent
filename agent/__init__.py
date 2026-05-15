"""
Agent - 生产级 AI Agent 框架

各子模块可独立导入:
    from agent.algorithms import HybridTokenEstimator
    from agent.observability import get_logger
    from agent.permissions import PermissionEngine
"""

__version__ = "0.2.0"
__author__ = "Agent Team"


def _safe_import():
    """安全导入所有模块 - 失败不阻塞"""
    import importlib
    modules = [
        "agent.config",
        "agent.observability",
        "agent.llm",
        "agent.memory",
        "agent.tools",
        "agent.graph",
        "agent.permissions",
        "agent.streaming",
        "agent.coordinator",
        "agent.context",
        "agent.middleware",
        "agent.retry",
        "agent.hooks",
        "agent.algorithms",
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
        except (ImportError, Exception):
            pass


_safe_import()
