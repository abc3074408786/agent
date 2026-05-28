"""
Leader Agent - 任务分解与分配

Leader 负责:
1. 分析用户需求
2. 拆解为子任务
3. 分配角色和模型
4. 确定依赖关系和执行顺序
"""

import json
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

import logging

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Agent 角色"""
    PYTHON_DEV = "python_dev"
    FRONTEND_DEV = "frontend_dev"
    BACKEND_DEV = "backend_dev"
    TEST_ENGINEER = "test_engineer"
    SECURITY_AUDITOR = "security_auditor"
    ARCHITECT = "architect"
    DEVOPS = "devops"
    DATABASE_EXPERT = "database_expert"
    CODE_REVIEWER = "code_reviewer"


# 角色显示信息
ROLE_INFO = {
    AgentRole.PYTHON_DEV: {"icon": "🐍", "label": "Python 开发", "color": "#3776AB"},
    AgentRole.FRONTEND_DEV: {"icon": "⚛️", "label": "前端开发", "color": "#61DAFB"},
    AgentRole.BACKEND_DEV: {"icon": "🔧", "label": "后端开发", "color": "#68A063"},
    AgentRole.TEST_ENGINEER: {"icon": "🧪", "label": "测试工程师", "color": "#E535AB"},
    AgentRole.SECURITY_AUDITOR: {"icon": "🛡️", "label": "安全审计", "color": "#FF6B6B"},
    AgentRole.ARCHITECT: {"icon": "🏗️", "label": "架构师", "color": "#FF9800"},
    AgentRole.DEVOPS: {"icon": "🚀", "label": "DevOps", "color": "#2196F3"},
    AgentRole.DATABASE_EXPERT: {"icon": "🗄️", "label": "数据库专家", "color": "#4CAF50"},
    AgentRole.CODE_REVIEWER: {"icon": "👁️", "label": "代码审查", "color": "#9C27B0"},
}

# 默认模型分配
DEFAULT_MODEL_ASSIGNMENT = {
    AgentRole.PYTHON_DEV: "gpt-4o",
    AgentRole.FRONTEND_DEV: "gpt-4o",
    AgentRole.BACKEND_DEV: "gpt-4o",
    AgentRole.TEST_ENGINEER: "claude-sonnet-4",
    AgentRole.SECURITY_AUDITOR: "gpt-4o",
    AgentRole.ARCHITECT: "claude-sonnet-4",
    AgentRole.DEVOPS: "gpt-4o",
    AgentRole.DATABASE_EXPERT: "gpt-4o",
    AgentRole.CODE_REVIEWER: "claude-sonnet-4",
}


@dataclass
class SubTask:
    """子任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    role: AgentRole = AgentRole.PYTHON_DEV
    model: str = "gpt-4o"
    depends_on: List[str] = field(default_factory=list)
    priority: int = 1  # 1=high, 2=medium, 3=low
    estimated_time: str = "~30s"
    status: str = "pending"  # pending, running, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        role_info = ROLE_INFO.get(self.role, {"icon": "🤖", "label": "Agent", "color": "#666"})
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "role": self.role.value,
            "role_icon": role_info["icon"],
            "role_label": role_info["label"],
            "role_color": role_info["color"],
            "model": self.model,
            "depends_on": self.depends_on,
            "priority": self.priority,
            "estimated_time": self.estimated_time,
            "status": self.status,
        }


@dataclass
class TaskPlan:
    """任务计划"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    user_request: str = ""
    summary: str = ""
    subtasks: List[SubTask] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_request": self.user_request,
            "summary": self.summary,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "created_at": self.created_at,
        }


class LeaderAgent:
    """
    Leader Agent - 任务分解者

    分析用户需求，拆解为子任务并分配给合适的角色
    """

    def __init__(self, llm=None, model_config: Optional[Dict[str, str]] = None):
        self._llm = llm
        self._model_config = model_config or {}

    async def decompose(self, user_request: str) -> TaskPlan:
        """
        分解用户请求为执行计划

        如果有 LLM，使用 LLM 智能分解
        否则使用基于规则的分解
        """
        if self._llm:
            return await self._llm_decompose(user_request)
        else:
            return self._rule_based_decompose(user_request)

    async def _llm_decompose(self, user_request: str) -> TaskPlan:
        """使用 LLM 分解任务"""
        prompt = f"""你是一个技术团队的 Leader。分析以下需求并分解为子任务。

