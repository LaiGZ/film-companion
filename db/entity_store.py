"""
统一实体存储层 — JSONB 风格，一张表通吃所有用户数据

核心设计：
  - entities 表：所有业务数据（film/gear/shoot/...）存同一张表
  - data 字段（JSON TEXT）：AI 自由定义字段结构，不限 schema
  - FTS5 全文索引：支持自然语言搜索
  - 所有查询走 JSON 路径表达式，不需要预定义查询参数

使用方式（以 film 为例）：
  await save_entity(uid, "film", name="Kodak Portra 400", data={
      "brand": "Kodak",
      "iso": 400,
      "format": "135",
      "type": "彩色负片",
      "status": "未使用",
  })
"""

import json
import time
import uuid
from datetime import datetime
from typing import Any

from db.pool import execute, execute_insert


# ============================================================
# 内部工具
# ============================================================

def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now().isoformat()


def _json(obj) -> str:
    if obj is None:
        return "{}"
    return json.dumps(obj, ensure_ascii=False, default=str)


# ============================================================
# 表创建 / 迁移
# ============================================================

CREATE_ENTITIES_SQL = """
CREATE TABLE IF NOT EXISTS entities (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    entity_type TEXT NOT NULL,      -- 'film' / 'gear' / 'shoot' / ...
    name        TEXT NOT NULL,      -- 实体名称，通用索引字段
    data        TEXT NOT NULL DEFAULT '{}',   -- JSON 数据，AI 自由定义
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_entities_user_type ON entities(user_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_type_status ON entities(entity_type, json_extract(data, '$.status'));
CREATE INDEX IF NOT EXISTS idx_entities_type_created ON entities(entity_type, created_at DESC);
"""

# FTS5 全文搜索（SQLite 需要单独建虚拟表）
CREATE_FTS5_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    name, data, content='entities', content_rowid='rowid'
);

-- 触发器：entities 写入时自动同步到 FTS
CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, name, data)
    VALUES (new.rowid, new.name, new.data);
END;

CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, data)
    VALUES ('delete', old.rowid, old.name, old.data);
END;

CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, name, data)
    VALUES ('delete', old.rowid, old.name, old.data);
    INSERT INTO entities_fts(rowid, name, data)
    VALUES (new.rowid, new.name, new.data);
END;
"""


async def init_entity_store():
    """初始化 entities 表 + FTS（幂等，多次调用安全）"""
    # 建表
    for stmt in CREATE_ENTITIES_SQL.split(";"):
        s = stmt.strip()
        if s:
            try:
                await execute(s)
            except Exception:
                pass  # "already exists" 之类忽略

    # 建 FTS（SQLite 不支持 IF NOT EXISTS on CREATE VIRTUAL TABLE）
    try:
        await execute(CREATE_FTS5_SQL.split(";")[0])  # 只建表
    except Exception:
        pass  # 已存在

    # 建触发器（逐条执行）
    for trigger_stmt in [
        "CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN INSERT INTO entities_fts(rowid, name, data) VALUES (new.rowid, new.name, new.data); END;",
        "CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN INSERT INTO entities_fts(entities_fts, rowid, name, data) VALUES ('delete', old.rowid, old.name, old.data); END;",
        "CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN INSERT INTO entities_fts(entities_fts, rowid, name, data) VALUES ('delete', old.rowid, old.name, old.data); INSERT INTO entities_fts(rowid, name, data) VALUES (new.rowid, new.name, new.data); END;",
    ]:
        try:
            await execute(trigger_stmt)
        except Exception:
            pass


# ============================================================
# 核心 CRUD
# ============================================================

async def save_entity(
    user_id: str,
    entity_type: str,
    name: str,
    data: dict = None,
    entity_id: str = None,
) -> str:
    """
    保存一个实体到 entities 表。

    参数:
        user_id:     用户 ID
        entity_type: 实体类型，如 'film', 'gear', 'shoot', 'film_loading'
        name:        实体名称（用于搜索和展示）
        data:        JSON 数据，AI 自由定义字段（嵌套对象/数组均可）
        entity_id:   指定 ID（不指定则自动生成）

    返回: entity_id

    示例:
        await save_entity(uid, "film", "Kodak Portra 400", {
            "brand": "Kodak",
            "iso": 400,
            "format": "135",
            "type": "彩色负片",
            "status": "未使用",
            "purchase": {"channel": "淘宝", "price": 180},
        })
    """
    eid = entity_id or _uid()
    now = _now()
    data_json = _json(data or {})

    # 检查是否已存在（更新 vs 新增）
    existing = await execute(
        "SELECT id FROM entities WHERE id = ?", eid
    )

    if existing:
        await execute(
            """UPDATE entities SET
               user_id = ?, entity_type = ?, name = ?,
               data = ?, updated_at = ?
               WHERE id = ?""",
            user_id, entity_type, name, data_json, now, eid
        )
    else:
        await execute(
            """INSERT INTO entities (id, user_id, entity_type, name, data, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            eid, user_id, entity_type, name, data_json, now, now
        )

    return eid


