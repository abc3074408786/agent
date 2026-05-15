"""
Skills System - ECC 风格的领域技能包

支持:
- YAML/Dict 定义技能 (system_prompt + tools + rules)
- 技能加载器 (从文件/目录加载)
- 技能注册器
- 技能与 Agent 集成
- 技能组合 (多技能叠加)
"""

import yaml
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field

import logging
logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str = ""
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)  # 工具名称列表
    rules: List[str] = field(default_factory=list)  # 编码规则
    examples: List[Dict[str, str]] = field(default_factory=list)  # 示例对话
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"
    author: Optional[str] = None
    # 高级配置
    temperature: Optional[float] = None
    max_iterations: Optional[int] = None
    context_window: Optional[int] = None

    def to_system_message(self) -> str:
        """将技能转为系统提示"""
        parts = []

        if self.system_prompt:
            parts.append(self.system_prompt)

        if self.rules:
            rules_text = "\n".join(f"- {r}" for r in self.rules)
            parts.append(f"\n## 规则\n{rules_text}")

        if self.examples:
            examples_text = ""
            for ex in self.examples:
                examples_text += f"\nUser: {ex.get('user', '')}\nAssistant: {ex.get('assistant', '')}\n"
            parts.append(f"\n## 示例\n{examples_text}")

        return "\n\n".join(parts)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        """从字典创建"""
        return cls(
            name=data.get("name", "unnamed"),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            rules=data.get("rules", []),
            examples=data.get("examples", []),
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0"),
            author=data.get("author"),
            temperature=data.get("temperature"),
            max_iterations=data.get("max_iterations"),
            context_window=data.get("context_window"),
        )

    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> "Skill":
        """从 YAML 文件加载"""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if "name" not in data:
            data["name"] = path.stem
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        d = {
            "name": self.name,
            "description": self.description,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "rules": self.rules,
            "tags": self.tags,
            "version": self.version,
        }
        if self.examples:
            d["examples"] = self.examples
        if self.author:
            d["author"] = self.author
        if self.temperature is not None:
            d["temperature"] = self.temperature
        return d


class SkillRegistry:
    """
    技能注册器

    管理所有可用技能的加载、注册和检索
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册技能"""
        self._skills[skill.name] = skill
        logger.info(f"Registered skill: {skill.name}")

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)

    def list_skills(self) -> List[str]:
        """列出所有技能"""
        return list(self._skills.keys())

    def get_by_tags(self, tags: List[str]) -> List[Skill]:
        """按标签筛选"""
        return [
            s for s in self._skills.values()
            if any(t in s.tags for t in tags)
        ]

    def load_from_directory(self, directory: Union[str, Path]) -> int:
        """从目录加载所有 YAML 技能文件"""
        directory = Path(directory)
        if not directory.exists():
            return 0

        count = 0
        for path in directory.glob("*.yaml"):
            try:
                skill = Skill.from_yaml(path)
                self.register(skill)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to load skill from {path}: {e}")

        for path in directory.glob("*.yml"):
            try:
                skill = Skill.from_yaml(path)
                self.register(skill)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to load skill from {path}: {e}")

        return count

    def remove(self, name: str) -> bool:
        """移除技能"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def clear(self) -> None:
        """清除所有"""
        self._skills.clear()

    @property
    def count(self) -> int:
        return len(self._skills)


def combine_skills(*skills: Skill) -> Skill:
    """
    组合多个技能为一个

    合并 system_prompt, tools, rules
    """
    if not skills:
        return Skill(name="empty")

    combined = Skill(
        name="+".join(s.name for s in skills),
        description="Combined skill: " + ", ".join(s.description for s in skills if s.description),
        system_prompt="\n\n---\n\n".join(s.system_prompt for s in skills if s.system_prompt),
        tools=list(set(t for s in skills for t in s.tools)),
        rules=list(set(r for s in skills for r in s.rules)),
        tags=list(set(t for s in skills for t in s.tags)),
    )
    return combined


# 全局注册器
skill_registry = SkillRegistry()


def register_builtin_skills() -> None:
    """注册内置技能"""
    presets_dir = Path(__file__).parent / "presets"
    if presets_dir.exists():
        skill_registry.load_from_directory(presets_dir)


__all__ = [
    "Skill",
    "SkillRegistry",
    "combine_skills",
    "skill_registry",
    "register_builtin_skills",
]
