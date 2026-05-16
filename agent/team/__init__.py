"""
团队智能体模块 - 多 Agent 协作系统

通过 WorkflowDAG 编排多个 AI Agent 模拟开发团队协作：
- 定义角色 (架构师、开发者、测试、审查)
- 定义工作流 (谁先谁后，什么条件下继续)
- 共享上下文 (所有人看到同一个项目状态)
- 质量门控 (Review 不过就不继续)
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class TeamMember:
    """团队成员"""
    name: str                    # 如 "architect", "developer"
    role: str                    # researcher / implementer / verifier
    preset_name: str             # 对应 presets 中的名称
    description: str = ""


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    name: str
    assigned_to: str             # TeamMember name
    prompt_template: str         # 提示模板 (可用 {requirement}, {prev_output} 变量)
    depends_on: List[str] = field(default_factory=list)
    quality_gate: Optional[str] = None  # 质量门控条件
    timeout_seconds: float = 300
    max_retries: int = 2


@dataclass
class QualityCheckResult:
    """质量检查结果"""
    passed: bool
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """步骤执行结果"""
    step_id: str
    status: str                  # "passed" / "failed" / "blocked" / "skipped"
    output: str = ""
    duration: float = 0.0
    quality_check: Optional[Dict[str, Any]] = None


@dataclass
class TeamExecutionResult:
    """团队执行总结果"""
    status: str                  # "completed" / "failed" / "partial"
    steps: List[StepResult] = field(default_factory=list)
    total_duration: float = 0.0
    shared_context: Dict[str, Any] = field(default_factory=dict)



# ============================================================
# SharedContext - 团队共享上下文
# ============================================================

class SharedContext:
    """团队共享上下文 - 所有 Agent 共享的项目知识"""

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._file_changes: List[Dict[str, str]] = []
        self._decisions: List[Dict[str, str]] = []

    def set(self, key: str, value: Any) -> None:
        """设置上下文"""
        self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """获取上下文"""
        return self._data.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """获取所有上下文数据"""
        return {
            **self._data,
            "_file_changes": self._file_changes,
            "_decisions": self._decisions,
        }

    def add_file_change(self, file_path: str, description: str) -> None:
        """记录文件变更"""
        self._file_changes.append({
            "file_path": file_path,
            "description": description,
        })

    def add_decision(self, decision: str, reason: str) -> None:
        """记录架构决策"""
        self._decisions.append({
            "decision": decision,
            "reason": reason,
        })

    def get_changed_files(self) -> List[Dict[str, str]]:
        """获取所有变更文件"""
        return list(self._file_changes)

    def get_decisions(self) -> List[Dict[str, str]]:
        """获取所有决策"""
        return list(self._decisions)

    def to_prompt_context(self) -> str:
        """转为可注入系统提示的文本"""
        lines = ["## 团队共享上下文\n"]

        # 基本数据
        if self._data:
            lines.append("### 项目状态")
            for key, value in self._data.items():
                lines.append(f"- {key}: {value}")
            lines.append("")

        # 架构决策
        if self._decisions:
            lines.append("### 架构决策")
            for d in self._decisions:
                lines.append(f"- {d['decision']} (原因: {d['reason']})")
            lines.append("")

        # 文件变更
        if self._file_changes:
            lines.append("### 文件变更")
            for fc in self._file_changes:
                lines.append(f"- {fc['file_path']}: {fc['description']}")
            lines.append("")

        return "\n".join(lines)



# ============================================================
# QualityGate - 质量门控
# ============================================================

class QualityGate:
    """质量门控 - 决定是否可以进入下一步"""

    # Review 失败关键词
    REVIEW_FAIL_KEYWORDS = [
        "critical", "Critical", "CRITICAL",
        "必须修复", "严重问题", "不通过", "reject", "Reject", "REJECT",
        "blocker", "Blocker", "BLOCKER",
        "安全漏洞", "严重缺陷",
    ]

    # 测试失败关键词（更精确匹配）
    TEST_FAIL_KEYWORDS = [
        "FAILED", " failed", "Error:", "ERROR:",
        "AssertionError", "测试失败", "不通过",
        "FAILURES", "failures:", "test failed",
    ]

    # 测试通过关键词
    TEST_PASS_KEYWORDS = [
        "passed", "PASSED", "all tests passed",
        "测试通过", "全部通过", "OK", "success", "SUCCESS",
    ]

    @classmethod
    def check_review_passed(cls, review_output: str) -> QualityCheckResult:
        """分析 review 输出是否通过"""
        if not review_output:
            return QualityCheckResult(
                passed=False,
                reason="Review 输出为空",
                details={"type": "empty_output"},
            )

        # 检查是否有失败关键词
        found_issues = []
        for keyword in cls.REVIEW_FAIL_KEYWORDS:
            if keyword in review_output:
                found_issues.append(keyword)

        if found_issues:
            return QualityCheckResult(
                passed=False,
                reason=f"Review 发现严重问题: {', '.join(found_issues)}",
                details={"type": "review_failed", "keywords_found": found_issues},
            )

        return QualityCheckResult(
            passed=True,
            reason="Review 通过，未发现严重问题",
            details={"type": "review_passed"},
        )

    @classmethod
    def check_tests_passed(cls, test_output: str) -> QualityCheckResult:
        """分析测试输出是否全部通过"""
        if not test_output:
            return QualityCheckResult(
                passed=False,
                reason="测试输出为空",
                details={"type": "empty_output"},
            )

        # 检查是否有通过关键词
        has_pass = any(kw in test_output for kw in cls.TEST_PASS_KEYWORDS)
        # 检查是否有失败关键词
        found_failures = [kw for kw in cls.TEST_FAIL_KEYWORDS if kw in test_output]

        # 如果同时有 pass 和 fail 信号，需要更智能地判断
        # 例如 "10 passed, 0 failed" 应该是通过
        if has_pass and found_failures:
            # 检查 "0 failed" 或 "0 failures" 模式
            import re
            zero_fail_pattern = re.compile(r'\b0\s+(failed|failures?|FAILED|FAILURES)\b')
            if zero_fail_pattern.search(test_output):
                return QualityCheckResult(
                    passed=True,
                    reason="所有测试通过 (0 failures)",
                    details={"type": "tests_passed"},
                )

        if found_failures and not has_pass:
            return QualityCheckResult(
                passed=False,
                reason=f"测试失败: {', '.join(f.strip() for f in found_failures)}",
                details={"type": "tests_failed", "keywords_found": found_failures},
            )

        if found_failures and has_pass:
            # 有失败信号也有通过信号，标记失败（不是 0 failed 的情况）
            return QualityCheckResult(
                passed=False,
                reason=f"测试部分失败: {', '.join(f.strip() for f in found_failures)}",
                details={"type": "tests_partial_failed", "keywords_found": found_failures},
            )

        if has_pass:
            return QualityCheckResult(
                passed=True,
                reason="所有测试通过",
                details={"type": "tests_passed"},
            )

        # 没有明确的通过或失败信号，默认通过
        return QualityCheckResult(
            passed=True,
            reason="未发现测试失败信号",
            details={"type": "no_failure_signal"},
        )

    @classmethod
    def check_custom(cls, output: str, condition: str) -> QualityCheckResult:
        """自定义检查 - 基于条件关键词"""
        if not output:
            return QualityCheckResult(
                passed=False,
                reason="输出为空",
                details={"type": "empty_output", "condition": condition},
            )

        # 自定义条件格式: "contains:keyword" 或 "not_contains:keyword"
        if condition.startswith("contains:"):
            keyword = condition[len("contains:"):]
            if keyword in output:
                return QualityCheckResult(
                    passed=True,
                    reason=f"输出包含: {keyword}",
                    details={"type": "custom_passed", "condition": condition},
                )
            return QualityCheckResult(
                passed=False,
                reason=f"输出不包含: {keyword}",
                details={"type": "custom_failed", "condition": condition},
            )
        elif condition.startswith("not_contains:"):
            keyword = condition[len("not_contains:"):]
            if keyword not in output:
                return QualityCheckResult(
                    passed=True,
                    reason=f"输出不包含: {keyword}",
                    details={"type": "custom_passed", "condition": condition},
                )
            return QualityCheckResult(
                passed=False,
                reason=f"输出包含不该有的: {keyword}",
                details={"type": "custom_failed", "condition": condition},
            )

        # 默认：检查条件字符串是否在输出中
        if condition in output:
            return QualityCheckResult(
                passed=True,
                reason=f"条件满足: {condition}",
                details={"type": "custom_passed", "condition": condition},
            )
        return QualityCheckResult(
            passed=False,
            reason=f"条件未满足: {condition}",
            details={"type": "custom_failed", "condition": condition},
        )

    @classmethod
    def evaluate(cls, gate_type: str, output: str) -> QualityCheckResult:
        """根据门控类型评估"""
        if gate_type == "review_passed":
            return cls.check_review_passed(output)
        elif gate_type == "tests_passed":
            return cls.check_tests_passed(output)
        else:
            return cls.check_custom(output, gate_type)



# ============================================================
# WorkflowDAG - 工作流有向无环图
# ============================================================

class WorkflowDAG:
    """工作流有向无环图 - 管理步骤依赖和执行顺序"""

    def __init__(self):
        self._steps: Dict[str, WorkflowStep] = {}
        self._edges: Dict[str, List[str]] = {}  # step_id -> [依赖的step_id]

    def add_step(self, step: WorkflowStep) -> None:
        """添加步骤"""
        self._steps[step.id] = step
        self._edges[step.id] = list(step.depends_on)

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        """获取步骤"""
        return self._steps.get(step_id)

    def get_all_steps(self) -> List[WorkflowStep]:
        """获取所有步骤"""
        return list(self._steps.values())

    def get_ready_steps(self, completed: Set[str]) -> List[WorkflowStep]:
        """获取可执行的步骤 (依赖都完成了)"""
        ready = []
        for step_id, deps in self._edges.items():
            if step_id in completed:
                continue
            if all(dep in completed for dep in deps):
                ready.append(self._steps[step_id])
        return ready

    def get_execution_order(self) -> List[WorkflowStep]:
        """拓扑排序获取执行顺序 (Kahn 算法)"""
        if not self.validate():
            raise ValueError("DAG 中存在循环依赖，无法拓扑排序")

        # 计算入度
        in_degree: Dict[str, int] = {step_id: 0 for step_id in self._steps}
        reverse_edges: Dict[str, List[str]] = {step_id: [] for step_id in self._steps}

        for step_id, deps in self._edges.items():
            for dep in deps:
                if dep in self._steps:
                    in_degree[step_id] += 1
                    reverse_edges[dep].append(step_id)

        # Kahn 算法
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        order: List[WorkflowStep] = []

        while queue:
            current = queue.popleft()
            order.append(self._steps[current])

            for neighbor in reverse_edges.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return order

    def validate(self) -> bool:
        """验证 DAG (无环检测) - 使用 DFS 检测环"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {step_id: WHITE for step_id in self._steps}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for dep_id in self._edges.get(node, []):
                if dep_id not in self._steps:
                    continue  # 忽略不存在的依赖
                if color[dep_id] == GRAY:
                    return False  # 发现环
                if color[dep_id] == WHITE:
                    if not dfs(dep_id):
                        return False
            color[node] = BLACK
            return True

        for step_id in self._steps:
            if color[step_id] == WHITE:
                if not dfs(step_id):
                    return False
        return True

    def get_parallel_groups(self) -> List[List[WorkflowStep]]:
        """获取可并行执行的步骤组"""
        if not self.validate():
            raise ValueError("DAG 中存在循环依赖")

        groups: List[List[WorkflowStep]] = []
        completed: Set[str] = set()

        while len(completed) < len(self._steps):
            ready = self.get_ready_steps(completed)
            if not ready:
                break
            groups.append(ready)
            completed.update(step.id for step in ready)

        return groups

    def to_mermaid(self) -> str:
        """可视化为 Mermaid 图"""
        lines = ["graph TD"]

        for step_id, step in self._steps.items():
            # 节点定义
            label = f"{step.name}"
            if step.quality_gate:
                label += f" [{step.quality_gate}]"
            lines.append(f"    {step_id}[\"{label}\"]")

        for step_id, deps in self._edges.items():
            for dep in deps:
                if dep in self._steps:
                    lines.append(f"    {dep} --> {step_id}")

        return "\n".join(lines)

    @classmethod
    def from_steps(cls, steps: List[WorkflowStep]) -> "WorkflowDAG":
        """从步骤列表创建 DAG"""
        dag = cls()
        for step in steps:
            dag.add_step(step)
        return dag



