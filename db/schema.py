"""
数据库操作层 — 所有表的 CRUD（SQLite + PostgreSQL 兼容）
"""

import hashlib
import hmac
import json
import os
import base64
import time
import uuid
from datetime import date, datetime
from typing import Any

from db.pool import execute, execute_insert, execute_many


# ============================================================
# 辅助
# ============================================================

def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now().isoformat()


def _to_json(obj) -> str:
    if obj is None:
        return "{}"
    return json.dumps(obj, ensure_ascii=False, default=str)


# ============================================================
# JWT 工具（纯 Python，无额外依赖）
# ============================================================

def _get_jwt_secret() -> str:
    """获取 JWT 密钥，持久化到文件"""
    secret_file = os.path.join(os.path.dirname(__file__), "..", "data", ".jwt_secret")
    if os.path.exists(secret_file):
        with open(secret_file) as f:
            return f.read().strip()
    # 第一次运行时生成
    secret = uuid.uuid4().hex + uuid.uuid4().hex
    os.makedirs(os.path.dirname(secret_file), exist_ok=True)
    with open(secret_file, "w") as f:
        f.write(secret)
    return secret


_JWT_SECRET = None


def _jwt_secret() -> str:
    global _JWT_SECRET
    if _JWT_SECRET is None:
        # 优先使用环境变量
        env_secret = os.getenv("JWT_SECRET")
        if env_secret:
            _JWT_SECRET = env_secret
        else:
            _JWT_SECRET = _get_jwt_secret()
    return _JWT_SECRET


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _base64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _jwt_sign(payload: dict) -> str:
    """HMAC-SHA256 签名 JWT"""
    header = _base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _base64url_encode(
        hmac.new(
            _jwt_secret().encode(),
            f"{header}.{body}".encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{header}.{body}.{sig}"


def _jwt_verify(token: str) -> dict | None:
    """验证 JWT，返回 payload 或 None"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, body_b64, sig_b64 = parts
        expected_sig = _base64url_encode(
            hmac.new(
                _jwt_secret().encode(),
                f"{header_b64}.{body_b64}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(sig_b64, expected_sig):
            return None
        payload = json.loads(_base64url_decode(body_b64))
        # 检查过期
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# ============================================================
# 密码工具
# ============================================================

def _hash_password(password: str) -> str:
    """pbkdf2_hmac 哈希密码"""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    # 格式: $algo$iterations$salt_b64$hash_b64
    return f"$pbkdf2-sha256$100000${_base64url_encode(salt)}${_base64url_encode(key)}"


def _check_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        parts = hashed.split("$")
        if len(parts) != 5:
            return False
        _, algo, iterations, salt_b64, hash_b64 = parts
        salt = _base64url_decode(salt_b64)
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(_base64url_encode(key), hash_b64)
    except Exception:
        return False


# ============================================================
# Token 生成
# ============================================================

def create_tokens(user_id: str, username: str, token_version: int) -> dict:
    """生成 access_token (15分钟) + refresh_token (7天)"""
    now = time.time()
    access_payload = {
        "sub": user_id,
        "username": username,
        "ver": token_version,
        "exp": now + 900,        # 15分钟
        "iat": now,
        "type": "access",
    }
    refresh_payload = {
        "sub": user_id,
        "ver": token_version,
        "exp": now + 604800,     # 7天
        "iat": now,
        "type": "refresh",
    }
    return {
        "access_token": _jwt_sign(access_payload),
        "refresh_token": _jwt_sign(refresh_payload),
        "expires_in": 900,
    }


# ============================================================
# 用户管理
# ============================================================

async def create_user(username: str, password: str) -> dict:
    """注册新用户"""
    uid = _uid()
    hashed = _hash_password(password)
    await execute(
        "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
        uid, username, hashed
    )
    return {"id": uid, "username": username}


async def get_user_by_username(username: str) -> dict | None:
    """按用户名查询用户"""
    rows = await execute("SELECT * FROM users WHERE username = ? AND status = 'active'", username)
    return rows[0] if rows else None


async def get_user_by_id(user_id: str) -> dict | None:
    """按 ID 查询用户（不含密码）"""
    rows = await execute(
        "SELECT id, username, token_version, phone, status, created_at FROM users WHERE id = ?",
        user_id
    )
    return rows[0] if rows else None


async def verify_user_password(username: str, password: str) -> dict | None:
    """验证用户密码，成功返回用户信息"""
    user = await get_user_by_username(username)
    if not user:
        return None
    if not _check_password(password, user["password_hash"]):
        return None
    return user


async def increment_token_version(user_id: str) -> int:
    """增加 token_version（单点登录：新登录使旧 token 失效）"""
    await execute(
        "UPDATE users SET token_version = token_version + 1, updated_at = datetime('now') WHERE id = ?",
        user_id
    )
    rows = await execute("SELECT token_version FROM users WHERE id = ?", user_id)
    return rows[0]["token_version"] if rows else 0


async def get_token_version(user_id: str) -> int:
    """获取当前 token_version"""
    rows = await execute("SELECT token_version FROM users WHERE id = ?", user_id)
    return rows[0]["token_version"] if rows else 0


# ============================================================
# 会话管理
# ============================================================

async def create_session(user_id: str = "default", platform: str = "cli") -> str:
    """创建新会话，返回 session_id"""
    sid = _uid()
    await execute(
        "INSERT INTO chat_session (id, user_id, platform) VALUES (?, ?, ?)",
        sid, user_id, platform
    )
    return sid


async def update_session_activity(session_id: str):
    """更新会话最后活动时间"""
    await execute(
        "UPDATE chat_session SET last_activity = datetime('now') WHERE id = ?",
        session_id
    )


async def list_sessions(user_id: str = "web_user", limit: int = 50) -> list[dict]:
    """列出用户的所有会话，含消息数和最后一条预览"""
    rows = await execute("""
        SELECT
            cs.id,
            cs.title,
            cs.created_at,
            cs.last_activity,
            (SELECT COUNT(*) FROM chat_message WHERE session_id = cs.id) AS msg_count,
            (SELECT content FROM chat_message
             WHERE session_id = cs.id AND role = 'user'
             ORDER BY turn_index DESC LIMIT 1) AS last_preview
        FROM chat_session cs
        WHERE cs.user_id = ?
        ORDER BY cs.last_activity DESC
        LIMIT ?
    """, user_id, limit)
    # 截断预览
    for r in rows:
        if r.get("last_preview") and len(r["last_preview"]) > 60:
            r["last_preview"] = r["last_preview"][:60] + "..."
    return rows


async def get_session_by_id(session_id: str) -> dict | None:
    """获取单个会话信息"""
    rows = await execute("SELECT * FROM chat_session WHERE id = ?", session_id)
    return rows[0] if rows else None


# ============================================================
# 消息管理
# ============================================================

async def add_message(session_id: str, role: str, content: str,
                      turn_index: int, meta: dict = None) -> str:
    """添加一条消息，返回 message_id"""
    mid = _uid()
    meta_json = _to_json(meta or {})
    await execute(
        """INSERT INTO chat_message (id, session_id, role, content, turn_index, meta)
           VALUES (?, ?, ?, ?, ?, ?)""",
        mid, session_id, role, content, turn_index, meta_json
    )
    return mid


async def get_recent_messages(session_id: str, limit: int = 20) -> list[dict]:
    """获取最近 N 条消息（从最新往前取）"""
    return await execute(
        """SELECT id, role, content, turn_index, meta, created_at
           FROM chat_message
           WHERE session_id = ?
           ORDER BY turn_index DESC
           LIMIT ?""",
        session_id, limit
    )


async def count_session_messages(session_id: str) -> int:
    """统计会话消息数"""
    rows = await execute(
        "SELECT COUNT(*) AS cnt FROM chat_message WHERE session_id = ?",
        session_id
    )
    return rows[0]["cnt"] if rows else 0


# ============================================================
# 胶卷管理
# ============================================================

async def add_film(user_id: str, name: str, film_type: str = None,
                   iso: int = None, format: str = "135",
                   frames: int = None, sheet_count: int = None,
                   quantity: int = 1, unit: str = "卷",
                   purchase_date: str = None, expiry_date: str = None,
                   purchase_price: float = None, current_value: float = None,
                   price: float = None,
                   storage_location: str = None,
                   status: str = "未使用", meta: dict = None) -> str:
    """添加胶卷记录，返回 film_id"""
    fid = _uid()
    meta_json = _to_json(meta or {})
    await execute(
        """INSERT INTO film (id, user_id, name, film_type, iso, format,
           frames, sheet_count, quantity, unit, purchase_date, expiry_date,
           purchase_price, current_value, price,
           storage_location, status, meta)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        fid, user_id, name, film_type, iso, format,
        frames, sheet_count, quantity, unit, purchase_date, expiry_date,
        purchase_price, current_value, price,
        storage_location, status, meta_json
    )
    return fid


async def query_film(user_id: str, filters: dict = None,
                     order_by: str = "created_at", order_dir: str = "DESC",
                     limit: int = 50) -> list[dict]:
    """查询胶卷，支持多种过滤条件"""
    where_parts = ["user_id = ?"]
    params = [user_id]

    for key, value in (filters or {}).items():
        if value is None:
            continue
        if "__gte" in key:
            field = key.replace("__gte", "")
            where_parts.append(f"{field} >= ?")
            params.append(value)
        elif "__lte" in key:
            field = key.replace("__lte", "")
            where_parts.append(f"{field} <= ?")
            params.append(value)
        elif "__ilike" in key:
            field = key.replace("__ilike", "")
            where_parts.append(f"{field} LIKE ?")
            params.append(str(value))
        elif "__eq" in key:
            field = key.replace("__eq", "")
            where_parts.append(f"{field} = ?")
            params.append(value)
        elif key.startswith("meta__"):
            meta_key = key.replace("meta__", "", 1)
            where_parts.append(f"json_extract(meta, '$.{meta_key}') = ?")
            params.append(str(value))
        else:
            where_parts.append(f"{key} = ?")
            params.append(value)

    where = " AND ".join(where_parts)
    params.append(limit)
    sql = f"SELECT * FROM film WHERE {where} ORDER BY {order_by} {order_dir} LIMIT ?"

    return await execute(sql, *params)


async def update_film(film_id: str, **kwargs) -> bool:
    """更新胶卷记录"""
    meta = kwargs.pop("meta", None)
    set_parts = []
    params = []

    for key, value in kwargs.items():
        if value is not None:
            set_parts.append(f"{key} = ?")
            params.append(value)

    if meta is not None:
        # 合并 JSON
        set_parts.append("meta = ?")
        # 获取当前 meta，合并后写入
        current = await execute("SELECT meta FROM film WHERE id = ?", film_id)
        if current and current[0].get("meta"):
            current_meta = current[0]["meta"]
            if isinstance(current_meta, str):
                current_meta = json.loads(current_meta)
            current_meta.update(meta)
            params.append(_to_json(current_meta))
        else:
            params.append(_to_json(meta))

    if not set_parts:
        return False

    set_parts.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_parts)
    params.append(film_id)

    sql = f"UPDATE film SET {set_clause} WHERE id = ?"
    await execute(sql, *params)
    return True


