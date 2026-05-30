"""
SQLite 持久化存储层 - 代码图谱的本地数据库

功能:
- SQLite 数据库初始化（symbols, edges, files 表）
- FTS5 全文搜索虚拟表
- 符号/边的增删改查
- 文件 hash 增量更新判断
- 高效批量操作
"""

import sqlite3
import hashlib
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ==============================================================================
# 数据库 Schema
# ==============================================================================

_SCHEMA_SQL = """
-- 文件索引表（用于增量更新）
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    last_indexed REAL NOT NULL,
    size INTEGER DEFAULT 0
);

-- 符号表（函数、类、模块）
CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    type TEXT NOT NULL,             -- function / class / module
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    line INTEGER NOT NULL,
    end_line INTEGER,
    signature TEXT,
    docstring TEXT,
    UNIQUE(qualified_name, file_path, line)
);

-- 关系边表
CREATE TABLE IF NOT EXISTS edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    target_name TEXT NOT NULL,
    type TEXT NOT NULL,             -- calls / imports / inherits / uses
    source_file TEXT,
    target_file TEXT,
    UNIQUE(source_name, target_name, type, source_file)
);

-- FTS5 全文搜索虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    qualified_name,
    docstring,
    signature,
    content=symbols,
    content_rowid=id,
    tokenize='unicode61'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_qualified ON symbols(qualified_name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_name);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_name);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);

-- FTS5 触发器：自动同步
CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, qualified_name, docstring, signature)
    VALUES (new.id, new.name, new.qualified_name, new.docstring, new.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, docstring, signature)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.docstring, old.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, qualified_name, docstring, signature)
    VALUES ('delete', old.id, old.name, old.qualified_name, old.docstring, old.signature);
    INSERT INTO symbols_fts(rowid, name, qualified_name, docstring, signature)
    VALUES (new.id, new.name, new.qualified_name, new.docstring, new.signature);
END;
"""


# ==============================================================================
# 数据类
# ==============================================================================

@dataclass
class SymbolRecord:
    """符号记录"""
    id: Optional[int] = None
    name: str = ""
    qualified_name: str = ""
    type: str = ""
    file_id: int = 0
    file_path: str = ""
    line: int = 0
    end_line: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class EdgeRecord:
    """边记录"""
    id: Optional[int] = None
    source_id: Optional[int] = None
    source_name: str = ""
    target_name: str = ""
    type: str = ""
    source_file: str = ""
    target_file: str = ""


@dataclass
class FileRecord:
    """文件记录"""
    id: Optional[int] = None
    path: str = ""
    hash: str = ""
    last_indexed: float = 0.0
    size: int = 0


# ==============================================================================
# 存储引擎
# ==============================================================================