# ============================================================
# TeamAgent - 核心编排器
# ============================================================

class TeamAgent:
    """团队智能体 - 编排多个 Agent 协作完成任务"""

    def __init__(
        self,
        llm: Optional[Any] = None,
        members: Optional[List[TeamMember]] = None,
        workflow: Optional[List[WorkflowStep]] = None,
    ):
        self.llm = llm
        self.members = {m.name: m for m in (members or [])}
        self.dag = WorkflowDAG.from_steps(workflow or [])
        self.shared_context = SharedContext()
        self.quality_gate = QualityGate()

    async def execute(self, requirement: str) -> TeamExecutionResult:
        """执行完整工作流"""
        start_time = time.time()
        results: List[StepResult] = []
        completed: Set[str] = set()
        failed: Set[str] = set()

        # 1. 初始化共享上下文
        self.shared_context = SharedContext()
        self.shared_context.set("requirement", requirement)
        self.shared_context.set("status", "in_progress")

        logger.info(f"开始团队工作流执行: {requirement[:100]}...")

        # 2. 验证 DAG
        if not self.dag.validate():
            return TeamExecutionResult(
                status="failed",
                steps=[],
                total_duration=time.time() - start_time,
                shared_context=self.shared_context.get_all(),
            )

        # 3. 按 DAG 顺序执行步骤
        try:
            execution_order = self.dag.get_execution_order()
        except ValueError as e:
            logger.error(f"DAG 验证失败: {e}")
            return TeamExecutionResult(
                status="failed",
                steps=[],
                total_duration=time.time() - start_time,
                shared_context=self.shared_context.get_all(),
            )

        for step in execution_order:
            # 检查依赖是否都已完成（非失败）
            if any(dep in failed for dep in step.depends_on):
                result = StepResult(
                    step_id=step.id,
                    status="blocked",
                    output=f"被阻塞: 依赖步骤失败 ({', '.join(d for d in step.depends_on if d in failed)})",
                    duration=0.0,
                )
                results.append(result)
                failed.add(step.id)
                logger.warning(f"步骤 {step.id} 被阻塞")
                continue

            # 执行步骤（带重试）
            result = await self._execute_step_with_retry(step)
            results.append(result)

            if result.status == "passed":
                completed.add(step.id)
                self.shared_context.set(f"step_{step.id}_output", result.output)
            else:
                failed.add(step.id)

        # 4. 确定最终状态
        total_duration = time.time() - start_time
        if not failed:
            status = "completed"
            self.shared_context.set("status", "completed")
        elif completed:
            status = "partial"
            self.shared_context.set("status", "partial")
        else:
            status = "failed"
            self.shared_context.set("status", "failed")

        logger.info(f"团队工作流完成: status={status}, duration={total_duration:.2f}s")

        return TeamExecutionResult(
            status=status,
            steps=results,
            total_duration=total_duration,
            shared_context=self.shared_context.get_all(),
        )

    async def _execute_step_with_retry(self, step: WorkflowStep) -> StepResult:
        """执行步骤（带重试逻辑）"""
        last_result: Optional[StepResult] = None

        for attempt in range(step.max_retries + 1):
            if attempt > 0:
                logger.info(f"步骤 {step.id} 第 {attempt} 次重试")

            result = await self._execute_step(step)

            if result.status == "passed":
                return result

            last_result = result

            # 如果不是门控失败，不重试
            if result.quality_check is None:
                break

        return last_result or StepResult(
            step_id=step.id,
            status="failed",
            output="执行失败（已用尽重试次数）",
            duration=0.0,
        )

    async def _execute_step(self, step: WorkflowStep) -> StepResult:
        """执行单个步骤"""
        start_time = time.time()
        logger.info(f"执行步骤: {step.id} ({step.name}), 分配给: {step.assigned_to}")

        # 构建 prompt
        prompt = self._build_prompt(step)

        # 调用 LLM 或使用 mock
        try:
            output = await self._call_llm(step, prompt)
        except asyncio.TimeoutError:
            return StepResult(
                step_id=step.id,
                status="failed",
                output=f"步骤超时 ({step.timeout_seconds}s)",
                duration=time.time() - start_time,
            )
        except Exception as e:
            logger.error(f"步骤 {step.id} 执行失败: {e}")
            return StepResult(
                step_id=step.id,
                status="failed",
                output=f"执行异常: {str(e)}",
                duration=time.time() - start_time,
            )

        duration = time.time() - start_time

        # 更新共享上下文
        self.shared_context.set(f"step_{step.id}_output", output)

        # 检查质量门控
        quality_check = None
        if step.quality_gate:
            qc_result = QualityGate.evaluate(step.quality_gate, output)
            quality_check = {
                "passed": qc_result.passed,
                "reason": qc_result.reason,
                "details": qc_result.details,
            }

            if not qc_result.passed:
                logger.warning(
                    f"步骤 {step.id} 质量门控失败: {qc_result.reason}"
                )
                return StepResult(
                    step_id=step.id,
                    status="failed",
                    output=output,
                    duration=duration,
                    quality_check=quality_check,
                )

        return StepResult(
            step_id=step.id,
            status="passed",
            output=output,
            duration=duration,
            quality_check=quality_check,
        )

    def _build_prompt(self, step: WorkflowStep) -> str:
        """构建步骤的 prompt"""
        # 获取前序输出
        prev_outputs = []
        for dep_id in step.depends_on:
            dep_output = self.shared_context.get(f"step_{dep_id}_output", "")
            if dep_output:
                dep_step = self.dag.get_step(dep_id)
                dep_name = dep_step.name if dep_step else dep_id
                prev_outputs.append(f"[{dep_name}的输出]:\n{dep_output}")

        prev_output = "\n\n".join(prev_outputs) if prev_outputs else "（无前序输出）"

        # 渲染模板
        prompt = step.prompt_template.format(
            requirement=self.shared_context.get("requirement", ""),
            prev_output=prev_output,
            context=self.shared_context.to_prompt_context(),
        )

        return prompt

    async def _call_llm(self, step: WorkflowStep, prompt: str) -> str:
        """调用 LLM（如无 LLM 则用 mock）"""
        if self.llm is None:
            return self._mock_response(step)

        # 使用 asyncio.wait_for 实现超时
        async def _do_call():
            if hasattr(self.llm, "agenerate"):
                response = await self.llm.agenerate(prompt)
                return response
            elif hasattr(self.llm, "generate"):
                response = self.llm.generate(prompt)
                return response
            elif callable(self.llm):
                result = self.llm(prompt)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                return self._mock_response(step)

        return await asyncio.wait_for(_do_call(), timeout=step.timeout_seconds)

    def _mock_response(self, step: WorkflowStep) -> str:
        """Mock 响应（无 LLM 时使用）"""
        mock_responses = {
            "architect": f"[Mock 架构设计] 已完成 {step.name} 的架构设计。建议使用模块化架构，方案可行。",
            "developer": f"[Mock 代码实现] 已完成 {step.name} 的代码实现。代码质量良好，功能完整。",
            "reviewer": f"[Mock 代码审查] 已完成 {step.name} 的代码审查。代码质量优秀，无问题，建议合并。LGTM.",
            "tester": f"[Mock 测试验证] 已完成 {step.name} 的测试验证。all tests passed，覆盖率达标。",
        }

        assigned = step.assigned_to
        return mock_responses.get(
            assigned,
            f"[Mock] 步骤 {step.name} (由 {assigned} 执行) 已完成。all tests passed.",
        )