async def delete_film(film_id: str) -> bool:
    """删除胶卷记录"""
    await execute("DELETE FROM film WHERE id = ?", film_id)
    return True


# ============================================================
# 设备管理
# ============================================================

async def add_gear(user_id: str, name: str, gear_type: str,
                   category: str = None,
                   brand: str = None, model: str = None,
                   nickname: str = None, serial_number: str = None,
                   camera_type: str = None, lens_mount: str = None,
                   shutter_type: str = None, format_support: str = None,
                   purchase_date: str = None, purchase_price: float = None,
                   sell_price: float = None, sell_date: str = None,
                   current_value: float = None, price: float = None,
                   condition: str = None, status: str = "在用",
                   storage_location: str = None,
                   parent_id: str = None, compatible_with: list = None,
                   meta: dict = None) -> str:
    """添加设备记录，返回 gear_id"""
    gid = _uid()
    meta_json = _to_json(meta or {})
    comp_json = _to_json(compatible_with or [])
    await execute(
        """INSERT INTO gear (id, user_id, name, gear_type, category,
           brand, model, nickname, serial_number,
           camera_type, lens_mount, shutter_type, format_support,
           purchase_date, purchase_price, sell_price, sell_date,
           current_value, price, condition, status, storage_location,
           parent_id, compatible_with, meta)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        gid, user_id, name, gear_type, category,
        brand, model, nickname, serial_number,
        camera_type, lens_mount, shutter_type, format_support,
        purchase_date, purchase_price, sell_price, sell_date,
        current_value, price, condition, status, storage_location,
        parent_id, comp_json, meta_json
    )
    return gid


async def query_gear(user_id: str, filters: dict = None,
                     order_by: str = "created_at", order_dir: str = "DESC",
                     limit: int = 50) -> list[dict]:
    """查询设备"""
    where_parts = ["user_id = ?"]
    params = [user_id]

    for key, value in (filters or {}).items():
        if value is None:
            continue
        where_parts.append(f"{key} = ?")
        params.append(value)

    where = " AND ".join(where_parts)
    params.append(limit)
    sql = f"SELECT * FROM gear WHERE {where} ORDER BY {order_by} {order_dir} LIMIT ?"

    return await execute(sql, *params)


async def update_gear(gear_id: str, **kwargs) -> bool:
    """更新设备记录"""
    meta = kwargs.pop("meta", None)
    set_parts = []
    params = []

    for key, value in kwargs.items():
        if value is not None:
            set_parts.append(f"{key} = ?")
            params.append(value)

    if meta is not None:
        current = await execute("SELECT meta FROM gear WHERE id = ?", gear_id)
        if current and current[0].get("meta"):
            current_meta = current[0]["meta"]
            if isinstance(current_meta, str):
                current_meta = json.loads(current_meta)
            current_meta.update(meta)
            params.append(_to_json(current_meta))
        else:
            params.append(_to_json(meta))

    if not set_parts:
        return False

    set_parts.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_parts)
    params.append(gear_id)

    await execute(f"UPDATE gear SET {set_clause} WHERE id = ?", *params)
    return True


async def delete_gear(gear_id: str) -> bool:
    """删除设备记录"""
    await execute("DELETE FROM gear WHERE id = ?", gear_id)
    return True


# ============================================================
# 关联与查询
# ============================================================

async def create_entity_link(message_id: str, entity_type: str,
                             entity_id: str, action: str = "created"):
    """建立消息-实体关联"""
    lid = _uid()
    await execute(
        """INSERT INTO message_entity_link (id, message_id, entity_type, entity_id, action)
           VALUES (?, ?, ?, ?, ?)""",
        lid, message_id, entity_type, entity_id, action
    )
    return lid


async def query_entity_by_message(message_id: str) -> list[dict]:
    """根据消息 ID 查询关联的业务数据"""
    return await execute(
        """SELECT entity_type, entity_id, action FROM message_entity_link
           WHERE message_id = ?""",
        message_id
    )


async def query_messages_by_entity(entity_type: str, entity_id: str) -> list[dict]:
    """根据业务数据查询关联的消息"""
    return await execute(
        """SELECT m.id, m.role, m.content, m.created_at, l.action
           FROM message_entity_link l
           JOIN chat_message m ON m.id = l.message_id
           WHERE l.entity_type = ? AND l.entity_id = ?
           ORDER BY m.created_at""",
        entity_type, entity_id
    )


# ============================================================
# 长期记忆
# ============================================================

async def add_memory(user_id: str, memory_type: str, content: str,
                     category: str = None, confidence: float = 0.8,
                     tags: list = None, source: str = None) -> str:
    """添加一条长期记忆"""
    mid = _uid()
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    await execute(
        """INSERT INTO long_term_memory
           (id, user_id, memory_type, category, content, source, confidence, tags)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        mid, user_id, memory_type, category, content, source, confidence, tags_json
    )
    return mid


