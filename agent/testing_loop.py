"""
自动测试闭环模块 - Auto Test Loop

当 Agent 修改了代码后，自动:
1. 检测修改了哪些文件
2. 找到相关测试文件
3. 运行测试
4. 如果失败 → 把错误信息反馈给 LLM → 自动修复
5. 重复 3-4 直到通过或达到最大重试次数

提供:
- TestRunner: 异步测试执行器 (pytest/unittest)
- TestFileFinder: 源文件→测试文件映射
- AutoTestLoop: 核心闭环逻辑
- auto_test_tool: LangChain 工具集成
- register_testing_tools(): 注册函数
"""

import asyncio
import os
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============ 数据类 ============


class TestFramework(str, Enum):
    """支持的测试框架"""
    PYTEST = "pytest"
    UNITTEST = "unittest"


class VerificationStatus(str, Enum):
    """验证状态"""
    PASSED = "passed"
    FAILED = "failed"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"


@dataclass
class TestResult:
    """单次测试运行结果"""
    passed: int = 0
    failed: int = 0
    errors: int = 0
    output: str = ""
    duration: float = 0.0

    @property
    def success(self) -> bool:
        """是否全部通过"""
        return self.failed == 0 and self.errors == 0

    @property
    def total(self) -> int:
        """测试总数"""
        return self.passed + self.failed + self.errors

    def summary(self) -> str:
        """简要摘要"""
        status = "PASSED" if self.success else "FAILED"
        return (
            f"[{status}] {self.passed} passed, {self.failed} failed, "
            f"{self.errors} errors ({self.duration:.2f}s)"
        )


@dataclass
class FixRecord:
    """修复记录"""
    iteration: int
    file_path: str
    description: str
    diff_summary: str = ""


@dataclass
class VerificationResult:
    """完整验证结果"""
    status: VerificationStatus
    iterations: int = 0
    test_results: List[TestResult] = field(default_factory=list)
    fixes_applied: List[FixRecord] = field(default_factory=list)
    total_duration: float = 0.0

    def summary(self) -> str:
        """生成文本摘要"""
        lines = [
            f"=== 测试验证结果 ===",
            f"状态: {self.status.value}",
            f"迭代次数: {self.iterations}",
            f"总耗时: {self.total_duration:.2f}s",
            "",
        ]

        for i, tr in enumerate(self.test_results):
            lines.append(f"  第 {i + 1} 轮: {tr.summary()}")

        if self.fixes_applied:
            lines.append("")
            lines.append("应用的修复:")
            for fix in self.fixes_applied:
                lines.append(
                    f"  [{fix.iteration}] {fix.file_path}: {fix.description}"
                )

        return "\n".join(lines)


# ============ 常量 ============

DEFAULT_TEST_TIMEOUT = 60  # 单次测试最长 60 秒
MAX_OUTPUT_LENGTH = 5000  # 测试输出最长 5000 字符



# ============ TestFileFinder ============