# ============================================================
# 预制团队成员
# ============================================================

DEFAULT_TEAM_MEMBERS = [
    TeamMember(
        name="architect",
        role="researcher",
        preset_name="architect",
        description="负责系统架构设计、技术方案选型",
    ),
    TeamMember(
        name="developer",
        role="implementer",
        preset_name="python_expert",
        description="负责代码实现、功能开发",
    ),
    TeamMember(
        name="reviewer",
        role="verifier",
        preset_name="code_reviewer",
        description="负责代码审查、质量把关",
    ),
    TeamMember(
        name="tester",
        role="verifier",
        preset_name="test_engineer",
        description="负责测试验证、质量保证",
    ),
]


# ============================================================
# 预制工作流
# ============================================================

# 标准开发工作流
STANDARD_DEV_WORKFLOW = [
    WorkflowStep(
        id="design",
        name="架构设计",
        assigned_to="architect",
        prompt_template=(
            "请为以下需求设计系统架构：\n\n"
            "需求: {requirement}\n\n"
            "{context}\n\n"
            "请输出：1. 模块划分 2. 接口定义 3. 数据模型 4. 技术选型"
        ),
        depends_on=[],
    ),
    WorkflowStep(
        id="implement",
        name="代码实现",
        assigned_to="developer",
        prompt_template=(
            "请根据以下架构设计实现代码：\n\n"
            "需求: {requirement}\n\n"
            "前序输出:\n{prev_output}\n\n"
            "{context}\n\n"
            "请输出完整的代码实现。"
        ),
        depends_on=["design"],
    ),
    WorkflowStep(
        id="review",
        name="代码审查",
        assigned_to="reviewer",
        prompt_template=(
            "请审查以下代码实现：\n\n"
            "需求: {requirement}\n\n"
            "代码:\n{prev_output}\n\n"
            "{context}\n\n"
            "请检查: 1. 代码质量 2. 安全问题 3. 性能问题 4. 最佳实践"
        ),
        depends_on=["implement"],
        quality_gate="review_passed",
    ),
    WorkflowStep(
        id="test",
        name="测试验证",
        assigned_to="tester",
        prompt_template=(
            "请为以下代码编写测试并验证：\n\n"
            "需求: {requirement}\n\n"
            "代码和审查结果:\n{prev_output}\n\n"
            "{context}\n\n"
            "请输出: 1. 测试用例 2. 测试结果 3. 覆盖率报告"
        ),
        depends_on=["review"],
        quality_gate="tests_passed",
    ),
]