用户需求: {user_request}

可用角色:
- python_dev: Python 开发 (代码实现)
- frontend_dev: 前端开发 (UI/UX)
- backend_dev: 后端开发 (API/服务)
- test_engineer: 测试工程师 (测试用例/验证)
- security_auditor: 安全审计 (漏洞检查)
- architect: 架构师 (设计方案)
- devops: DevOps (部署/CI)
- database_expert: 数据库专家 (数据模型)
- code_reviewer: 代码审查

请以 JSON 格式返回:
{{
  "summary": "一句话描述你的分解方案",
  "subtasks": [
    {{
      "title": "子任务标题",
      "description": "详细描述",
      "role": "角色名",
      "depends_on_indices": [依赖的子任务索引],
      "priority": 1
    }}
  ]
}}

要求:
- 合理分解，不要超过5个子任务
- 正确识别依赖关系
- 选择最合适的角色
- 返回纯 JSON"""

        try:
            from langchain_core.messages import HumanMessage
            response = await self._llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content

            # 解析 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            return self._build_plan(user_request, data)

        except Exception as e:
            logger.warning(f"LLM decomposition failed: {e}, falling back to rule-based")
            return self._rule_based_decompose(user_request)

    def _build_plan(self, user_request: str, data: Dict) -> TaskPlan:
        """从 LLM 输出构建计划"""
        subtasks = []
        for i, st_data in enumerate(data.get("subtasks", [])):
            role_str = st_data.get("role", "python_dev")
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.PYTHON_DEV

            model = self._model_config.get(role.value) or DEFAULT_MODEL_ASSIGNMENT.get(role, "gpt-4o")

            task = SubTask(
                title=st_data.get("title", f"子任务 {i+1}"),
                description=st_data.get("description", ""),
                role=role,
                model=model,
                priority=st_data.get("priority", 2),
            )
            subtasks.append(task)

        # 设置依赖
        for i, st_data in enumerate(data.get("subtasks", [])):
            deps = st_data.get("depends_on_indices", [])
            for dep_idx in deps:
                if 0 <= dep_idx < len(subtasks) and dep_idx != i:
                    subtasks[i].depends_on.append(subtasks[dep_idx].id)

        return TaskPlan(
            user_request=user_request,
            summary=data.get("summary", f"将任务分解为 {len(subtasks)} 个子任务"),
            subtasks=subtasks,
        )

    def _rule_based_decompose(self, user_request: str) -> TaskPlan:
        """基于规则的任务分解 (无 LLM 时使用)"""
        request_lower = user_request.lower()

        subtasks = []

        # 分析关键词来决定子任务
        has_api = any(kw in request_lower for kw in ["api", "接口", "服务", "后端", "endpoint"])
        has_frontend = any(kw in request_lower for kw in ["前端", "页面", "ui", "组件", "界面"])
        has_db = any(kw in request_lower for kw in ["数据库", "表", "model", "数据模型", "存储"])
        has_auth = any(kw in request_lower for kw in ["登录", "注册", "认证", "鉴权", "权限", "验证"])
        has_test = any(kw in request_lower for kw in ["测试", "test", "验证", "检查"])
        has_deploy = any(kw in request_lower for kw in ["部署", "docker", "ci", "cd", "上线"])

        # 1. 架构设计 (总是第一步)
        arch_task = SubTask(
            title="架构设计",
            description=f"为「{user_request}」设计系统架构，确定模块划分和技术方案",
            role=AgentRole.ARCHITECT,
            model=self._get_model(AgentRole.ARCHITECT),
            priority=1,
            estimated_time="~20s",
        )
        subtasks.append(arch_task)

        # 2. 代码实现
        if has_api or has_auth:
            impl_task = SubTask(
                title="实现 API" + (" (含认证)" if has_auth else ""),
                description=f"根据架构设计实现后端 API 和业务逻辑",
                role=AgentRole.BACKEND_DEV if has_api else AgentRole.PYTHON_DEV,
                model=self._get_model(AgentRole.BACKEND_DEV if has_api else AgentRole.PYTHON_DEV),
                depends_on=[arch_task.id],
                priority=1,
                estimated_time="~45s",
            )
            subtasks.append(impl_task)
        else:
            impl_task = SubTask(
                title="代码实现",
                description=f"根据架构设计编写核心代码",
                role=AgentRole.PYTHON_DEV,
                model=self._get_model(AgentRole.PYTHON_DEV),
                depends_on=[arch_task.id],
                priority=1,
                estimated_time="~45s",
            )
            subtasks.append(impl_task)

        # 3. 前端 (如果需要)
        if has_frontend:
            fe_task = SubTask(
                title="前端开发",
                description="实现前端页面和组件",
                role=AgentRole.FRONTEND_DEV,
                model=self._get_model(AgentRole.FRONTEND_DEV),
                depends_on=[arch_task.id],
                priority=2,
                estimated_time="~40s",
            )
            subtasks.append(fe_task)

        # 4. 数据库 (如果需要)
        if has_db:
            db_task = SubTask(
                title="数据模型设计",
                description="设计数据库表结构和迁移脚本",
                role=AgentRole.DATABASE_EXPERT,
                model=self._get_model(AgentRole.DATABASE_EXPERT),
                depends_on=[arch_task.id],
                priority=1,
                estimated_time="~25s",
            )
            subtasks.append(db_task)

        # 5. 测试
        test_task = SubTask(
            title="编写测试",
            description="编写单元测试和集成测试",
            role=AgentRole.TEST_ENGINEER,
            model=self._get_model(AgentRole.TEST_ENGINEER),
            depends_on=[impl_task.id],
            priority=2,
            estimated_time="~30s",
        )
        subtasks.append(test_task)

        # 6. 安全审计 (如果涉及认证)
        if has_auth:
            security_task = SubTask(
                title="安全审计",
                description="检查认证流程的安全性，识别潜在漏洞",
                role=AgentRole.SECURITY_AUDITOR,
                model=self._get_model(AgentRole.SECURITY_AUDITOR),
                depends_on=[impl_task.id],
                priority=2,
                estimated_time="~25s",
            )
            subtasks.append(security_task)

        # 7. 部署 (如果需要)
        if has_deploy:
            deploy_task = SubTask(
                title="部署配置",
                description="编写 Dockerfile 和 CI/CD 配置",
                role=AgentRole.DEVOPS,
                model=self._get_model(AgentRole.DEVOPS),
                depends_on=[impl_task.id, test_task.id],
                priority=3,
                estimated_time="~20s",
            )
            subtasks.append(deploy_task)

        # 生成摘要
        roles_involved = list(set(st.role for st in subtasks))
        role_labels = [ROLE_INFO[r]["label"] for r in roles_involved]
        summary = f"好的，我把这个任务拆解为以下 {len(subtasks)} 个子任务：\n"
        for i, st in enumerate(subtasks, 1):
            role_info = ROLE_INFO[st.role]
            summary += f"  {i}. {st.title} → {role_info['icon']} {role_info['label']}\n"

        return TaskPlan(
            user_request=user_request,
            summary=summary,
            subtasks=subtasks,
        )

    def _get_model(self, role: AgentRole) -> str:
        """获取角色的模型"""
        return self._model_config.get(role.value) or DEFAULT_MODEL_ASSIGNMENT.get(role, "gpt-4o")