async def query_entities(
    user_id: str,
    entity_type: str = None,
    filters: dict = None,
    order_by: str = "created_at",
    order_dir: str = "DESC",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    查询实体，支持 JSON 字段过滤。

    filters 中所有键值对都通过 json_extract 匹配 data 里的字段。
    支持嵌套路径：{"purchase.channel": "淘宝"}

    示例:
        # 查所有 film
        await query_entities(uid, "film")

        # 查未使用的 ISO 400 彩色负片
        await query_entities(uid, "film", {
            "status": "未使用",
            "iso": 400,
            "type": "彩色负片",
        })

        # 查某品牌设备
        await query_entities(uid, "gear", {"brand": "Leica"})

        # 全部实体（不分类型，最新优先）
        await query_entities(uid, limit=50)
    """
    where_parts = ["user_id = ?"]
    params = [user_id]

    if entity_type:
        where_parts.append("entity_type = ?")
        params.append(entity_type)

    for key, value in (filters or {}).items():
        if value is None:
            continue

        # 支持嵌套路径： "purchase.channel" → $.purchase.channel
        json_path = f"$.{key}"
        where_parts.append(f"json_extract(data, '{json_path}') = ?")
        params.append(str(value))

    where = " AND ".join(where_parts)
    safe_order = "created_at" if order_by not in ("created_at", "updated_at", "name") else order_by
    safe_dir = "DESC" if order_dir.upper() not in ("ASC", "DESC") else order_dir.upper()

    sql = f"""SELECT id, entity_type, name, data, created_at, updated_at
              FROM entities
              WHERE {where}
              ORDER BY {safe_order} {safe_dir}
              LIMIT ? OFFSET ?"""
    params.extend([limit, offset])

    rows = await execute(sql, *params)
    return [_parse_row(r) for r in rows]


async def get_entity(entity_id: str) -> dict | None:
    """按 ID 获取单个实体"""
    rows = await execute(
        "SELECT id, user_id, entity_type, name, data, created_at, updated_at FROM entities WHERE id = ?",
        entity_id
    )
    if not rows:
        return None
    return _parse_row(rows[0])


async def delete_entity(entity_id: str) -> bool:
    """删除实体（FTS 自动同步删除）"""
    await execute("DELETE FROM entities WHERE id = ?", entity_id)
    return True


async def count_entities(user_id: str, entity_type: str = None) -> int:
    """统计数量"""
    if entity_type:
        rows = await execute(
            "SELECT COUNT(*) AS cnt FROM entities WHERE user_id = ? AND entity_type = ?",
            user_id, entity_type
        )
    else:
        rows = await execute(
            "SELECT COUNT(*) AS cnt FROM entities WHERE user_id = ?",
            user_id
        )
    return rows[0]["cnt"] if rows else 0


# ============================================================
# 全文搜索
# ============================================================

async def search_entities(
    user_id: str,
    query_text: str,
    entity_type: str = None,
    limit: int = 20,
) -> list[dict]:
    """
    全文搜索实体（通过 FTS5）。

    query_text 支持 FTS5 查询语法：
      - 关键词：'Portra 400'
      - 短语：'"彩色负片"'
      - 前缀：'Koda*'
      - 布尔：'Portra NOT Ektar'

    示例:
        await search_entities(uid, "Portra 400 人像")
        await search_entities(uid, '"彩色负片" 过期', "film")
    """
    # FTS5 要求每行都有 docid，通过 JOIN entities 过滤 user_id
    sql = """
        SELECT e.id, e.entity_type, e.name, e.data, e.created_at, e.updated_at
        FROM entities_fts f
        JOIN entities e ON e.rowid = f.rowid
        WHERE entities_fts MATCH ?
          AND e.user_id = ?
    """
    params = [query_text, user_id]

    if entity_type:
        sql += " AND e.entity_type = ?"
        params.append(entity_type)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    try:
        rows = await execute(sql, *params)
    except Exception as exc:
        # FTS 查询语法错误时降级为 LIKE
        like_text = f"%{query_text}%"
        sql2 = """
            SELECT id, entity_type, name, data, created_at, updated_at
            FROM entities
            WHERE user_id = ? AND (name LIKE ? OR data LIKE ?)
        """
        params2 = [user_id, like_text, like_text]
        if entity_type:
            sql2 += " AND entity_type = ?"
            params2.append(entity_type)
        sql2 += " ORDER BY created_at DESC LIMIT ?"
        params2.append(limit)
        rows = await execute(sql2, *params2)

    return [_parse_row(r) for r in rows]


# ============================================================
# 聚合统计
# ============================================================

async def get_stats(user_id: str) -> dict:
    """获取用户所有实体的统计信息"""
    rows = await execute(
        """SELECT entity_type, COUNT(*) AS cnt
           FROM entities WHERE user_id = ?
           GROUP BY entity_type""",
        user_id
    )

    stats = {}
    for r in rows:
        etype = r["entity_type"]
        count = r["cnt"]
        stats[etype] = {"count": count}

        # 特殊处理：film 的统计
        if etype == "film":
            # 按 status 分组
            status_rows = await execute(
                """SELECT json_extract(data, '$.status') AS status, COUNT(*) AS cnt
                   FROM entities WHERE user_id = ? AND entity_type = 'film'
                   GROUP BY json_extract(data, '$.status')""",
                user_id
            )
            statuses = {s["status"] or "未知": s["cnt"] for s in status_rows}
            stats[etype]["statuses"] = statuses

            # 总价值
            price_rows = await execute(
                """SELECT json_extract(data, '$.purchase.price') AS p
                   FROM entities WHERE user_id = ? AND entity_type = 'film'""",
                user_id
            )
            total_price = sum(
                float(r["p"]) for r in price_rows
                if r["p"] is not None
            )
            stats[etype]["total_price"] = total_price

            # 过期统计
            today = datetime.now().strftime("%Y-%m-%d")
            expired = await execute(
                """SELECT COUNT(*) AS cnt FROM entities
                   WHERE user_id = ? AND entity_type = 'film'
                   AND json_extract(data, '$.expiry') IS NOT NULL
                   AND json_extract(data, '$.expiry') < ?""",
                user_id, today
            )
            stats[etype]["expired"] = expired[0]["cnt"] if expired else 0

        # 特殊处理：gear 的总价值
        elif etype == "gear":
            price_rows = await execute(
                """SELECT json_extract(data, '$.purchase.price') AS p
                   FROM entities WHERE user_id = ? AND entity_type = 'gear'""",
                user_id
            )
            total_price = sum(
                float(r["p"]) for r in price_rows
                if r["p"] is not None
            )
            stats[etype]["total_price"] = total_price

    return stats


# ============================================================
# 内部：行解析
# ============================================================

def _parse_row(row: dict) -> dict:
    """将数据库行解析为友好的 dict，自动解析 JSON data"""
    result = dict(row)

    # 解析 data JSON
    data_raw = result.get("data", "{}")
    if isinstance(data_raw, str):
        try:
            result["data"] = json.loads(data_raw)
        except (json.JSONDecodeError, TypeError):
            result["data"] = {}

    return result