class TestFileFinder:
    """
    源文件 → 测试文件映射

    默认规则:
    - src/foo.py → tests/test_foo.py
    - agent/bar.py → tests/test_bar.py
    - module/sub/baz.py → tests/test_baz.py 或 tests/sub/test_baz.py

    支持自定义映射规则。
    """

    def __init__(
        self,
        project_root: Optional[str] = None,
        custom_mappings: Optional[Dict[str, str]] = None,
        test_dirs: Optional[List[str]] = None,
    ):
        """
        初始化

        Args:
            project_root: 项目根目录
            custom_mappings: 自定义映射 {源文件模式: 测试文件模式}
            test_dirs: 测试目录列表，默认 ['tests', 'test']
        """
        self.project_root = project_root or os.getcwd()
        self.custom_mappings = custom_mappings or {}
        self.test_dirs = test_dirs or ["tests", "test"]

    def find_test_file(self, source_file: str) -> Optional[str]:
        """
        根据源文件找对应的测试文件

        Args:
            source_file: 源文件路径 (相对或绝对)

        Returns:
            测试文件路径，如果找不到返回 None
        """
        # 转为相对路径
        if os.path.isabs(source_file):
            try:
                source_file = os.path.relpath(source_file, self.project_root)
            except ValueError:
                return None

        # 跳过非 Python 文件
        if not source_file.endswith(".py"):
            return None

        # 跳过已经是测试文件的
        basename = os.path.basename(source_file)
        if basename.startswith("test_") or basename.startswith("tests_"):
            # 它本身就是测试文件
            full_path = os.path.join(self.project_root, source_file)
            return full_path if os.path.exists(full_path) else None

        # 检查自定义映射
        for pattern, test_pattern in self.custom_mappings.items():
            if pattern in source_file:
                test_file = source_file.replace(pattern, test_pattern)
                full_path = os.path.join(self.project_root, test_file)
                if os.path.exists(full_path):
                    return full_path

        # 提取文件名 (不含路径和扩展名)
        file_stem = Path(source_file).stem
        test_filename = f"test_{file_stem}.py"

        # 策略 1: 在 test_dirs 中查找
        for test_dir in self.test_dirs:
            # 直接在测试目录下
            candidate = os.path.join(self.project_root, test_dir, test_filename)
            if os.path.exists(candidate):
                return candidate

            # 保持子目录结构
            # e.g., agent/tools/bash_tool.py → tests/tools/test_bash_tool.py
            parts = Path(source_file).parts
            if len(parts) > 1:
                # 去掉第一级目录 (如 src/, agent/)，用剩余路径
                sub_path = os.path.join(*parts[1:-1]) if len(parts) > 2 else ""
                candidate = os.path.join(
                    self.project_root, test_dir, sub_path, test_filename
                )
                if os.path.exists(candidate):
                    return candidate

        # 策略 2: 同目录下的测试文件
        source_dir = os.path.dirname(source_file)
        candidate = os.path.join(self.project_root, source_dir, test_filename)
        if os.path.exists(candidate):
            return candidate

        # 策略 3: 递归搜索项目中的测试文件
        for test_dir in self.test_dirs:
            test_dir_path = os.path.join(self.project_root, test_dir)
            if os.path.isdir(test_dir_path):
                for root, _dirs, files in os.walk(test_dir_path):
                    if test_filename in files:
                        return os.path.join(root, test_filename)

        return None

    def find_related_tests(self, changed_files: List[str]) -> List[str]:
        """
        批量查找相关测试文件

        Args:
            changed_files: 修改的文件列表

        Returns:
            相关测试文件列表 (去重)
        """
        test_files = []
        seen = set()

        for source_file in changed_files:
            test_file = self.find_test_file(source_file)
            if test_file and test_file not in seen:
                test_files.append(test_file)
                seen.add(test_file)

        return test_files



# ============ TestRunner ============