async def get_active_memories(user_id: str, limit: int = 10) -> list[dict]:
    """获取活跃的长期记忆"""
    rows = await execute(
        """SELECT * FROM long_term_memory
           WHERE user_id = ? AND is_active = 1
           ORDER BY confidence DESC, updated_at DESC
           LIMIT ?""",
        user_id, limit
    )
    return rows


async def find_similar_memory(user_id: str, content: str) -> dict | None:
    """查找内容相似的已有记忆（简单包含匹配）"""
    # SQLite 不支持 pg_trgm，用 LIKE 简化
    rows = await execute(
        """SELECT * FROM long_term_memory
           WHERE user_id = ? AND is_active = 1
             AND content LIKE ?
           LIMIT 1""",
        user_id, f"%{content[:20]}%"
    )
    return rows[0] if rows else None


async def refresh_memory(memory_id: str):
    """刷新记忆（提高置信度、更新时间）"""
    await execute(
        """UPDATE long_term_memory
           SET confidence = MIN(confidence + 0.05, 1.0),
               updated_at = datetime('now')
           WHERE id = ?""",
        memory_id
    )


# ============================================================
# 拍摄记录管理
# ============================================================

async def add_shoot(user_id: str, title: str = None,
                    shoot_date: str = None, location: str = None,
                    description: str = None, tags: list = None,
                    rating: int = None, weather: str = None,
                    meta: dict = None) -> str:
    """创建拍摄记录，返回 shoot_id"""
    sid = _uid()
    meta_json = _to_json(meta or {})
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    await execute(
        """INSERT INTO shoot (id, user_id, title, shoot_date, location,
           description, tags, rating, weather, meta)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        sid, user_id, title, shoot_date, location,
        description, tags_json, rating, weather, meta_json
    )
    return sid


async def query_shoot(user_id: str, filters: dict = None,
                      order_by: str = "created_at", order_dir: str = "DESC",
                      limit: int = 50) -> list[dict]:
    """查询拍摄记录"""
    where_parts = ["user_id = ?"]
    params = [user_id]

    for key, value in (filters or {}).items():
        if value is None:
            continue
        if key == "date_from":
            where_parts.append("shoot_date >= ?")
            params.append(value)
        elif key == "date_to":
            where_parts.append("shoot_date <= ?")
            params.append(value)
        elif "__like" in key:
            field = key.replace("__like", "")
            where_parts.append(f"{field} LIKE ?")
            params.append(f"%{value}%")
        elif key in ("title", "location", "status"):
            where_parts.append(f"{key} = ?")
            params.append(value)
        else:
            where_parts.append(f"{key} = ?")
            params.append(value)

    where = " AND ".join(where_parts)
    params.append(limit)
    sql = f"SELECT * FROM shoot WHERE {where} ORDER BY {order_by} {order_dir} LIMIT ?"
    return await execute(sql, *params)


async def update_shoot(shoot_id: str, **kwargs) -> bool:
    """更新拍摄记录"""
    meta = kwargs.pop("meta", None)
    tags = kwargs.pop("tags", None)
    set_parts = []
    params = []

    for key, value in kwargs.items():
        if value is not None:
            set_parts.append(f"{key} = ?")
            params.append(value)

    if tags is not None:
        set_parts.append("tags = ?")
        params.append(json.dumps(tags, ensure_ascii=False))
    if meta is not None:
        set_parts.append("meta = ?")
        params.append(_to_json(meta))

    if not set_parts:
        return False

    set_parts.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_parts)
    params.append(shoot_id)
    await execute(f"UPDATE shoot SET {set_clause} WHERE id = ?", *params)
    return True


async def delete_shoot(shoot_id: str) -> bool:
    """删除拍摄记录及其关联"""
    await execute("DELETE FROM shoot_gear WHERE shoot_id = ?", shoot_id)
    await execute("UPDATE film_loading SET shoot_id = NULL WHERE shoot_id = ?", shoot_id)
    await execute("DELETE FROM shoot WHERE id = ?", shoot_id)
    return True


# ============================================================
# 装卷事件管理
# ============================================================

async def add_film_loading(user_id: str, film_id: str,
                           camera_id: str = None, shoot_id: str = None,
                           loaded_at: str = None,
                           iso_setting: int = None, push_pull: int = 0,
                           notes: str = None, status: str = "在机内",
                           meta: dict = None) -> str:
    """创建装卷事件，返回 loading_id"""
    lid = _uid()
    meta_json = _to_json(meta or {})
    loaded = loaded_at or datetime.now().isoformat()
    await execute(
        """INSERT INTO film_loading (id, user_id, film_id, camera_id, shoot_id,
           loaded_at, iso_setting, push_pull, notes, status, meta)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        lid, user_id, film_id, camera_id, shoot_id,
        loaded, iso_setting, push_pull, notes, status, meta_json
    )
    return lid


