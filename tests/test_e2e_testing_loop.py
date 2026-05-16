"""
自动测试闭环端到端测试

使用真实文件系统和真实 pytest:
- 创建通过的测试 → TestRunner 运行 → 验证 passed > 0
- 创建失败的测试 → 运行 → 验证 failed > 0
- TestFileFinder 映射测试
- 无 LLM 时只运行测试不修复
"""
import pytest
import os
import sys
import asyncio
from unittest.mock import patch

from agent.testing_loop import (
    TestRunner,
    TestFileFinder,
    TestResult,
    AutoTestLoop,
    VerificationStatus,
    TestFramework,
)


# 获取正确的 python 可执行文件路径（当前运行 pytest 的解释器）
PYTHON_EXECUTABLE = sys.executable


class PatchedTestRunner(TestRunner):
    """使用当前 Python 解释器的 TestRunner 子类"""

    def _build_command(self, test_files=None):
        """使用正确的 Python 解释器"""
        cmd = [PYTHON_EXECUTABLE, "-m", "pytest", "-v", "--tb=short", "--no-header"]
        if test_files:
            cmd.extend(test_files)
        return cmd


class TestPassingTestsDetected:
    """创建通过的测试文件 → TestRunner 运行 → 验证 passed > 0"""

    @pytest.mark.asyncio
    async def test_passing_tests_detected(self, tmp_path):
        """运行一个通过的测试文件"""
        # 创建一个简单的通过测试
        test_file = tmp_path / "test_pass.py"
        test_file.write_text(
            "def test_addition():\n"
            "    assert 1 + 1 == 2\n\n"
            "def test_string():\n"
            "    assert 'hello'.upper() == 'HELLO'\n"
        )

        runner = PatchedTestRunner(framework=TestFramework.PYTEST, timeout=30)
        result = await runner.run_tests(
            test_files=[str(test_file)],
            cwd=str(tmp_path),
        )

        assert result.passed >= 2
        assert result.failed == 0
        assert result.success is True
        assert result.duration > 0

    @pytest.mark.asyncio
    async def test_empty_test_file(self, tmp_path):
        """运行空测试文件"""
        test_file = tmp_path / "test_empty.py"
        test_file.write_text("# no tests here\n")

        runner = PatchedTestRunner(framework=TestFramework.PYTEST, timeout=30)
        result = await runner.run_tests(
            test_files=[str(test_file)],
            cwd=str(tmp_path),
        )

        # 没有测试但不应报错 (pytest 返回 exit code 5 for no tests)
        assert result.failed == 0


class TestFailingTestsDetected:
    """创建失败的测试文件 → 运行 → 验证 failed > 0"""

    @pytest.mark.asyncio
    async def test_failing_tests_detected(self, tmp_path):
        """运行一个失败的测试文件"""
        test_file = tmp_path / "test_fail.py"
        test_file.write_text(
            "def test_will_pass():\n"
            "    assert True\n\n"
            "def test_will_fail():\n"
            "    assert 1 == 2, 'Expected failure'\n"
        )

        runner = PatchedTestRunner(framework=TestFramework.PYTEST, timeout=30)
        result = await runner.run_tests(
            test_files=[str(test_file)],
            cwd=str(tmp_path),
        )

        assert result.failed >= 1
        assert result.passed >= 1
        assert result.success is False
        assert "Expected failure" in result.output or "1 failed" in result.output


class TestTestFileFinder:
    """创建 src/foo.py 和 tests/test_foo.py → finder 能找到映射"""

    def test_test_file_finder(self, tmp_path):
        """源文件到测试文件的映射"""
        # 创建目录结构
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        # 创建源文件和测试文件
        (src_dir / "foo.py").write_text("def foo(): return 42\n")
        (test_dir / "test_foo.py").write_text("from src.foo import foo\ndef test_foo(): assert foo() == 42\n")

        # 创建 finder
        finder = TestFileFinder(
            project_root=str(tmp_path),
            test_dirs=["tests"],
        )

        # 查找映射
        test_file = finder.find_test_file("src/foo.py")
        assert test_file is not None
        assert "test_foo.py" in test_file

    def test_test_file_finder_no_match(self, tmp_path):
        """找不到对应测试文件时返回 None"""
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        (src_dir / "bar.py").write_text("def bar(): pass\n")

        finder = TestFileFinder(
            project_root=str(tmp_path),
            test_dirs=["tests"],
        )

        result = finder.find_test_file("src/bar.py")
        assert result is None

    def test_find_related_tests_batch(self, tmp_path):
        """批量查找相关测试"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_alpha.py").write_text("def test_a(): pass\n")
        (test_dir / "test_beta.py").write_text("def test_b(): pass\n")

        finder = TestFileFinder(
            project_root=str(tmp_path),
            test_dirs=["tests"],
        )

        related = finder.find_related_tests(["alpha.py", "beta.py", "gamma.py"])
        assert len(related) == 2  # gamma 没有对应测试


class TestAutoLoopWithoutLLM:
    """无 LLM 时，只运行测试不尝试修复"""

    @pytest.mark.asyncio
    async def test_auto_loop_without_llm(self, tmp_path):
        """无 LLM 的 AutoTestLoop 只报告结果不修复"""
        # 创建一个失败的测试
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_broken.py"
        test_file.write_text(
            "def test_broken():\n"
            "    assert False, 'This should fail'\n"
        )

        # 创建 AutoTestLoop，不传入 LLM，使用 PatchedTestRunner
        loop = AutoTestLoop(
            llm=None,
            max_retries=3,
            test_runner=PatchedTestRunner(framework=TestFramework.PYTEST, timeout=30),
            cwd=str(tmp_path),
        )

        # 运行（手动指定测试文件来源）
        result = await loop.run(changed_files=[str(test_file)])

        # 应该是 MAX_RETRIES_EXCEEDED 或 FAILED，但不会崩溃
        # 没有 LLM 意味着不能修复，第一次失败后就停止
        assert result.status in (
            VerificationStatus.FAILED,
            VerificationStatus.MAX_RETRIES_EXCEEDED,
        )
        assert len(result.test_results) >= 1
        assert result.fixes_applied == []  # 没有 LLM 就没有修复

    @pytest.mark.asyncio
    async def test_auto_loop_passing_without_llm(self, tmp_path):
        """无 LLM 但测试通过"""
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_ok.py"
        test_file.write_text(
            "def test_ok():\n"
            "    assert 1 + 1 == 2\n"
        )

        loop = AutoTestLoop(
            llm=None,
            max_retries=3,
            test_runner=PatchedTestRunner(framework=TestFramework.PYTEST, timeout=30),
            cwd=str(tmp_path),
        )

        result = await loop.run(changed_files=[str(test_file)])

        assert result.status == VerificationStatus.PASSED
        assert result.iterations == 1
        assert result.test_results[0].success is True
