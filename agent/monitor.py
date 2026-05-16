"""
主动监控 Agent - 定时扫描项目发现问题

后台运行的监控 Agent，定期扫描项目代码，主动发现语法错误、
安全隐患、代码质量问题等，并通过回调通知机制报告给用户。

用法:
    monitor = ProjectMonitor("/path/to/project", check_interval=300)
    monitor.on_issue_found(my_callback)
    await monitor.start()
"""

import ast
import asyncio
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Set

logger = logging.getLogger(__name__)

# 需要跳过的目录
SKIP_DIRS: Set[str] = {"__pycache__", ".venv", "node_modules", ".git", "venv", ".tox",
                        ".mypy_cache", ".pytest_cache", ".ruff_cache", "dist", "build",
                        ".eggs"}


@dataclass
class Issue:
    """监控发现的问题"""
    severity: str  # "critical" | "warning" | "info"
    category: str  # "syntax" | "test" | "security" | "quality" | "todo"
    file: str
    line: Optional[int] = None
    message: str = ""
    suggestion: Optional[str] = None
    confidence: float = 1.0  # 置信度 0.0 ~ 1.0

    def format(self) -> str:
        """格式化为可读字符串"""
        icon = {"critical": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "•")
        loc = f"{self.file}:{self.line}" if self.line else self.file
        text = f"{icon} [{self.severity}/{self.category}] {loc} - {self.message}"
        if self.suggestion:
            text += f"\n   💡 建议: {self.suggestion}"
        return text