async def query_film_loading(user_id: str, filters: dict = None,
                             order_by: str = "loaded_at",
                             order_dir: str = "DESC",
                             limit: int = 50) -> list[dict]:
    """查询装卷事件"""
    where_parts = ["fl.user_id = ?"]
    params = [user_id]

    for key, value in (filters or {}).items():
        if value is None:
            continue
        if key == "film_id":
            where_parts.append("fl.film_id = ?")
            params.append(value)
        elif key == "camera_id":
            where_parts.append("fl.camera_id = ?")
            params.append(value)
        elif key == "shoot_id":
            where_parts.append("fl.shoot_id = ?")
            params.append(value)
        elif key == "status":
            where_parts.append("fl.status = ?")
            params.append(value)
        elif key == "status_in":
            placeholders = ",".join("?" for _ in value)
            where_parts.append(f"fl.status IN ({placeholders})")
            params.extend(value)

    where = " AND ".join(where_parts)
    params.append(limit)
    sql = f"""SELECT fl.*, f.name as film_name, g.name as camera_name
              FROM film_loading fl
              LEFT JOIN film f ON f.id = fl.film_id
              LEFT JOIN gear g ON g.id = fl.camera_id
              WHERE {where}
              ORDER BY fl.{order_by} {order_dir} LIMIT ?"""
    return await execute(sql, *params)