class TestRunner:
    """
    异步测试执行器

    支持 pytest (默认) 和 unittest 框架。
    使用 asyncio.subprocess 运行测试。
    """

    def __init__(
        self,
        framework: TestFramework = TestFramework.PYTEST,
        timeout: int = DEFAULT_TEST_TIMEOUT,
        max_output_length: int = MAX_OUTPUT_LENGTH,
    ):
        """
        初始化

        Args:
            framework: 测试框架 (pytest/unittest)
            timeout: 单次测试超时时间 (秒)
            max_output_length: 输出最大长度 (字符)
        """
        self.framework = framework
        self.timeout = timeout
        self.max_output_length = max_output_length

    def _truncate_output(self, output: str) -> str:
        """截断过长的输出"""
        if len(output) <= self.max_output_length:
            return output
        half = self.max_output_length // 2
        return (
            output[:half]
            + f"\n\n... [输出截断，总长 {len(output)} 字符] ...\n\n"
            + output[-half:]
        )

    def _build_command(
        self, test_files: Optional[List[str]] = None
    ) -> List[str]:
        """构建测试命令"""
        if self.framework == TestFramework.PYTEST:
            cmd = ["python", "-m", "pytest", "-v", "--tb=short", "--no-header"]
            if test_files:
                cmd.extend(test_files)
            return cmd
        elif self.framework == TestFramework.UNITTEST:
            cmd = ["python", "-m", "unittest"]
            if test_files:
                # 将文件路径转换为模块路径
                for f in test_files:
                    module = f.replace("/", ".").replace("\\", ".").rstrip(".py")
                    if module.endswith(".py"):
                        module = module[:-3]
                    cmd.append(module)
            else:
                cmd.append("discover")
            return cmd
        else:
            raise ValueError(f"不支持的测试框架: {self.framework}")

    def _parse_pytest_output(self, output: str, duration: float) -> TestResult:
        """解析 pytest 输出"""
        import re

        passed = 0
        failed = 0
        errors = 0

        # 尝试匹配 pytest 摘要行
        # e.g., "3 passed, 1 failed, 1 error in 2.34s"
        summary_pattern = r"(\d+)\s+passed"
        match = re.search(summary_pattern, output)
        if match:
            passed = int(match.group(1))

        failed_pattern = r"(\d+)\s+failed"
        match = re.search(failed_pattern, output)
        if match:
            failed = int(match.group(1))

        error_pattern = r"(\d+)\s+error"
        match = re.search(error_pattern, output)
        if match:
            errors = int(match.group(1))

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            output=self._truncate_output(output),
            duration=duration,
        )

    def _parse_unittest_output(self, output: str, duration: float) -> TestResult:
        """解析 unittest 输出"""
        import re

        passed = 0
        failed = 0
        errors = 0

        # unittest 的输出格式
        # "Ran X tests in Y.YYYs"
        ran_pattern = r"Ran\s+(\d+)\s+test"
        match = re.search(ran_pattern, output)
        total = int(match.group(1)) if match else 0

        # "FAILED (failures=X, errors=Y)"
        failures_pattern = r"failures=(\d+)"
        match = re.search(failures_pattern, output)
        if match:
            failed = int(match.group(1))

        errors_pattern = r"errors=(\d+)"
        match = re.search(errors_pattern, output)
        if match:
            errors = int(match.group(1))

        passed = max(0, total - failed - errors)

        return TestResult(
            passed=passed,
            failed=failed,
            errors=errors,
            output=self._truncate_output(output),
            duration=duration,
        )

    async def run_tests(
        self,
        test_files: Optional[List[str]] = None,
        cwd: Optional[str] = None,
    ) -> TestResult:
        """
        运行指定测试文件

        Args:
            test_files: 测试文件列表，None 则运行所有
            cwd: 工作目录

        Returns:
            TestResult 结构化结果
        """
        cmd = self._build_command(test_files)
        logger.info(f"Running tests: {' '.join(cmd)}")

        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                duration = time.time() - start_time
                return TestResult(
                    passed=0,
                    failed=0,
                    errors=1,
                    output=f"测试执行超时 ({self.timeout}s)",
                    duration=duration,
                )

            duration = time.time() - start_time
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")

            # 合并输出
            combined_output = output
            if err_output:
                combined_output += f"\n[STDERR]\n{err_output}"

            # 根据框架解析
            if self.framework == TestFramework.PYTEST:
                result = self._parse_pytest_output(combined_output, duration)
            else:
                result = self._parse_unittest_output(combined_output, duration)

            # 如果解析不到数字，但退出码非零，标记为错误
            if result.total == 0 and process.returncode != 0:
                result.errors = 1
                result.output = self._truncate_output(combined_output)

            return result

        except FileNotFoundError:
            duration = time.time() - start_time
            return TestResult(
                passed=0,
                failed=0,
                errors=1,
                output="错误: 测试命令未找到，请确保已安装测试框架",
                duration=duration,
            )
        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                passed=0,
                failed=0,
                errors=1,
                output=f"错误: {type(e).__name__}: {str(e)}",
                duration=duration,
            )

    async def run_all_tests(self, cwd: Optional[str] = None) -> TestResult:
        """
        运行项目所有测试

        Args:
            cwd: 工作目录

        Returns:
            TestResult
        """
        return await self.run_tests(test_files=None, cwd=cwd)

    async def run_related_tests(
        self,
        changed_files: List[str],
        cwd: Optional[str] = None,
        finder: Optional["TestFileFinder"] = None,
    ) -> TestResult:
        """
        根据修改的文件找到并运行相关测试

        Args:
            changed_files: 修改的文件列表
            cwd: 工作目录
            finder: TestFileFinder 实例

        Returns:
            TestResult
        """
        if finder is None:
            finder = TestFileFinder(project_root=cwd or os.getcwd())

        test_files = finder.find_related_tests(changed_files)

        if not test_files:
            logger.info("未找到相关测试文件，运行所有测试")
            return await self.run_all_tests(cwd=cwd)

        logger.info(f"找到 {len(test_files)} 个相关测试文件")
        return await self.run_tests(test_files=test_files, cwd=cwd)