class ProjectMonitor:
    """主动监控 Agent - 定时扫描项目发现问题"""

    def __init__(self, project_path: str, check_interval: int = 300):
        """
        初始化监控 Agent。

        Args:
            project_path: 要监控的项目根目录路径
            check_interval: 检查间隔（秒），默认 300 秒
        """
        self.project_path = Path(os.path.abspath(project_path))
        self.check_interval = check_interval
        self._running = False
        self._callbacks: List[Callable[[Issue], None]] = []
        self._issues_history: List[Issue] = []

        # 安全模式检测的正则
        self._security_patterns = [
            # 硬编码密钥/密码
            (re.compile(r'''(?:password|passwd|pwd|secret|api_key|apikey|token|access_key)\s*=\s*['"][^'"]{4,}['"]''', re.IGNORECASE),
             "硬编码的密钥或密码", "使用环境变量或配置文件管理敏感信息"),
            # SQL 注入风险
            (re.compile(r'''(?:execute|cursor\.execute)\s*\(\s*[f"'].*?\{.*?\}''', re.IGNORECASE),
             "可能存在 SQL 注入风险 (f-string 拼接 SQL)", "使用参数化查询"),
            (re.compile(r'''(?:execute|cursor\.execute)\s*\(\s*.*?%\s*[\(]''', re.IGNORECASE),
             "可能存在 SQL 注入风险 (% 格式化 SQL)", "使用参数化查询"),
            # eval/exec
            (re.compile(r'''\beval\s*\('''),
             "使用了 eval()，可能存在代码注入风险", "避免使用 eval，考虑使用 ast.literal_eval 或其他安全替代"),
            (re.compile(r'''\bexec\s*\('''),
             "使用了 exec()，可能存在代码注入风险", "避免使用 exec，使用更安全的方式执行逻辑"),
            # pickle 反序列化
            (re.compile(r'''pickle\.loads?\s*\('''),
             "使用 pickle 加载数据，可能存在反序列化漏洞", "对不可信数据避免使用 pickle"),
        ]

    def on_issue_found(self, callback: Callable[[Issue], None]):
        """注册问题发现时的回调函数。

        Args:
            callback: 接收 Issue 对象的回调函数
        """
        self._callbacks.append(callback)

    def _notify(self, issue: Issue):
        """通知所有注册的回调"""
        self._issues_history.append(issue)
        for cb in self._callbacks:
            try:
                cb(issue)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")

    def _iter_py_files(self) -> List[Path]:
        """遍历项目中的所有 .py 文件（跳过忽略目录）"""
        py_files = []
        for root, dirs, files in os.walk(self.project_path):
            # 原地修改 dirs 以跳过忽略目录
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for filename in files:
                if filename.endswith(".py"):
                    py_files.append(Path(root) / filename)
        return py_files

    def _rel_path(self, filepath: Path) -> str:
        """获取相对于项目根目录的路径"""
        try:
            return str(filepath.relative_to(self.project_path))
        except ValueError:
            return str(filepath)

    # ─── 检查方法 ──────────────────────────────────────────────────────────────

    async def check_syntax_errors(self) -> List[Issue]:
        """扫描所有 .py 文件的语法错误 (使用 ast.parse)"""
        issues = []
        for filepath in self._iter_py_files():
            try:
                source = filepath.read_text(encoding="utf-8", errors="replace")
                ast.parse(source, filename=str(filepath))
            except SyntaxError as e:
                issue = Issue(
                    severity="critical",
                    category="syntax",
                    file=self._rel_path(filepath),
                    line=e.lineno,
                    message=f"语法错误: {e.msg}",
                    suggestion="修复语法错误以确保代码可以正常运行",
                    confidence=1.0,
                )
                issues.append(issue)
                self._notify(issue)
            except Exception as e:
                logger.debug(f"解析文件失败 {filepath}: {e}")
        return issues

    async def check_import_errors(self) -> List[Issue]:
        """检测无效导入（通过静态分析 AST 检查导入语句）"""
        issues = []
        stdlib_modules = set(sys.stdlib_module_names) if hasattr(sys, 'stdlib_module_names') else set()

        for filepath in self._iter_py_files():
            try:
                source = filepath.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(filepath))
            except (SyntaxError, Exception):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        if not self._can_resolve_module(module_name, filepath, stdlib_modules):
                            issue = Issue(
                                severity="warning",
                                category="syntax",
                                file=self._rel_path(filepath),
                                line=node.lineno,
                                message=f"可能无效的导入: {alias.name}",
                                suggestion=f"确认模块 '{alias.name}' 已安装或路径正确",
                                confidence=0.7,
                            )
                            issues.append(issue)
                            self._notify(issue)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        if not self._can_resolve_module(module_name, filepath, stdlib_modules):
                            issue = Issue(
                                severity="warning",
                                category="syntax",
                                file=self._rel_path(filepath),
                                line=node.lineno,
                                message=f"可能无效的导入: from {node.module}",
                                suggestion=f"确认模块 '{node.module}' 已安装或路径正确",
                                confidence=0.7,
                            )
                            issues.append(issue)
                            self._notify(issue)
        return issues

    def _can_resolve_module(self, module_name: str, source_file: Path, stdlib_modules: Set[str]) -> bool:
        """检查模块是否可以解析（简单启发式检查）"""
        # 标准库模块
        if stdlib_modules and module_name in stdlib_modules:
            return True
        # 相对路径的本地模块 - 检查项目里是否存在
        local_path = self.project_path / module_name
        if local_path.exists() or local_path.with_suffix(".py").exists():
            return True
        # 常见第三方包（简单白名单）
        common_packages = {
            "pytest", "numpy", "pandas", "requests", "flask", "django",
            "fastapi", "pydantic", "sqlalchemy", "celery", "redis",
            "boto3", "aiohttp", "httpx", "uvicorn", "gunicorn",
            "yaml", "toml", "dotenv", "click", "typer", "rich",
            "openai", "langchain", "transformers", "torch", "tensorflow",
            "setuptools", "pip", "pkg_resources", "importlib",
        }
        if module_name in common_packages:
            return True
        # 尝试 importlib 检查（不实际导入）
        try:
            import importlib.util
            spec = importlib.util.find_spec(module_name)
            return spec is not None
        except (ModuleNotFoundError, ValueError):
            return False

    async def check_test_health(self) -> List[Issue]:
        """运行测试，检查是否有失败的测试"""
        issues = []
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--tb=line", "-q", "--no-header", "-x"],
                capture_output=True,
                text=True,
                cwd=str(self.project_path),
                timeout=120,
            )

            if result.returncode != 0:
                # 解析 pytest 输出找到失败的测试
                output = result.stdout + result.stderr
                failed_lines = [l for l in output.split("\n") if "FAILED" in l or "ERROR" in l]

                issue = Issue(
                    severity="warning",
                    category="test",
                    file="tests/",
                    line=None,
                    message=f"测试失败 (exit code {result.returncode}): {len(failed_lines)} 个失败",
                    suggestion="运行 pytest -v 查看详细失败信息并修复测试",
                    confidence=1.0,
                )
                issues.append(issue)
                self._notify(issue)

                # 为每个失败的测试创建单独的 issue
                for line in failed_lines[:10]:  # 最多报告 10 个
                    issue = Issue(
                        severity="warning",
                        category="test",
                        file=line.strip()[:200],
                        line=None,
                        message="测试失败",
                        confidence=1.0,
                    )
                    issues.append(issue)
                    self._notify(issue)

        except subprocess.TimeoutExpired:
            issue = Issue(
                severity="warning",
                category="test",
                file="tests/",
                line=None,
                message="测试执行超时 (>120秒)",
                suggestion="检查是否有死循环或过慢的测试",
                confidence=1.0,
            )
            issues.append(issue)
            self._notify(issue)
        except FileNotFoundError:
            logger.debug("pytest 不可用，跳过测试健康检查")

        return issues

    async def check_large_functions(self) -> List[Issue]:
        """找出超过 50 行的函数，建议拆分"""
        issues = []
        max_lines = 50

        for filepath in self._iter_py_files():
            try:
                source = filepath.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(filepath))
            except (SyntaxError, Exception):
                continue

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # 计算函数体行数
                    if node.body:
                        start_line = node.lineno
                        end_line = max(
                            getattr(n, 'end_lineno', getattr(n, 'lineno', start_line))
                            for n in ast.walk(node)
                            if hasattr(n, 'lineno')
                        )
                        func_lines = end_line - start_line + 1

                        if func_lines > max_lines:
                            issue = Issue(
                                severity="info",
                                category="quality",
                                file=self._rel_path(filepath),
                                line=node.lineno,
                                message=f"函数 '{node.name}' 有 {func_lines} 行 (超过 {max_lines} 行)",
                                suggestion=f"考虑将函数 '{node.name}' 拆分为更小的子函数以提高可读性",
                                confidence=0.9,
                            )
                            issues.append(issue)
                            self._notify(issue)

        return issues

    async def check_todo_fixme(self) -> List[Issue]:
        """扫描代码中的 TODO/FIXME 注释"""
        issues = []
        pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX|BUG)\b[:\s]*(.*)', re.IGNORECASE)

        for filepath in self._iter_py_files():
            try:
                lines = filepath.read_text(encoding="utf-8", errors="replace").split("\n")
            except Exception:
                continue

            for i, line in enumerate(lines, start=1):
                match = pattern.search(line)
                if match:
                    tag = match.group(1).upper()
                    comment = match.group(2).strip()
                    severity = "warning" if tag in ("FIXME", "BUG") else "info"

                    issue = Issue(
                        severity=severity,
                        category="todo",
                        file=self._rel_path(filepath),
                        line=i,
                        message=f"{tag}: {comment}" if comment else f"发现 {tag} 标记",
                        suggestion="处理或移除此标记",
                        confidence=1.0,
                    )
                    issues.append(issue)
                    self._notify(issue)

        return issues

    async def check_unused_imports(self) -> List[Issue]:
        """检测未使用的导入"""
        issues = []

        for filepath in self._iter_py_files():
            try:
                source = filepath.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source, filename=str(filepath))
            except (SyntaxError, Exception):
                continue

            # 收集所有导入的名称
            imported_names = {}  # name -> lineno
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        name = alias.asname if alias.asname else alias.name.split(".")[0]
                        imported_names[name] = node.lineno
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "*":
                            continue
                        name = alias.asname if alias.asname else alias.name
                        imported_names[name] = node.lineno

            # 收集所有使用的名称（排除导入节点本身）
            used_names: Set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    # 处理 module.attr 的情况
                    if isinstance(node.value, ast.Name):
                        used_names.add(node.value.id)

            # 检查 __all__ 中列出的名称
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        used_names.add(elt.value)

            # 找出未使用的导入
            for name, lineno in imported_names.items():
                if name.startswith("_"):
                    continue  # 跳过下划线开头的（通常是有意为之）
                if name not in used_names:
                    issue = Issue(
                        severity="info",
                        category="quality",
                        file=self._rel_path(filepath),
                        line=lineno,
                        message=f"未使用的导入: '{name}'",
                        suggestion=f"移除未使用的导入 '{name}' 或添加 '# noqa' 注释",
                        confidence=0.8,
                    )
                    issues.append(issue)
                    self._notify(issue)

        return issues

    async def check_security_patterns(self) -> List[Issue]:
        """检测硬编码密钥、SQL 注入等安全模式"""
        issues = []

        for filepath in self._iter_py_files():
            try:
                lines = filepath.read_text(encoding="utf-8", errors="replace").split("\n")
            except Exception:
                continue

            for i, line in enumerate(lines, start=1):
                # 跳过注释行
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern, message, suggestion in self._security_patterns:
                    if pattern.search(line):
                        issue = Issue(
                            severity="critical",
                            category="security",
                            file=self._rel_path(filepath),
                            line=i,
                            message=message,
                            suggestion=suggestion,
                            confidence=0.8,
                        )
                        issues.append(issue)
                        self._notify(issue)
                        break  # 每行只报告一个安全问题

        return issues

    # ─── 生命周期管理 ──────────────────────────────────────────────────────────

    async def check_once(self) -> List[Issue]:
        """执行一次完整检查，返回所有发现的问题"""
        all_issues: List[Issue] = []

        checks = [
            ("syntax_errors", self.check_syntax_errors),
            ("import_errors", self.check_import_errors),
            ("large_functions", self.check_large_functions),
            ("todo_fixme", self.check_todo_fixme),
            ("unused_imports", self.check_unused_imports),
            ("security_patterns", self.check_security_patterns),
            ("test_health", self.check_test_health),
        ]

        for check_name, check_func in checks:
            try:
                logger.debug(f"执行检查: {check_name}")
                issues = await check_func()
                all_issues.extend(issues)
            except Exception as e:
                logger.error(f"检查 {check_name} 失败: {e}")

        # 按 severity 排序: critical > warning > info
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        all_issues.sort(key=lambda x: severity_order.get(x.severity, 99))

        logger.info(f"检查完成: 发现 {len(all_issues)} 个问题 "
                    f"(critical={sum(1 for i in all_issues if i.severity == 'critical')}, "
                    f"warning={sum(1 for i in all_issues if i.severity == 'warning')}, "
                    f"info={sum(1 for i in all_issues if i.severity == 'info')})")

        return all_issues

    async def start(self):
        """启动监控循环"""
        self._running = True
        logger.info(f"ProjectMonitor 启动: 监控 {self.project_path}, 间隔 {self.check_interval}s")

        while self._running:
            try:
                await self.check_once()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
                await asyncio.sleep(self.check_interval)

        logger.info("ProjectMonitor 已停止")

    async def stop(self):
        """停止监控"""
        self._running = False
        logger.info("ProjectMonitor 正在停止...")

    @property
    def issues(self) -> List[Issue]:
        """获取历史发现的所有问题"""
        return self._issues_history.copy()

    def summary(self) -> str:
        """获取问题摘要"""
        total = len(self._issues_history)
        critical = sum(1 for i in self._issues_history if i.severity == "critical")
        warning = sum(1 for i in self._issues_history if i.severity == "warning")
        info = sum(1 for i in self._issues_history if i.severity == "info")
        return (f"监控摘要: {total} 个问题 "
                f"(🚨 critical={critical}, ⚠️ warning={warning}, ℹ️ info={info})")
