"""
文件监听器 - 自动增量更新代码图谱

功能:
- 监听项目目录的文件变更（创建/修改/删除）
- 自动触发增量重新索引（仅变更文件）
- 防抖：短时间内多次变更合并为一次索引
- 支持后台线程和手动启停

依赖:
- watchdog (pip install watchdog)

用法:
    from agent.agent.code_graph.watcher import CodeGraphWatcher
    
    watcher = CodeGraphWatcher("/path/to/project")
    watcher.start()   # 后台启动
    # ... 开发中 ...
    watcher.stop()    # 停止
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Set, Optional, Callable

logger = logging.getLogger(__name__)

# 尝试导入 watchdog，不可用时提供降级方案
try:
    from watchdog.observers import Observer
    from watchdog.events import (
        FileSystemEventHandler,
        FileCreatedEvent,
        FileModifiedEvent,
        FileDeletedEvent,
        FileMovedEvent,
    )
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    logger.info("watchdog 未安装，文件监听功能不可用。安装: pip install watchdog")


# 需要跳过的目录和文件
_SKIP_DIRS = {
    "__pycache__", ".venv", "venv", "node_modules", ".git",
    ".tox", "dist", "build", "egg-info", ".codegraph", ".mypy_cache",
    ".pytest_cache", ".ruff_cache",
}

_WATCH_EXTENSIONS = {".py"}


def _should_watch(filepath: str) -> bool:
    """判断文件是否应该被监听"""
    path = Path(filepath)
    
    # 检查扩展名
    if path.suffix not in _WATCH_EXTENSIONS:
        return False
    
    # 检查是否在跳过目录中
    parts = path.parts
    if any(skip in parts for skip in _SKIP_DIRS):
        return False
    
    return True


if HAS_WATCHDOG:

    class _CodeGraphEventHandler(FileSystemEventHandler):
        """文件系统事件处理器 - 收集变更文件"""

        def __init__(self, on_changes: Callable[[Set[str], Set[str]], None]):
            """
            Args:
                on_changes: 回调函数 (modified_files, deleted_files)
            """
            super().__init__()
            self._modified: Set[str] = set()
            self._deleted: Set[str] = set()
            self._lock = threading.Lock()
            self._on_changes = on_changes

        def on_created(self, event: FileCreatedEvent):
            if not event.is_directory and _should_watch(event.src_path):
                with self._lock:
                    self._modified.add(str(Path(event.src_path).resolve()))

        def on_modified(self, event: FileModifiedEvent):
            if not event.is_directory and _should_watch(event.src_path):
                with self._lock:
                    self._modified.add(str(Path(event.src_path).resolve()))

        def on_deleted(self, event: FileDeletedEvent):
            if not event.is_directory and _should_watch(event.src_path):
                with self._lock:
                    filepath = str(Path(event.src_path).resolve())
                    self._deleted.add(filepath)
                    self._modified.discard(filepath)

        def on_moved(self, event: FileMovedEvent):
            if not event.is_directory:
                if _should_watch(event.src_path):
                    with self._lock:
                        self._deleted.add(str(Path(event.src_path).resolve()))
                if _should_watch(event.dest_path):
                    with self._lock:
                        self._modified.add(str(Path(event.dest_path).resolve()))

        def flush_changes(self) -> tuple:
            """获取并清空待处理的变更"""
            with self._lock:
                modified = self._modified.copy()
                deleted = self._deleted.copy()
                self._modified.clear()
                self._deleted.clear()
            return modified, deleted

        @property
        def has_pending(self) -> bool:
            """是否有待处理的变更"""
            with self._lock:
                return bool(self._modified or self._deleted)


class CodeGraphWatcher:
    """代码图谱文件监听器
    
    监听项目目录中 Python 文件的变更，自动触发增量重新索引。
    使用防抖机制（debounce）避免频繁写入时重复索引。
    
    用法:
        watcher = CodeGraphWatcher("/path/to/project")
        watcher.start()
        # ... 项目开发中，自动索引 ...
        watcher.stop()
    """

    def __init__(
        self,
        project_root: str = ".",
        debounce_seconds: float = 2.0,
        analyzer=None,
    ):
        """
        Args:
            project_root: 项目根目录
            debounce_seconds: 防抖间隔（秒）。文件变更后等待这么久再索引。
            analyzer: CodeGraphAnalyzer 实例。None 则自动创建。
        """
        self.project_root = str(Path(project_root).resolve())
        self.debounce_seconds = debounce_seconds
        self._analyzer = analyzer
        self._observer: Optional[Any] = None
        self._handler: Optional[Any] = None
        self._debounce_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()
        
        # 统计
        self.total_reindexed = 0
        self.total_deleted = 0
        self.last_update_time: Optional[float] = None

    @property
    def analyzer(self):
        """懒加载分析器"""
        if self._analyzer is None:
            from . import CodeGraphAnalyzer
            self._analyzer = CodeGraphAnalyzer(self.project_root)
        return self._analyzer

    def start(self):
        """启动文件监听（后台线程）"""
        if not HAS_WATCHDOG:
            logger.error(
                "无法启动文件监听: watchdog 未安装。"
                "请运行: pip install watchdog"
            )
            return False

        if self._running:
            logger.warning("Watcher 已在运行中")
            return True

        self._handler = _CodeGraphEventHandler(self._process_changes)
        self._observer = Observer()
        self._observer.schedule(self._handler, self.project_root, recursive=True)
        self._observer.start()

        # 启动防抖处理线程
        self._running = True
        self._stop_event.clear()
        self._debounce_thread = threading.Thread(
            target=self._debounce_loop,
            name="codegraph-watcher-debounce",
            daemon=True,
        )
        self._debounce_thread.start()

        logger.info(
            f"CodeGraph Watcher 已启动: {self.project_root} "
            f"(防抖: {self.debounce_seconds}s)"
        )
        return True

    def stop(self):
        """停止文件监听"""
        self._running = False
        self._stop_event.set()

        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        if self._debounce_thread:
            self._debounce_thread.join(timeout=5)
            self._debounce_thread = None

        logger.info(
            f"CodeGraph Watcher 已停止。"
            f"累计重索引: {self.total_reindexed} 文件, "
            f"删除: {self.total_deleted} 文件"
        )

    def _debounce_loop(self):
        """防抖循环：等待变更稳定后批量处理"""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.debounce_seconds)

            if not self._running:
                break

            if self._handler and self._handler.has_pending:
                modified, deleted = self._handler.flush_changes()
                if modified or deleted:
                    self._process_changes(modified, deleted)

    def _process_changes(self, modified: Set[str], deleted: Set[str]):
        """处理文件变更：增量重索引"""
        start_time = time.time()

        # 处理删除的文件
        for filepath in deleted:
            try:
                self.analyzer.storage.remove_file(filepath)
                self.total_deleted += 1
                logger.debug(f"已从图谱移除: {filepath}")
            except Exception as e:
                logger.error(f"移除文件失败 {filepath}: {e}")

        # 处理修改/新建的文件
        reindexed = 0
        for filepath in modified:
            if not os.path.exists(filepath):
                continue
            try:
                self.analyzer.reindex_file(filepath)
                reindexed += 1
                self.total_reindexed += 1
            except Exception as e:
                logger.error(f"重索引失败 {filepath}: {e}")

        elapsed_ms = int((time.time() - start_time) * 1000)
        self.last_update_time = time.time()

        if reindexed > 0 or deleted:
            logger.info(
                f"增量更新完成: "
                f"+{reindexed} 文件重索引, "
                f"-{len(deleted)} 文件删除, "
                f"耗时 {elapsed_ms}ms"
            )

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running

    def get_status(self) -> dict:
        """获取监听器状态"""
        return {
            "running": self._running,
            "project_root": self.project_root,
            "debounce_seconds": self.debounce_seconds,
            "total_reindexed": self.total_reindexed,
            "total_deleted": self.total_deleted,
            "last_update": self.last_update_time,
            "watchdog_available": HAS_WATCHDOG,
        }


# ==============================================================================
# 便捷函数
# ==============================================================================

_global_watcher: Optional[CodeGraphWatcher] = None


def start_watcher(project_root: str = ".", debounce_seconds: float = 2.0) -> CodeGraphWatcher:
    """启动全局文件监听器（单例）"""
    global _global_watcher
    if _global_watcher and _global_watcher.is_running:
        return _global_watcher
    _global_watcher = CodeGraphWatcher(project_root, debounce_seconds)
    _global_watcher.start()
    return _global_watcher


def stop_watcher():
    """停止全局文件监听器"""
    global _global_watcher
    if _global_watcher:
        _global_watcher.stop()
        _global_watcher = None


def get_watcher() -> Optional[CodeGraphWatcher]:
    """获取全局监听器实例"""
    return _global_watcher
