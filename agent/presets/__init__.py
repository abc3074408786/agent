"""
Presets - 预制 Agent 模板

提供开箱即用的专业 Agent，将 Skills 与 Coordinator Worker 集成:
- 每个 preset 定义一个完整的 Agent 配置
- 可直接用于 Coordinator 的 Worker 任务分配
- 支持组合多个 Skills
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from agent.skills import Skill, skill_registry, register_builtin_skills

import logging
logger = logging.getLogger(__name__)


@dataclass
class AgentPreset:
    """预制 Agent 模板"""
    name: str
    description: str
    skills: List[str] = field(default_factory=list)  # 引用的技能名
    system_prompt: str = ""  # 额外的系统提示 (叠加在技能之上)
    tools: List[str] = field(default_factory=list)  # 额外工具
    max_iterations: int = 10
    temperature: float = 0.7
    # Worker 配置
    worker_role: str = "general"  # researcher / implementer / verifier / general
    can_parallel: bool = True     # 是否可并行
    timeout_seconds: float = 300.0

    def get_full_system_prompt(self) -> str:
        """获取完整系统提示 (合并所有技能)"""
        parts = []

        # 加载引用的技能
        for skill_name in self.skills:
            skill = skill_registry.get(skill_name)
            if skill:
                parts.append(skill.to_system_message())

        # 额外提示
        if self.system_prompt:
            parts.append(self.system_prompt)

        return "\n\n---\n\n".join(parts)

    def get_all_tools(self) -> List[str]:
        """获取所有工具名 (技能 + 额外)"""
        all_tools = list(self.tools)
        for skill_name in self.skills:
            skill = skill_registry.get(skill_name)
            if skill:
                all_tools.extend(skill.tools)
        return list(set(all_tools))


# ============ 预制 Agent 定义 ============

BUILTIN_PRESETS: Dict[str, AgentPreset] = {
    "code_reviewer": AgentPreset(
        name="code_reviewer",
        description="代码审查 Agent - 发现 bug、安全问题和性能瓶颈",
        skills=["code_reviewer", "security_auditor"],
        worker_role="verifier",
        can_parallel=True,
        temperature=0.3,
    ),
    "security_auditor": AgentPreset(
        name="security_auditor",
        description="安全审计 Agent - 全面安全漏洞扫描",
        skills=["security_auditor"],
        worker_role="verifier",
        can_parallel=True,
        temperature=0.2,
    ),
    "architect": AgentPreset(
        name="architect",
        description="架构设计 Agent - 系统设计和技术选型",
        skills=["architect", "database_expert"],
        worker_role="researcher",
        can_parallel=True,
        temperature=0.7,
    ),
    "performance_optimizer": AgentPreset(
        name="performance_optimizer",
        description="性能优化 Agent - 定位瓶颈并给出优化方案",
        skills=["performance_optimizer"],
        worker_role="researcher",
        can_parallel=True,
        temperature=0.3,
    ),
    "python_developer": AgentPreset(
        name="python_developer",
        description="Python 开发 Agent - 编写高质量 Python 代码",
        skills=["python_expert", "test_engineer"],
        worker_role="implementer",
        can_parallel=False,  # 实现类串行
        temperature=0.5,
    ),
    "frontend_developer": AgentPreset(
        name="frontend_developer",
        description="前端开发 Agent - React/TypeScript 实现",
        skills=["frontend_expert", "test_engineer"],
        worker_role="implementer",
        can_parallel=False,
        temperature=0.5,
    ),
    "devops_agent": AgentPreset(
        name="devops_agent",
        description="DevOps Agent - CI/CD、容器化、部署",
        skills=["devops_engineer"],
        worker_role="implementer",
        can_parallel=True,
        temperature=0.3,
    ),
    "data_analyst": AgentPreset(
        name="data_analyst",
        description="数据分析 Agent - 数据探索、建模、可视化",
        skills=["data_scientist"],
        worker_role="researcher",
        can_parallel=True,
        temperature=0.5,
    ),
    "doc_writer": AgentPreset(
        name="doc_writer",
        description="文档 Agent - API 文档、README、教程",
        skills=["technical_writer"],
        worker_role="implementer",
        can_parallel=True,
        temperature=0.7,
    ),
    "full_stack": AgentPreset(
        name="full_stack",
        description="全栈开发 Agent - 前后端 + DevOps",
        skills=["python_expert", "frontend_expert", "devops_engineer"],
        worker_role="implementer",
        can_parallel=False,
        temperature=0.5,
        max_iterations=15,
    ),
    "research_agent": AgentPreset(
        name="research_agent",
        description="研究 Agent - 代码库探索和信息收集",
        skills=[],
        system_prompt=(
            "你是一个研究员。你的任务是探索代码库、收集信息、理解架构。\n"
            "- 不要修改任何文件\n"
            "- 报告文件路径、行号和关键发现\n"
            "- 关注依赖关系和数据流"
        ),
        worker_role="researcher",
        can_parallel=True,
        temperature=0.3,
    ),
    "bug_fixer": AgentPreset(
        name="bug_fixer",
        description="Bug 修复 Agent - 定位并修复 bug",
        skills=["python_expert", "test_engineer"],
        system_prompt=(
            "你专注于修复 bug。你的工作流:\n"
            "1. 复现问题\n"
            "2. 定位根本原因 (不是症状)\n"
            "3. 编写修复\n"
            "4. 添加回归测试\n"
            "5. 验证修复不引入新问题"
        ),
        worker_role="implementer",
        can_parallel=False,
        temperature=0.3,
    ),
}


class PresetManager:
    """预制 Agent 管理器"""

    def __init__(self):
        self._presets: Dict[str, AgentPreset] = dict(BUILTIN_PRESETS)

    def get(self, name: str) -> Optional[AgentPreset]:
        return self._presets.get(name)

    def register(self, preset: AgentPreset) -> None:
        self._presets[preset.name] = preset

    def list_presets(self) -> List[str]:
        return list(self._presets.keys())

    def list_by_role(self, role: str) -> List[AgentPreset]:
        return [p for p in self._presets.values() if p.worker_role == role]

    def get_description_map(self) -> Dict[str, str]:
        """获取 name → description 映射 (用于 LLM 选择)"""
        return {name: p.description for name, p in self._presets.items()}


# 全局实例
preset_manager = PresetManager()


def get_preset(name: str) -> Optional[AgentPreset]:
    """获取预制 Agent"""
    return preset_manager.get(name)


def list_presets() -> List[str]:
    """列出所有预制 Agent"""
    return preset_manager.list_presets()


__all__ = [
    "AgentPreset",
    "PresetManager",
    "BUILTIN_PRESETS",
    "preset_manager",
    "get_preset",
    "list_presets",
]