async def update_film_loading(loading_id: str, **kwargs) -> bool:
    """更新装卷事件"""
    meta = kwargs.pop("meta", None)
    set_parts = []
    params = []

    for key, value in kwargs.items():
        if value is not None:
            set_parts.append(f"{key} = ?")
            params.append(value)

    if meta is not None:
        set_parts.append("meta = ?")
        params.append(_to_json(meta))

    if not set_parts:
        return False

    set_parts.append("updated_at = datetime('now')")
    set_clause = ", ".join(set_parts)
    params.append(loading_id)
    await execute(f"UPDATE film_loading SET {set_clause} WHERE id = ?", *params)
    return True


async def get_film_loading_summary(film_id: str) -> dict:
    """获取某卷胶卷的装卷汇总（累计张数、当前在哪台相机）"""
    rows = await execute(
        """SELECT status, SUM(frames_shot) as total_frames,
                  COUNT(*) as load_times
           FROM film_loading WHERE film_id = ?
           GROUP BY status""",
        film_id
    )
    current = await execute(
        """SELECT id, camera_id, loaded_at, frames_shot
           FROM film_loading
           WHERE film_id = ? AND status = '在机内'
           ORDER BY loaded_at DESC LIMIT 1""",
        film_id
    )
    total_frames = sum(r.get("total_frames", 0) or 0 for r in rows)
    return {
        "total_frames": total_frames,
        "loading_count": sum(r.get("load_times", 0) or 0 for r in rows),
        "current_loading": current[0] if current else None,
        "by_status": {r["status"]: {"count": r["load_times"], "frames": r["total_frames"]}
                      for r in rows}
    }


