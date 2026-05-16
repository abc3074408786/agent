"""
Proactive Monitor - 主动监控守护进程

在后台持续运行，监控项目变化并主动发现问题：
- 文件变化检测
- 测试状态监控
- 依赖安全检查
- 代码质量巡检

启动: python -m agent.monitor --watch /path/to/project
"""

import os
import sys
import time
import hashlib
import asyncio
import argparse
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# 日志输出到 stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# ─── Alert 数据类 ──────────────────────────────────────────────────────────────

@dataclass
class Alert:
    """监控告警"""
    level: str  # info / warning / critical
    source: str  # file_change / test / quality / git
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def format(self) -> str:
        """格式化告警为可读字符串"""
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(self.level, "•")
        return f"[{self.timestamp}] {icon} [{self.source}] {self.message}"


# ─── FileWatcher ───────────────────────────────────────────────────────────────

class FileWatcher:
    """
    文件变化监控器 (polling 方式)
    
    通过计算文件 hash 来检测变化，不依赖 watchdog 等第三方库。
    """

    # 默认忽略的目录
    IGNORE_DIRS: Set[str] = {
        ".git", "__pycache__", "node_modules", ".venv",
        "venv", ".tox", ".mypy_cache", ".pytest_cache",
        ".ruff_cache", "dist", "build", ".eggs", "*.egg-info",
    }

    # 默认忽略的文件扩展名
    IGNORE_EXTENSIONS: Set[str] = {
        ".pyc", ".pyo", ".so", ".o", ".a",
        ".class", ".jar",
    }

    def __init__(self, watch_dir: str, on_change: Optional[Callable] = None):
        self.watch_dir = os.path.abspath(watch_dir)
        self.on_change = on_change
        self._file_hashes: Dict[str, str] = {}
        self._initialized = False

    def _should_ignore(self, path: str) -> bool:
        """判断路径是否应该被忽略"""
        parts = Path(path).parts
        for part in parts:
            if part in self.IGNORE_DIRS:
                return True
            # 处理 *.egg-info 等通配符模式
            for ignore in self.IGNORE_DIRS:
                if "*" in ignore and part.endswith(ignore.replace("*", "")):
                    return True
        # 检查文件扩展名
        _, ext = os.path.splitext(path)
        if ext in self.IGNORE_EXTENSIONS:
            return True
        return False

    def _compute_hash(self, filepath: str) -> Optional[str]:
        """计算文件 MD5 hash"""
        try:
            hasher = hashlib.md5()
            with open(filepath, "rb") as f:
                # 读取前 64KB 来快速计算 hash
                chunk = f.read(65536)
                while chunk:
                    hasher.update(chunk)
                    chunk = f.read(65536)
            return hasher.hexdigest()
        except (OSError, IOError):
            return None

    def _scan_files(self) -> Dict[str, str]:
        """扫描目录，返回 {filepath: hash} 映射"""
        file_hashes = {}
        for root, dirs, files in os.walk(self.watch_dir):
            # 过滤忽略的目录 (in-place 修改)
            dirs[:] = [d for d in dirs if not self._should_ignore(os.path.join(root, d))]

            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.watch_dir)
                if self._should_ignore(rel_path):
                    continue
                file_hash = self._compute_hash(filepath)
                if file_hash:
                    file_hashes[rel_path] = file_hash

        return file_hashes

    def check(self) -> Dict[str, List[str]]:
        """
        检查文件变化
        
        Returns:
            {"added": [...], "modified": [...], "deleted": [...]}
        """
        current_hashes = self._scan_files()
        changes: Dict[str, List[str]] = {"added": [], "modified": [], "deleted": []}

        if not self._initialized:
            self._file_hashes = current_hashes
            self._initialized = True
            logger.info(f"FileWatcher initialized: tracking {len(current_hashes)} files")
            return changes

        # 新增和修改
        for path, hash_val in current_hashes.items():
            if path not in self._file_hashes:
                changes["added"].append(path)
            elif self._file_hashes[path] != hash_val:
                changes["modified"].append(path)

        # 删除
        for path in self._file_hashes:
            if path not in current_hashes:
                changes["deleted"].append(path)

        self._file_hashes = current_hashes

        # 触发回调
        has_changes = any(changes[k] for k in changes)
        if has_changes and self.on_change:
            self.on_change(changes)

        return changes


# ─── ProactiveMonitor ──────────────────────────────────────────────────────────