# ============ AutoTestLoop ============


class AutoTestLoop:
    """
    核心自动测试闭环

    流程:
    1. find_related_tests(changed_files)
    2. run_tests(test_files)
    3. if all passed → return success
    4. if failed → 构建修复 prompt (包含错误信息 + 源代码)
    5. 调用 LLM 获取修复建议
    6. 应用修复 (file_edit)
    7. 回到步骤 2
    8. 达到 max_retries → return failure with summary
    """

    def __init__(
        self,
        llm: Optional[Any] = None,
        max_retries: int = 3,
        test_runner: Optional[TestRunner] = None,
        cwd: Optional[str] = None,
        file_finder: Optional[TestFileFinder] = None,
        apply_fix_fn: Optional[Callable] = None,
    ):
        """
        初始化

        Args:
            llm: LLM 实例 (langchain BaseChatModel)，None 则只运行测试不修复
            max_retries: 最大重试次数
            test_runner: 测试运行器
            cwd: 工作目录
            file_finder: 测试文件查找器
            apply_fix_fn: 应用修复的函数，签名: async (file_path, new_content) -> bool
        """
        self.llm = llm
        self.max_retries = max_retries
        self.test_runner = test_runner or TestRunner()
        self.cwd = cwd or os.getcwd()
        self.file_finder = file_finder or TestFileFinder(project_root=self.cwd)
        self.apply_fix_fn = apply_fix_fn or self._default_apply_fix

    @staticmethod
    async def _default_apply_fix(file_path: str, new_content: str) -> bool:
        """默认的修复应用函数: 直接写入文件"""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return True
        except Exception as e:
            logger.error(f"写入文件失败 {file_path}: {e}")
            return False

    def _build_fix_prompt(
        self,
        test_result: TestResult,
        changed_files: List[str],
    ) -> str:
        """
        构建修复 prompt

        包含:
        - 测试错误输出
        - 相关源文件内容
        """
        parts = [
            "测试运行失败，请分析错误并提供修复。",
            "",
            "## 测试输出",
            "```",
            test_result.output[-3000:],  # 只取最后 3000 字符的错误
            "```",
            "",
            "## 相关源文件",
        ]

        for file_path in changed_files:
            abs_path = file_path
            if not os.path.isabs(file_path):
                abs_path = os.path.join(self.cwd, file_path)

            if os.path.exists(abs_path):
                try:
                    with open(abs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # 限制单个文件内容长度
                    if len(content) > 3000:
                        content = content[:3000] + "\n... (文件截断)"
                    parts.append(f"\n### {file_path}")
                    parts.append("```python")
                    parts.append(content)
                    parts.append("```")
                except Exception:
                    pass

        parts.extend([
            "",
            "## 要求",
            "请分析测试失败原因，返回修复后的文件内容。",
            "格式要求：",
            "对每个需要修复的文件，用以下格式:",
            "===FILE: <文件路径>===",
            "<完整的修复后文件内容>",
            "===END FILE===",
            "",
            "只输出需要修改的文件，保持其他文件不变。",
        ])

        return "\n".join(parts)

    def _parse_fix_response(self, response: str) -> Dict[str, str]:
        """
        解析 LLM 的修复响应

        Returns:
            {file_path: new_content}
        """
        import re

        fixes = {}

        # 匹配 ===FILE: path=== ... ===END FILE===
        pattern = r"===FILE:\s*(.+?)\s*===\s*\n(.*?)===END FILE==="
        matches = re.findall(pattern, response, re.DOTALL)

        for file_path, content in matches:
            # 清理内容 (去除可能的 markdown 代码块标记)
            content = content.strip()
            if content.startswith("```"):
                first_newline = content.index("\n")
                content = content[first_newline + 1:]
            if content.endswith("```"):
                content = content[:-3].rstrip()

            fixes[file_path.strip()] = content

        return fixes

    async def _get_llm_fix(
        self,
        test_result: TestResult,
        changed_files: List[str],
    ) -> Dict[str, str]:
        """
        调用 LLM 获取修复建议

        Returns:
            {file_path: new_content} 修复映射
        """
        if self.llm is None:
            return {}

        prompt = self._build_fix_prompt(test_result, changed_files)

        try:
            # 兼容 langchain 的 BaseChatModel
            if hasattr(self.llm, "ainvoke"):
                response = await self.llm.ainvoke(prompt)
                response_text = (
                    response.content
                    if hasattr(response, "content")
                    else str(response)
                )
            elif hasattr(self.llm, "invoke"):
                response = self.llm.invoke(prompt)
                response_text = (
                    response.content
                    if hasattr(response, "content")
                    else str(response)
                )
            else:
                # 尝试直接调用
                response_text = str(self.llm(prompt))

            return self._parse_fix_response(response_text)

        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return {}

    async def run(self, changed_files: List[str]) -> VerificationResult:
        """
        执行完整的测试闭环

        Args:
            changed_files: 修改的文件列表

        Returns:
            VerificationResult
        """
        start_time = time.time()
        test_results: List[TestResult] = []
        fixes_applied: List[FixRecord] = []
        iteration = 0

        # 查找相关测试
        test_files = self.file_finder.find_related_tests(changed_files)
        logger.info(
            f"开始测试闭环: {len(changed_files)} 个修改文件, "
            f"{len(test_files)} 个测试文件, 最大重试 {self.max_retries} 次"
        )

        while iteration <= self.max_retries:
            iteration += 1
            logger.info(f"=== 第 {iteration} 轮测试 ===")

            # 运行测试
            if test_files:
                result = await self.test_runner.run_tests(
                    test_files=test_files, cwd=self.cwd
                )
            else:
                result = await self.test_runner.run_all_tests(cwd=self.cwd)

            test_results.append(result)
            logger.info(f"测试结果: {result.summary()}")

            # 全部通过
            if result.success:
                total_duration = time.time() - start_time
                return VerificationResult(
                    status=VerificationStatus.PASSED,
                    iterations=iteration,
                    test_results=test_results,
                    fixes_applied=fixes_applied,
                    total_duration=total_duration,
                )

            # 达到最大重试 (最后一次不需要再修复)
            if iteration > self.max_retries:
                break

            # 没有 LLM，无法修复
            if self.llm is None:
                logger.warning("没有配置 LLM，无法自动修复")
                break

            # 获取 LLM 修复建议
            logger.info("请求 LLM 修复建议...")
            fixes = await self._get_llm_fix(result, changed_files)

            if not fixes:
                logger.warning("LLM 未返回修复建议")
                break

            # 应用修复
            for file_path, new_content in fixes.items():
                abs_path = file_path
                if not os.path.isabs(file_path):
                    abs_path = os.path.join(self.cwd, file_path)

                success = await self.apply_fix_fn(abs_path, new_content)
                if success:
                    fix_record = FixRecord(
                        iteration=iteration,
                        file_path=file_path,
                        description=f"LLM 自动修复 (第 {iteration} 轮)",
                        diff_summary=f"文件已更新: {file_path}",
                    )
                    fixes_applied.append(fix_record)
                    logger.info(f"已应用修复: {file_path}")
                else:
                    logger.error(f"修复应用失败: {file_path}")

        # 循环结束但测试仍然失败
        total_duration = time.time() - start_time
        return VerificationResult(
            status=VerificationStatus.MAX_RETRIES_EXCEEDED,
            iterations=iteration,
            test_results=test_results,
            fixes_applied=fixes_applied,
            total_duration=total_duration,
        )

    async def run_and_fix(
        self,
        test_command: str,
        cwd: Optional[str] = None,
    ) -> VerificationResult:
        """
        简单版本: 运行指定测试命令并自动修复

        Args:
            test_command: 测试命令 (如 "pytest tests/test_foo.py")
            cwd: 工作目录

        Returns:
            VerificationResult
        """
        work_dir = cwd or self.cwd
        start_time = time.time()
        test_results: List[TestResult] = []
        fixes_applied: List[FixRecord] = []
        iteration = 0

        while iteration <= self.max_retries:
            iteration += 1
            logger.info(f"=== 第 {iteration} 轮 (命令模式) ===")

            # 直接用 subprocess 运行命令
            result = await self._run_command(test_command, work_dir)
            test_results.append(result)

            if result.success:
                total_duration = time.time() - start_time
                return VerificationResult(
                    status=VerificationStatus.PASSED,
                    iterations=iteration,
                    test_results=test_results,
                    fixes_applied=fixes_applied,
                    total_duration=total_duration,
                )

            if iteration > self.max_retries:
                break

            if self.llm is None:
                break

            # 从命令中推断相关文件
            inferred_files = self._infer_files_from_command(test_command)
            fixes = await self._get_llm_fix(result, inferred_files)

            if not fixes:
                break

            for file_path, new_content in fixes.items():
                abs_path = file_path
                if not os.path.isabs(file_path):
                    abs_path = os.path.join(work_dir, file_path)
                success = await self.apply_fix_fn(abs_path, new_content)
                if success:
                    fixes_applied.append(FixRecord(
                        iteration=iteration,
                        file_path=file_path,
                        description=f"命令模式修复 (第 {iteration} 轮)",
                    ))

        total_duration = time.time() - start_time
        return VerificationResult(
            status=VerificationStatus.MAX_RETRIES_EXCEEDED,
            iterations=iteration,
            test_results=test_results,
            fixes_applied=fixes_applied,
            total_duration=total_duration,
        )

    async def _run_command(self, command: str, cwd: str) -> TestResult:
        """直接运行测试命令"""
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.test_runner.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                duration = time.time() - start_time
                return TestResult(
                    errors=1,
                    output=f"命令执行超时 ({self.test_runner.timeout}s)",
                    duration=duration,
                )

            duration = time.time() - start_time
            output = stdout.decode("utf-8", errors="replace")
            err_output = stderr.decode("utf-8", errors="replace")
            combined = output + (f"\n{err_output}" if err_output else "")

            # 根据退出码判断
            if process.returncode == 0:
                return self.test_runner._parse_pytest_output(combined, duration)
            else:
                result = self.test_runner._parse_pytest_output(combined, duration)
                if result.failed == 0 and result.errors == 0:
                    result.failed = 1  # 至少标记一个失败
                return result

        except Exception as e:
            duration = time.time() - start_time
            return TestResult(
                errors=1,
                output=f"命令执行错误: {type(e).__name__}: {str(e)}",
                duration=duration,
            )

    @staticmethod
    def _infer_files_from_command(command: str) -> List[str]:
        """从测试命令中推断相关文件"""
        import re

        files = []
        # 匹配类似 tests/test_foo.py 的模式
        patterns = re.findall(r"[\w/\\]+\.py", command)
        for p in patterns:
            # 从测试文件推断源文件
            basename = os.path.basename(p)
            if basename.startswith("test_"):
                source_name = basename[5:]  # 去掉 test_ 前缀
                files.append(source_name)
            files.append(p)
        return files



# ============ LangChain 工具集成 ============


class AutoTestInput(BaseModel):
    """自动测试工具输入"""
    changed_files: Optional[List[str]] = Field(
        default=None,
        description="修改的文件列表，用于查找相关测试并运行",
    )
    test_command: Optional[str] = Field(
        default=None,
        description="直接指定测试命令 (如 'pytest tests/test_foo.py -v')",
    )
    cwd: Optional[str] = Field(
        default=None,
        description="工作目录",
    )


# 全局 AutoTestLoop 实例 (延迟初始化)
_global_loop: Optional[AutoTestLoop] = None


def get_or_create_loop(
    llm: Optional[Any] = None,
    cwd: Optional[str] = None,
) -> AutoTestLoop:
    """获取或创建全局 AutoTestLoop 实例"""
    global _global_loop
    if _global_loop is None:
        _global_loop = AutoTestLoop(llm=llm, cwd=cwd)
    return _global_loop


def set_global_loop(loop: AutoTestLoop) -> None:
    """设置全局 AutoTestLoop 实例"""
    global _global_loop
    _global_loop = loop


async def auto_test_execute(
    changed_files: Optional[List[str]] = None,
    test_command: Optional[str] = None,
    cwd: Optional[str] = None,
) -> str:
    """
    执行自动测试闭环

    两种模式:
    1. changed_files 模式: 根据修改文件查找并运行相关测试
    2. test_command 模式: 直接运行指定测试命令

    如果测试失败且配置了 LLM，会自动尝试修复。
    """
    loop = get_or_create_loop(cwd=cwd)

    # 如果提供了 cwd，更新工作目录
    if cwd:
        loop.cwd = cwd
        loop.file_finder.project_root = cwd

    if test_command:
        result = await loop.run_and_fix(test_command, cwd=cwd)
    elif changed_files:
        result = await loop.run(changed_files)
    else:
        # 没有参数，运行所有测试
        test_result = await loop.test_runner.run_all_tests(cwd=cwd or loop.cwd)
        result = VerificationResult(
            status=(
                VerificationStatus.PASSED
                if test_result.success
                else VerificationStatus.FAILED
            ),
            iterations=1,
            test_results=[test_result],
            total_duration=test_result.duration,
        )

    return result.summary()


def _create_auto_test_tool():
    """创建 auto_test LangChain 工具 (延迟导入避免循环依赖)"""
    try:
        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            func=auto_test_execute,
            name="auto_test",
            description=(
                "自动测试闭环工具。"
                "输入修改的文件列表或测试命令，自动运行测试。"
                "如果测试失败且配置了 LLM，会自动尝试修复并重试。"
                "返回结构化的验证结果。"
            ),
            args_schema=AutoTestInput,
            coroutine=auto_test_execute,
        )
    except ImportError:
        logger.warning("langchain_core 未安装，auto_test_tool 不可用")
        return None