# ============================================================
# 拍摄设备关联
# ============================================================

async def add_shoot_gear(shoot_id: str, gear_id: str,
                         role: str = "主机", notes: str = None) -> str:
    """关联设备到拍摄记录"""
    sgid = _uid()
    await execute(
        "INSERT INTO shoot_gear (id, shoot_id, gear_id, role, notes) VALUES (?, ?, ?, ?, ?)",
        sgid, shoot_id, gear_id, role, notes
    )
    return sgid


async def query_shoot_gear(shoot_id: str) -> list[dict]:
    """查询拍摄关联的设备"""
    return await execute(
        """SELECT sg.*, g.name, g.gear_type, g.brand, g.model
           FROM shoot_gear sg
           JOIN gear g ON g.id = sg.gear_id
           WHERE sg.shoot_id = ?
           ORDER BY sg.created_at""",
        shoot_id
    )


async def get_shoot_detail(shoot_id: str) -> dict:
    """获取拍摄完整详情（含胶卷、设备）"""
    shoot = await execute("SELECT * FROM shoot WHERE id = ?", shoot_id)
    if not shoot:
        return {}
    result = dict(shoot[0])
    result["film_loadings"] = await query_film_loading(
        result.get("user_id", "default"),
        {"shoot_id": shoot_id}
    )
    result["gear"] = await query_shoot_gear(shoot_id)
    return result