class ProactiveMonitor:
    """
    主动监控守护进程
    
    在后台持续运行，定期检查项目状态并发出告警。
    """

    def __init__(
        self,
        project_dir: str,
        check_interval: int = 60,
        quiet: bool = False,
        webhook_url: Optional[str] = None,
    ):
        self.project_dir = os.path.abspath(project_dir)
        self.check_interval = check_interval
        self.quiet = quiet
        self.webhook_url = webhook_url
        self._running = False
        self._alerts: List[Alert] = []
        self._file_watcher = FileWatcher(
            self.project_dir,
            on_change=self._on_file_change,
        )

        # 确保通知日志目录存在
        self._log_dir = Path.home() / ".agent"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "notifications.log"

        # 质量阈值
        self.max_file_size_kb = 500  # 文件大于 500KB 告警
        self.max_function_lines = 100  # 函数超过 100 行告警
        self.max_uncommitted_files = 20  # 未提交文件超过 20 个告警
        self.max_todo_count = 50  # TODO 超过 50 个告警

    def _on_file_change(self, changes: Dict[str, List[str]]):
        """文件变化回调"""
        total = sum(len(v) for v in changes.values())
        if total > 0:
            details = {
                "added": len(changes["added"]),
                "modified": len(changes["modified"]),
                "deleted": len(changes["deleted"]),
            }
            self._emit_alert(Alert(
                level="info",
                source="file_change",
                message=f"Detected {total} file change(s)",
                details=details,
            ))

    def _emit_alert(self, alert: Alert):
        """发出告警"""
        self._alerts.append(alert)

        # Console 输出
        if not self.quiet:
            print(alert.format(), file=sys.stderr)

        # 写入日志文件
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(alert.format() + "\n")
        except IOError:
            pass

    async def check_file_changes(self) -> List[Alert]:
        """检测文件变化"""
        alerts = []
        changes = self._file_watcher.check()

        added = changes.get("added", [])
        modified = changes.get("modified", [])
        deleted = changes.get("deleted", [])
        total = len(added) + len(modified) + len(deleted)

        if total > 0:
            alert = Alert(
                level="info",
                source="file_change",
                message=f"{total} files changed: +{len(added)} ~{len(modified)} -{len(deleted)}",
                details={"added": added[:10], "modified": modified[:10], "deleted": deleted[:10]},
            )
            alerts.append(alert)
            self._emit_alert(alert)

        return alerts

    async def check_test_health(self) -> List[Alert]:
        """定期跑测试，检查测试健康状态"""
        alerts = []
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--tb=no", "-q", "--no-header"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=120,
            )

            if result.returncode != 0:
                # 解析失败测试数量
                output = result.stdout + result.stderr
                alert = Alert(
                    level="warning",
                    source="test",
                    message=f"Tests failing (exit code {result.returncode})",
                    details={"output": output[-500:]},  # 只保留最后 500 字符
                )
                alerts.append(alert)
                self._emit_alert(alert)
            else:
                logger.debug("All tests passing")

        except subprocess.TimeoutExpired:
            alert = Alert(
                level="warning",
                source="test",
                message="Test execution timed out (>120s)",
            )
            alerts.append(alert)
            self._emit_alert(alert)
        except FileNotFoundError:
            logger.debug("pytest not available, skipping test health check")

        return alerts

    async def check_code_quality(self) -> List[Alert]:
        """检测代码质量问题"""
        alerts = []

        large_files = []
        long_functions = []
        todo_count = 0

        for root, dirs, files in os.walk(self.project_dir):
            # 过滤
            dirs[:] = [d for d in dirs if d not in FileWatcher.IGNORE_DIRS]

            for filename in files:
                if not filename.endswith(".py"):
                    continue

                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self.project_dir)

                # 检查文件大小
                try:
                    size_kb = os.path.getsize(filepath) / 1024
                    if size_kb > self.max_file_size_kb:
                        large_files.append((rel_path, int(size_kb)))
                except OSError:
                    continue

                # 检查长函数和 TODO
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        lines = f.readlines()
                except IOError:
                    continue

                func_start = None
                func_name = ""
                for i, line in enumerate(lines):
                    stripped = line.strip()

                    # 统计 TODO
                    if "TODO" in line or "FIXME" in line or "HACK" in line:
                        todo_count += 1

                    # 检测函数定义
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        if func_start is not None:
                            length = i - func_start
                            if length > self.max_function_lines:
                                long_functions.append((rel_path, func_name, length))
                        func_name = stripped.split("(")[0].replace("def ", "").replace("async ", "")
                        func_start = i

                # 最后一个函数
                if func_start is not None:
                    length = len(lines) - func_start
                    if length > self.max_function_lines:
                        long_functions.append((rel_path, func_name, length))

        # 生成告警
        if large_files:
            alert = Alert(
                level="warning",
                source="quality",
                message=f"Found {len(large_files)} large file(s) (>{self.max_file_size_kb}KB)",
                details={"files": large_files[:10]},
            )
            alerts.append(alert)
            self._emit_alert(alert)

        if long_functions:
            alert = Alert(
                level="info",
                source="quality",
                message=f"Found {len(long_functions)} long function(s) (>{self.max_function_lines} lines)",
                details={"functions": long_functions[:10]},
            )
            alerts.append(alert)
            self._emit_alert(alert)

        if todo_count > self.max_todo_count:
            alert = Alert(
                level="info",
                source="quality",
                message=f"High TODO count: {todo_count} items",
                details={"count": todo_count},
            )
            alerts.append(alert)
            self._emit_alert(alert)

        return alerts

    async def check_git_status(self) -> List[Alert]:
        """检查 git 状态"""
        alerts = []
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10,
            )
            if result.returncode != 0:
                return alerts

            changed_files = [l for l in result.stdout.strip().split("\n") if l.strip()]
            count = len(changed_files)

            if count > self.max_uncommitted_files:
                alert = Alert(
                    level="warning",
                    source="git",
                    message=f"Too many uncommitted changes: {count} files (threshold: {self.max_uncommitted_files})",
                    details={"files": changed_files[:20]},
                )
                alerts.append(alert)
                self._emit_alert(alert)

            # 检查是否有未推送的 commit
            result2 = subprocess.run(
                ["git", "log", "--oneline", "@{u}..HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=10,
            )
            if result2.returncode == 0 and result2.stdout.strip():
                unpushed = result2.stdout.strip().split("\n")
                if len(unpushed) > 5:
                    alert = Alert(
                        level="info",
                        source="git",
                        message=f"{len(unpushed)} unpushed commit(s)",
                        details={"commits": unpushed[:10]},
                    )
                    alerts.append(alert)
                    self._emit_alert(alert)

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return alerts

    async def start(self):
        """启动后台监控"""
        self._running = True
        logger.info(f"ProactiveMonitor started: watching {self.project_dir}")
        logger.info(f"Check interval: {self.check_interval}s")

        # 初始化 FileWatcher
        self._file_watcher.check()

        cycle = 0
        while self._running:
            try:
                cycle += 1
                logger.debug(f"Monitor cycle #{cycle}")

                # 每个周期都检查文件变化
                await self.check_file_changes()

                # 每 5 个周期检查 git 状态
                if cycle % 5 == 0:
                    await self.check_git_status()

                # 每 10 个周期检查代码质量
                if cycle % 10 == 0:
                    await self.check_code_quality()

                # 每 30 个周期跑测试
                if cycle % 30 == 0:
                    await self.check_test_health()

                await asyncio.sleep(self.check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor cycle: {e}")
                await asyncio.sleep(self.check_interval)

        logger.info("ProactiveMonitor stopped")

    def stop(self):
        """停止监控"""
        self._running = False
        logger.info("Stopping monitor...")

    @property
    def alerts(self) -> List[Alert]:
        """获取所有告警历史"""
        return self._alerts.copy()


# ─── Entry Point ───────────────────────────────────────────────────────────────

def main():
    """Monitor 入口"""
    parser = argparse.ArgumentParser(
        description="Proactive Monitor - 主动监控守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m agent.monitor --watch .
  python -m agent.monitor --watch /path/to/project --interval 30
  python -m agent.monitor --watch . --quiet
        """,
    )
    parser.add_argument(
        "--watch", "-w",
        default=".",
        help="要监控的项目目录 (默认: 当前目录)",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=60,
        help="检查间隔秒数 (默认: 60)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式 (不输出到 console)",
    )

    args = parser.parse_args()

    # 验证目录
    watch_dir = os.path.abspath(args.watch)
    if not os.path.isdir(watch_dir):
        print(f"Error: Directory not found: {watch_dir}", file=sys.stderr)
        sys.exit(1)

    monitor = ProactiveMonitor(
        project_dir=watch_dir,
        check_interval=args.interval,
        quiet=args.quiet,
    )

    # 优雅退出
    import signal

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        monitor.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print(f"🔍 Proactive Monitor started", file=sys.stderr)
    print(f"   Watching: {watch_dir}", file=sys.stderr)
    print(f"   Interval: {args.interval}s", file=sys.stderr)
    print(f"   Log: ~/.agent/notifications.log", file=sys.stderr)
    print(f"   Press Ctrl+C to stop\n", file=sys.stderr)

    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        pass
    finally:
        print("\n✅ Monitor stopped gracefully", file=sys.stderr)


if __name__ == "__main__":
    main()