# 延迟创建工具实例
auto_test_tool: Optional[Any] = None


def get_auto_test_tool():
    """获取 auto_test 工具 (延迟初始化)"""
    global auto_test_tool
    if auto_test_tool is None:
        auto_test_tool = _create_auto_test_tool()
    return auto_test_tool


# ============ 注册函数 ============


def register_testing_tools(registry) -> None:
    """
    注册测试工具到 ToolRegistry

    Args:
        registry: ToolRegistry 实例
    """
    tool = get_auto_test_tool()
    if tool is not None:
        registry.register(
            tool,
            category="testing",
            tags=["test", "auto-fix", "verification"],
        )
        logger.info("已注册 auto_test 工具")
    else:
        logger.warning("auto_test 工具创建失败，跳过注册")


# ============ 便捷函数 ============


async def quick_test(
    changed_files: List[str],
    cwd: Optional[str] = None,
    framework: TestFramework = TestFramework.PYTEST,
) -> TestResult:
    """
    快速运行相关测试 (不修复)

    Args:
        changed_files: 修改的文件列表
        cwd: 工作目录
        framework: 测试框架

    Returns:
        TestResult
    """
    runner = TestRunner(framework=framework)
    finder = TestFileFinder(project_root=cwd or os.getcwd())
    return await runner.run_related_tests(changed_files, cwd=cwd, finder=finder)


async def test_and_fix(
    changed_files: List[str],
    llm: Optional[Any] = None,
    cwd: Optional[str] = None,
    max_retries: int = 3,
) -> VerificationResult:
    """
    运行测试并自动修复 (便捷函数)

    Args:
        changed_files: 修改的文件列表
        llm: LLM 实例 (可选)
        cwd: 工作目录
        max_retries: 最大重试次数

    Returns:
        VerificationResult
    """
    loop = AutoTestLoop(llm=llm, max_retries=max_retries, cwd=cwd)
    return await loop.run(changed_files)


# ============ 模块导出 ============

__all__ = [
    # 枚举
    "TestFramework",
    "VerificationStatus",
    # 数据类
    "TestResult",
    "FixRecord",
    "VerificationResult",
    # 核心类
    "TestFileFinder",
    "TestRunner",
    "AutoTestLoop",
    # 工具
    "get_auto_test_tool",
    "register_testing_tools",
    # 便捷函数
    "quick_test",
    "test_and_fix",
    "get_or_create_loop",
    "set_global_loop",
]