# 快速修复工作流
QUICK_FIX_WORKFLOW = [
    WorkflowStep(
        id="investigate",
        name="问题调查",
        assigned_to="developer",
        prompt_template=(
            "请调查以下问题：\n\n"
            "问题描述: {requirement}\n\n"
            "{context}\n\n"
            "请输出: 1. 根因分析 2. 影响范围 3. 修复方案"
        ),
        depends_on=[],
    ),
    WorkflowStep(
        id="fix",
        name="修复实现",
        assigned_to="developer",
        prompt_template=(
            "请根据调查结果修复问题：\n\n"
            "问题描述: {requirement}\n\n"
            "调查结果:\n{prev_output}\n\n"
            "{context}\n\n"
            "请输出修复代码。"
        ),
        depends_on=["investigate"],
    ),
    WorkflowStep(
        id="verify",
        name="验证修复",
        assigned_to="tester",
        prompt_template=(
            "请验证以下修复是否正确：\n\n"
            "问题描述: {requirement}\n\n"
            "修复内容:\n{prev_output}\n\n"
            "{context}\n\n"
            "请运行测试并验证修复是否有效。"
        ),
        depends_on=["fix"],
        quality_gate="tests_passed",
    ),
]

# 全栈工作流（含并行步骤）
FULL_STACK_WORKFLOW = [
    WorkflowStep(
        id="design",
        name="全栈架构设计",
        assigned_to="architect",
        prompt_template=(
            "请为以下全栈需求设计架构：\n\n"
            "需求: {requirement}\n\n"
            "{context}\n\n"
            "请输出: 1. 前后端分工 2. API 设计 3. 数据模型 4. 技术栈选型"
        ),
        depends_on=[],
    ),
    WorkflowStep(
        id="backend",
        name="后端开发",
        assigned_to="developer",
        prompt_template=(
            "请实现后端部分：\n\n"
            "需求: {requirement}\n\n"
            "架构设计:\n{prev_output}\n\n"
            "{context}\n\n"
            "请实现: API 接口、业务逻辑、数据层"
        ),
        depends_on=["design"],
    ),
    WorkflowStep(
        id="frontend",
        name="前端开发",
        assigned_to="developer",
        prompt_template=(
            "请实现前端部分：\n\n"
            "需求: {requirement}\n\n"
            "架构设计:\n{prev_output}\n\n"
            "{context}\n\n"
            "请实现: 页面组件、状态管理、API 调用"
        ),
        depends_on=["design"],  # 和 backend 并行！
    ),
    WorkflowStep(
        id="integrate",
        name="集成联调",
        assigned_to="developer",
        prompt_template=(
            "请完成前后端集成：\n\n"
            "需求: {requirement}\n\n"
            "前后端实现:\n{prev_output}\n\n"
            "{context}\n\n"
            "请完成: 接口联调、数据流验证、错误处理"
        ),
        depends_on=["backend", "frontend"],
    ),
    WorkflowStep(
        id="test",
        name="集成测试",
        assigned_to="tester",
        prompt_template=(
            "请对集成后的系统进行测试：\n\n"
            "需求: {requirement}\n\n"
            "集成结果:\n{prev_output}\n\n"
            "{context}\n\n"
            "请执行: 集成测试、E2E 测试、性能测试"
        ),
        depends_on=["integrate"],
        quality_gate="tests_passed",
    ),
]