class CodeGraphStorage:
    """SQLite 代码图谱存储引擎
    
    提供持久化的代码图谱存储，支持：
    - 符号（函数/类/模块）的存储和检索
    - 关系边（调用/导入/继承）的存储
    - FTS5 全文搜索
    - 基于文件 hash 的增量更新
    """

    def __init__(self, db_path: str = ".codegraph/index.db"):
        """初始化存储引擎
        
        Args:
            db_path: SQLite 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_dir()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _ensure_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def _init_db(self):
        """初始化数据库连接和 schema"""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # 性能优化
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        self._conn.execute("PRAGMA foreign_keys=ON")
        # 创建表
        self._conn.executescript(_SCHEMA_SQL)
        self._conn.commit()
        logger.info(f"CodeGraph 数据库已初始化: {self.db_path}")

    @property
    def conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._conn is None:
            self._init_db()
        return self._conn

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    # ==========================================================================
    # 文件管理
    # ==========================================================================

    @staticmethod
    def compute_file_hash(filepath: str) -> str:
        """计算文件内容的 MD5 hash"""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except (IOError, OSError):
            return ""

    def get_file_record(self, filepath: str) -> Optional[FileRecord]:
        """获取文件记录"""
        row = self.conn.execute(
            "SELECT id, path, hash, last_indexed, size FROM files WHERE path = ?",
            (filepath,)
        ).fetchone()
        if row:
            return FileRecord(
                id=row["id"], path=row["path"], hash=row["hash"],
                last_indexed=row["last_indexed"], size=row["size"]
            )
        return None

    def upsert_file(self, filepath: str, file_hash: str, size: int = 0) -> int:
        """插入或更新文件记录，返回 file_id"""
        import time
        now = time.time()
        self.conn.execute("""
            INSERT INTO files (path, hash, last_indexed, size)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                hash = excluded.hash,
                last_indexed = excluded.last_indexed,
                size = excluded.size
        """, (filepath, file_hash, now, size))
        self.conn.commit()
        row = self.conn.execute("SELECT id FROM files WHERE path = ?", (filepath,)).fetchone()
        return row["id"]

    def file_needs_reindex(self, filepath: str) -> bool:
        """判断文件是否需要重新索引（hash 变化）"""
        record = self.get_file_record(filepath)
        if record is None:
            return True
        current_hash = self.compute_file_hash(filepath)
        return current_hash != record.hash

    def remove_file(self, filepath: str):
        """删除文件及其关联的所有符号和边"""
        self.conn.execute("DELETE FROM edges WHERE source_file = ?", (filepath,))
        self.conn.execute("DELETE FROM symbols WHERE file_path = ?", (filepath,))
        self.conn.execute("DELETE FROM files WHERE path = ?", (filepath,))
        self.conn.commit()

    # ==========================================================================
    # 符号操作
    # ==========================================================================

    def insert_symbol(self, symbol: SymbolRecord) -> int:
        """插入符号记录，返回 symbol id"""
        cursor = self.conn.execute("""
            INSERT OR REPLACE INTO symbols 
                (name, qualified_name, type, file_id, file_path, line, end_line, signature, docstring)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            symbol.name, symbol.qualified_name, symbol.type,
            symbol.file_id, symbol.file_path, symbol.line,
            symbol.end_line, symbol.signature, symbol.docstring
        ))
        return cursor.lastrowid

    def insert_symbols_batch(self, symbols: List[SymbolRecord]):
        """批量插入符号"""
        data = [
            (s.name, s.qualified_name, s.type, s.file_id, s.file_path,
             s.line, s.end_line, s.signature, s.docstring)
            for s in symbols
        ]
        self.conn.executemany("""
            INSERT OR REPLACE INTO symbols
                (name, qualified_name, type, file_id, file_path, line, end_line, signature, docstring)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()

    def get_symbol_by_name(self, name: str) -> List[SymbolRecord]:
        """按名称查找符号"""
        rows = self.conn.execute(
            "SELECT * FROM symbols WHERE name = ? OR qualified_name = ?",
            (name, name)
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def get_symbols_in_file(self, filepath: str) -> List[SymbolRecord]:
        """获取文件中的所有符号"""
        rows = self.conn.execute(
            "SELECT * FROM symbols WHERE file_path = ? ORDER BY line",
            (filepath,)
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    def get_symbol_at_line(self, filepath: str, line: int) -> Optional[SymbolRecord]:
        """获取某行最近的符号"""
        row = self.conn.execute("""
            SELECT * FROM symbols 
            WHERE file_path = ? AND line <= ? AND type != 'module'
            ORDER BY line DESC LIMIT 1
        """, (filepath, line)).fetchone()
        if row:
            return self._row_to_symbol(row)
        return None

    def get_symbols_by_type(self, symbol_type: str) -> List[SymbolRecord]:
        """按类型查找符号"""
        rows = self.conn.execute(
            "SELECT * FROM symbols WHERE type = ?", (symbol_type,)
        ).fetchall()
        return [self._row_to_symbol(r) for r in rows]

    # ==========================================================================
    # 边操作
    # ==========================================================================

    def insert_edge(self, edge: EdgeRecord):
        """插入关系边"""
        self.conn.execute("""
            INSERT OR IGNORE INTO edges
                (source_id, source_name, target_name, type, source_file, target_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            edge.source_id, edge.source_name, edge.target_name,
            edge.type, edge.source_file, edge.target_file
        ))

    def insert_edges_batch(self, edges: List[EdgeRecord]):
        """批量插入边"""
        data = [
            (e.source_id, e.source_name, e.target_name,
             e.type, e.source_file, e.target_file)
            for e in edges
        ]
        self.conn.executemany("""
            INSERT OR IGNORE INTO edges
                (source_id, source_name, target_name, type, source_file, target_file)
            VALUES (?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()

    def get_callers(self, func_name: str) -> List[Dict[str, str]]:
        """获取调用某函数的所有调用者"""
        rows = self.conn.execute("""
            SELECT DISTINCT e.source_name, e.source_file, s.line, s.type
            FROM edges e
            LEFT JOIN symbols s ON s.qualified_name = e.source_name OR s.name = e.source_name
            WHERE (e.target_name = ? OR e.target_name LIKE ?) AND e.type = 'calls'
        """, (func_name, f"%.{func_name}")).fetchall()
        return [{"name": r["source_name"], "file": r["source_file"] or "",
                 "line": r["line"] or 0, "type": r["type"] or ""} for r in rows]

    def get_callees(self, func_name: str) -> List[Dict[str, str]]:
        """获取某函数调用的所有函数"""
        rows = self.conn.execute("""
            SELECT DISTINCT e.target_name, e.target_file
            FROM edges e
            WHERE (e.source_name = ? OR e.source_name LIKE ?) AND e.type = 'calls'
        """, (func_name, f"%.{func_name}")).fetchall()
        return [{"name": r["target_name"], "file": r["target_file"] or ""} for r in rows]

    def get_dependents(self, module_name: str) -> List[Dict[str, str]]:
        """获取依赖某模块的所有模块"""
        rows = self.conn.execute("""
            SELECT DISTINCT e.source_name, e.source_file
            FROM edges e
            WHERE (e.target_name = ? OR e.target_name LIKE ?) AND e.type = 'imports'
        """, (module_name, f"{module_name}.%")).fetchall()
        return [{"name": r["source_name"], "file": r["source_file"] or ""} for r in rows]

    def get_dependencies(self, module_name: str) -> List[Dict[str, str]]:
        """获取某模块依赖的所有模块"""
        rows = self.conn.execute("""
            SELECT DISTINCT e.target_name, e.target_file
            FROM edges e
            WHERE e.source_name = ? AND e.type = 'imports'
        """, (module_name,)).fetchall()
        return [{"name": r["target_name"], "file": r["target_file"] or ""} for r in rows]

    def get_edges_by_type(self, edge_type: str) -> List[EdgeRecord]:
        """按类型获取所有边"""
        rows = self.conn.execute(
            "SELECT * FROM edges WHERE type = ?", (edge_type,)
        ).fetchall()
        return [self._row_to_edge(r) for r in rows]

    # ==========================================================================
    # FTS5 全文搜索
    # ==========================================================================

    def search(self, query: str, limit: int = 20) -> List[SymbolRecord]:
        """FTS5 全文搜索符号
        
        支持：
        - 简单关键词: "calculator"
        - 前缀匹配: "calc*"
        - 短语: '"token estimator"'
        - 布尔: "cache OR retry"
        
        Args:
            query: 搜索查询字符串
            limit: 最大返回数量
            
        Returns:
            匹配的符号列表（按相关性排序）
        """
        try:
            # 尝试 FTS5 查询
            rows = self.conn.execute("""
                SELECT s.*, rank
                FROM symbols_fts fts
                JOIN symbols s ON s.id = fts.rowid
                WHERE symbols_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
            return [self._row_to_symbol(r) for r in rows]
        except sqlite3.OperationalError:
            # FTS5 语法错误时退回到 LIKE 查询
            like_pattern = f"%{query}%"
            rows = self.conn.execute("""
                SELECT * FROM symbols
                WHERE name LIKE ? OR qualified_name LIKE ? OR docstring LIKE ?
                ORDER BY name
                LIMIT ?
            """, (like_pattern, like_pattern, like_pattern, limit)).fetchall()
            return [self._row_to_symbol(r) for r in rows]

    # ==========================================================================
    # 影响分析
    # ==========================================================================

    def get_impact(self, symbol_name: str, max_depth: int = 5) -> Dict[str, Set[str]]:
        """递归影响分析 — 修改某符号会影响哪些文件和符号
        
        Args:
            symbol_name: 要分析的符号名
            max_depth: 最大递归深度
            
        Returns:
            {"files": 受影响文件集, "symbols": 受影响符号集}
        """
        affected_files: Set[str] = set()
        affected_symbols: Set[str] = set()
        visited: Set[str] = set()

        def _trace(name: str, depth: int):
            if name in visited or depth > max_depth:
                return
            visited.add(name)

            rows = self.conn.execute("""
                SELECT DISTINCT source_name, source_file
                FROM edges
                WHERE target_name = ? OR target_name LIKE ?
            """, (name, f"%.{name}")).fetchall()

            for row in rows:
                src_name = row["source_name"]
                src_file = row["source_file"]
                affected_symbols.add(src_name)
                if src_file:
                    affected_files.add(src_file)
                _trace(src_name, depth + 1)

        _trace(symbol_name, 0)
        return {"files": affected_files, "symbols": affected_symbols}

    # ==========================================================================
    # 统计
    # ==========================================================================

    def get_stats(self) -> Dict[str, int]:
        """获取数据库统计信息"""
        stats = {}
        stats["files"] = self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        stats["symbols"] = self.conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        stats["functions"] = self.conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE type='function'").fetchone()[0]
        stats["classes"] = self.conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE type='class'").fetchone()[0]
        stats["modules"] = self.conn.execute(
            "SELECT COUNT(*) FROM symbols WHERE type='module'").fetchone()[0]
        stats["edges"] = self.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        stats["call_edges"] = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE type='calls'").fetchone()[0]
        stats["import_edges"] = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE type='imports'").fetchone()[0]
        stats["inherit_edges"] = self.conn.execute(
            "SELECT COUNT(*) FROM edges WHERE type='inherits'").fetchone()[0]
        return stats

    def get_db_size(self) -> str:
        """获取数据库文件大小"""
        try:
            size = os.path.getsize(self.db_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except OSError:
            return "unknown"

    # ==========================================================================
    # 工具方法
    # ==========================================================================

    def clear(self):
        """清空所有数据"""
        self.conn.execute("DELETE FROM edges")
        self.conn.execute("DELETE FROM symbols")
        self.conn.execute("DELETE FROM files")
        self.conn.commit()
        logger.info("代码图谱数据已清空")

    def vacuum(self):
        """压缩数据库"""
        self.conn.execute("VACUUM")

    def _row_to_symbol(self, row) -> SymbolRecord:
        """将数据库行转为 SymbolRecord"""
        return SymbolRecord(
            id=row["id"] if "id" in row.keys() else None,
            name=row["name"],
            qualified_name=row["qualified_name"],
            type=row["type"],
            file_id=row["file_id"] if "file_id" in row.keys() else 0,
            file_path=row["file_path"] if "file_path" in row.keys() else "",
            line=row["line"] if "line" in row.keys() else 0,
            end_line=row["end_line"] if "end_line" in row.keys() else None,
            signature=row["signature"] if "signature" in row.keys() else None,
            docstring=row["docstring"] if "docstring" in row.keys() else None,
        )

    def _row_to_edge(self, row) -> EdgeRecord:
        """将数据库行转为 EdgeRecord"""
        return EdgeRecord(
            id=row["id"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            target_name=row["target_name"],
            type=row["type"],
            source_file=row["source_file"] or "",
            target_file=row["target_file"] or "",
        )

    def __del__(self):
        self.close()


# ==============================================================================
# 便捷工厂函数
# ==============================================================================

_default_storage: Optional[CodeGraphStorage] = None


def get_storage(db_path: str = ".codegraph/index.db") -> CodeGraphStorage:
    """获取全局存储实例（单例）"""
    global _default_storage
    if _default_storage is None:
        _default_storage = CodeGraphStorage(db_path)
    return _default_storage


def reset_storage():
    """重置全局存储实例"""
    global _default_storage
    if _default_storage:
        _default_storage.close()
    _default_storage = None
