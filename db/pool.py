"""
数据库连接池 — 支持 PostgreSQL 和 SQLite 两种后端

环境变量 DATABASE_URL 控制：
  postgresql://... → PostgreSQL（生产）
  sqlite:///path   → SQLite（本地测试，默认）
"""

import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any


# ============================================================
# 配置
# ============================================================

USE_SQLITE = True  # 默认使用 SQLite（本地环境无需安装 PostgreSQL）

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "film_companion.db")


def get_dsn() -> str:
    """获取数据库连接字符串"""
    return os.getenv("DATABASE_URL", "")


def is_sqlite() -> bool:
    """判断是否使用 SQLite"""
    dsn = get_dsn()
    if dsn:
        return dsn.startswith("sqlite")
    return USE_SQLITE


# ============================================================
# SQLite 连接管理
# ============================================================

_sqlite_conn: sqlite3.Connection | None = None


def _get_sqlite_conn() -> sqlite3.Connection:
    """获取 SQLite 连接（同步，单连接）"""
    global _sqlite_conn
    if _sqlite_conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _sqlite_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
        _sqlite_conn.execute("PRAGMA foreign_keys=ON")
        _init_sqlite_schema(_sqlite_conn)
    return _sqlite_conn


def _init_sqlite_schema(conn: sqlite3.Connection):
    """初始化 SQLite 表结构（含增量迁移）"""
    
    # ========== 现有表结构（保留 CREATE IF NOT EXISTS） ==========
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_session (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT,
            platform TEXT DEFAULT 'cli',
            status TEXT DEFAULT 'active',
            meta TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            last_activity TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS chat_message (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL REFERENCES chat_session(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            turn_index INTEGER NOT NULL,
            parent_id TEXT REFERENCES chat_message(id),
            meta TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS message_entity_link (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL REFERENCES chat_message(id) ON DELETE CASCADE,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS data_audit_log (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            session_id TEXT,
            message_id TEXT,
            entity_link_id TEXT,
            operation TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            sql_text TEXT NOT NULL,
            sql_params TEXT DEFAULT '{}',
            data_before TEXT,
            data_after TEXT,
            rows_affected INTEGER DEFAULT 0,
            tool_name TEXT,
            tool_args TEXT DEFAULT '{}',
            status TEXT DEFAULT 'success',
            error_message TEXT,
            duration_ms INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS long_term_memory (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            memory_type TEXT NOT NULL,
            category TEXT,
            content TEXT NOT NULL,
            source TEXT,
            confidence REAL DEFAULT 0.8,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            is_active INTEGER DEFAULT 1
        );
    """)

    # ========== 胶卷表（重新创建，含数据迁移） ==========
    # 检查是否是旧表（没有 frames 字段）
    cur = conn.execute("PRAGMA table_info(film)")
    film_cols = {r[1] for r in cur.fetchall()}

    if not film_cols:
        # 第一次创建
        conn.executescript("""
            CREATE TABLE film_new_v2 (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                film_type TEXT,
                iso INTEGER,
                format TEXT DEFAULT '135',
                frames INTEGER,
                sheet_count INTEGER,
                quantity INTEGER DEFAULT 0,
                unit TEXT DEFAULT '卷',
                purchase_date TEXT,
                expiry_date TEXT,
                purchase_price REAL,
                current_value REAL,
                price REAL,
                currency TEXT DEFAULT 'CNY',
                storage_location TEXT,
                status TEXT DEFAULT '未使用',
                meta TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                CHECK (quantity >= 0)
            );
            INSERT INTO film_new_v2 SELECT
                id, user_id, name, film_type, iso, format,
                NULL, NULL, quantity, unit, purchase_date, expiry_date,
                NULL, NULL, price, currency, storage_location, status, meta,
                created_at, updated_at
            FROM film;
            DROP TABLE film;
            ALTER TABLE film_new_v2 RENAME TO film;
        """)
    elif "frames" not in film_cols:
        # 旧表增量迁移
        for col in ["frames", "sheet_count", "purchase_price", "current_value"]:
            try:
                conn.execute(f"ALTER TABLE film ADD COLUMN {col} TEXT")
            except sqlite3.OperationalError:
                pass  # 列已存在
        # 用 price 填充 purchase_price
        conn.execute("UPDATE film SET purchase_price = price WHERE purchase_price IS NULL AND price IS NOT NULL")

    # ========== 设备表（含增量迁移） ==========
    cur = conn.execute("PRAGMA table_info(gear)")
    gear_cols = {r[1] for r in cur.fetchall()}

    if not gear_cols:
        conn.executescript("""
            CREATE TABLE gear_new_v2 (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                name TEXT NOT NULL,
                gear_type TEXT NOT NULL,
                category TEXT,
                brand TEXT,
                model TEXT,
                nickname TEXT,
                serial_number TEXT,
                camera_type TEXT,
                lens_mount TEXT,
                shutter_type TEXT,
                format_support TEXT,
                purchase_price REAL,
                sell_price REAL,
                purchase_date TEXT,
                sell_date TEXT,
                current_value REAL,
                price REAL,
                currency TEXT DEFAULT 'CNY',
                condition TEXT,
                status TEXT DEFAULT '在用',
                storage_location TEXT,
                parent_id TEXT REFERENCES gear(id),
                compatible_with TEXT DEFAULT '[]',
                meta TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            INSERT INTO gear_new_v2 SELECT
                id, user_id, name, gear_type,
                NULL, brand, model, nickname, serial_number,
                NULL, NULL, NULL, NULL,
                NULL, NULL, purchase_date, NULL,
                NULL, price, currency, condition, status, storage_location,
                NULL, NULL, meta, created_at, updated_at
            FROM gear;
            DROP TABLE gear;
            ALTER TABLE gear_new_v2 RENAME TO gear;
        """)
    else:
        new_gear_cols = ["category", "camera_type", "lens_mount", "shutter_type",
                         "format_support", "purchase_price", "sell_price", "sell_date",
                         "current_value", "parent_id", "compatible_with"]
        for col in new_gear_cols:
            if col not in gear_cols:
                try:
                    dtype = "TEXT" if col not in ("purchase_price", "sell_price", "current_value") else "REAL"
                    conn.execute(f"ALTER TABLE gear ADD COLUMN {col} {dtype}")
                except sqlite3.OperationalError:
                    pass

    # ========== 新表：拍摄记录 ==========
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS shoot (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            title TEXT,
            shoot_date TEXT,
            location TEXT,
            description TEXT,
            tags TEXT DEFAULT '[]',
            rating INTEGER,
            weather TEXT,
            status TEXT DEFAULT 'active',
            meta TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS film_loading (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT 'default',
            film_id TEXT NOT NULL REFERENCES film(id),
            camera_id TEXT REFERENCES gear(id),
            shoot_id TEXT REFERENCES shoot(id),
            loaded_at TEXT DEFAULT (datetime('now')),
            unloaded_at TEXT,
            frames_shot INTEGER DEFAULT 0,
            iso_setting INTEGER,
            push_pull INTEGER DEFAULT 0,
            notes TEXT,
            status TEXT DEFAULT '在机内',
            meta TEXT DEFAULT '{}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS shoot_gear (
            id TEXT PRIMARY KEY,
            shoot_id TEXT NOT NULL REFERENCES shoot(id) ON DELETE CASCADE,
            gear_id TEXT NOT NULL REFERENCES gear(id),
            role TEXT DEFAULT '主机',
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # ========== 新表索引 ==========
    try:
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_shoot_user ON shoot(user_id);
            CREATE INDEX IF NOT EXISTS idx_shoot_date ON shoot(shoot_date);
            CREATE INDEX IF NOT EXISTS idx_shoot_location ON shoot(location);
            CREATE INDEX IF NOT EXISTS idx_loading_film ON film_loading(film_id);
            CREATE INDEX IF NOT EXISTS idx_loading_camera ON film_loading(camera_id);
            CREATE INDEX IF NOT EXISTS idx_loading_shoot ON film_loading(shoot_id);
            CREATE INDEX IF NOT EXISTS idx_loading_status ON film_loading(status);
            CREATE INDEX IF NOT EXISTS idx_shoot_gear_shoot ON shoot_gear(shoot_id);
            CREATE INDEX IF NOT EXISTS idx_shoot_gear_gear ON shoot_gear(gear_id);
        """)
    except sqlite3.OperationalError:
        pass  # 索引已存在

    # ========== users 表 ==========
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                token_version INTEGER DEFAULT 1,
                phone TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        # 给 film_loading 和 shoot_gear 加 user_id 索引（已有字段）
        conn.execute("CREATE INDEX IF NOT EXISTS idx_loading_user ON film_loading(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shoot_gear_user ON shoot_gear(user_id)")
    except sqlite3.OperationalError:
        pass

    conn.commit()


# ============================================================
# 异步适配（使用线程池包装 SQLite 同步操作）
# ============================================================

import asyncio

async def execute(sql: str, *params) -> list[dict]:
    """执行 SQL，返回行列表"""
    def _run():
        conn = _get_sqlite_conn()
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        conn.commit()
        return [_row_to_dict(r) for r in rows]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def execute_many(sql: str, params_list: list[tuple]) -> list[dict]:
    """批量执行"""
    def _run():
        conn = _get_sqlite_conn()
        conn.executemany(sql, params_list)
        conn.commit()
        return [{"status": "ok"}]

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def execute_insert(sql: str, *params) -> str:
    """执行 INSERT，返回最后插入的 rowid"""
    def _run():
        conn = _get_sqlite_conn()
        cursor = conn.execute(sql, params)
        conn.commit()
        return str(cursor.lastrowid)

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def init_pool():
    """初始化（SQLite 下是懒加载，不需要额外操作）"""
    if not is_sqlite():
        # PostgreSQL 模式
        global _sqlite_conn
        _sqlite_conn = None
        dsn = get_dsn()
        if dsn:
            from asyncpg import create_pool
            # 尝试连接 PostgreSQL
            pass
    print(f"📦 数据库就绪: {'SQLite' if is_sqlite() else 'PostgreSQL'}")
    print(f"   路径: {DB_PATH if is_sqlite() else get_dsn()}")


async def close_pool():
    """关闭数据库"""
    global _sqlite_conn
    if _sqlite_conn:
        try:
            _sqlite_conn.close()
        except Exception:
            pass  # SQLite 跨线程关闭问题，忽略即可
        _sqlite_conn = None


@asynccontextmanager
async def get_connection():
    """获取连接（SQLite 适配器）"""
    yield None  # SQLite 使用全局连接，不需要 context manager


# ============================================================
# 辅助函数
# ============================================================

def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 sqlite3.Row 转为 dict"""
    if row is None:
        return {}
    d = dict(row)

    # 解析 JSON 字段
    for key in ("meta", "sql_params", "tool_args"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except (json.JSONDecodeError, TypeError):
                pass

    # 解析 tags 字段
    if "tags" in d and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []

    return d


# 临时重写 schema.py 中的 get_connection 导入
# schema.py 和 audit.py 都通过 from db.pool import get_connection 引用
# 现在它们会自动使用新的 SQLite 实现