# 工作流注册表
WORKFLOW_REGISTRY: Dict[str, List[WorkflowStep]] = {
    "standard": STANDARD_DEV_WORKFLOW,
    "standard_dev": STANDARD_DEV_WORKFLOW,
    "quick_fix": QUICK_FIX_WORKFLOW,
    "full_stack": FULL_STACK_WORKFLOW,
}



# ============================================================
# 便捷函数
# ============================================================

def create_team(
    llm: Optional[Any] = None,
    workflow_name: str = "standard",
    members: Optional[List[TeamMember]] = None,
) -> TeamAgent:
    """快速创建团队

    Args:
        llm: LLM 实例（可选，无则使用 mock 响应）
        workflow_name: 工作流名称 ("standard" / "quick_fix" / "full_stack")
        members: 团队成员列表（可选，默认使用预制团队）

    Returns:
        TeamAgent: 团队智能体实例
    """
    if members is None:
        members = DEFAULT_TEAM_MEMBERS

    workflow_steps = WORKFLOW_REGISTRY.get(workflow_name, STANDARD_DEV_WORKFLOW)

    return TeamAgent(
        llm=llm,
        members=members,
        workflow=workflow_steps,
    )


async def run_team(
    requirement: str,
    llm: Optional[Any] = None,
    workflow: str = "standard",
) -> TeamExecutionResult:
    """一键执行团队工作流

    Args:
        requirement: 需求描述
        llm: LLM 实例（可选）
        workflow: 工作流名称

    Returns:
        TeamExecutionResult: 执行结果
    """
    team = create_team(llm=llm, workflow_name=workflow)
    return await team.execute(requirement)


# ============================================================
# 模块导出
# ============================================================

__all__ = [
    # 数据结构
    "TeamMember",
    "WorkflowStep",
    "StepResult",
    "TeamExecutionResult",
    "QualityCheckResult",
    # 核心类
    "SharedContext",
    "QualityGate",
    "WorkflowDAG",
    "TeamAgent",
    # 预制工作流
    "STANDARD_DEV_WORKFLOW",
    "QUICK_FIX_WORKFLOW",
    "FULL_STACK_WORKFLOW",
    "WORKFLOW_REGISTRY",
    "DEFAULT_TEAM_MEMBERS",
    # 便捷函数
    "create_team",
    "run_team",
]
