"""
胶卷管理 — 基于 entity_store 的灵活版本

核心变化：
  - 不再定义固定字段参数，AI 自由填 data 字典
  - 所有 CRUD 委托给 entity_store
  - 保留审计日志（基于 entity_store）
"""

import time

from db.entity_store import (
    save_entity,
    query_entities,
    get_entity,
    delete_entity,
    search_entities,
)
from db.audit import record_audit
from db.schema import create_entity_link


# ============================================================
# 全局上下文（由 chat_loop 或 web server 设置）
# ============================================================

_current_context = {
    "user_id": "web_user",
    "session_id": None,
    "message_id": None,
}


def set_context(user_id: str = "web_user", session_id: str = None, message_id: str = None):
    """设置当前上下文"""
    _current_context["user_id"] = user_id
    _current_context["session_id"] = session_id
    _current_context["message_id"] = message_id


# ============================================================
# 工具函数（全部 async）
# ============================================================


async def film_add(name: str, data: dict = None) -> dict:
    """
    添加胶卷记录。

    AI 可根据对话内容自由决定 data 中的字段。
    常见字段参考（非强制）：
      type:         '彩色负片' / '反转片' / '黑白负片' / '电影卷'
      brand:        'Kodak' / 'Fuji' / 'Ilford' / ...
      iso:          100 / 200 / 400 / 800 / 1600 / 3200
      format:       '135' / '120' / '4×5' / '8×10' / '半格' / '110'
      frames:       36（135 默认）/ 12（120 默认）/ 72（半格）
      quantity:     数量（默认 1）
      unit:         '卷' / '盒' / '张'（默认 '卷'）
      status:       '未使用' / '在机内' / '已退卷' / '已使用'（默认 '未使用'）
      storage:      '冰箱-上层' / '防潮箱' / '常温柜'
      purchase:     { 'date': '2026-05-20', 'price': 180, 'channel': '淘宝', 'currency': 'CNY' }
      expiry:       '2028-03'（有效期）
      purpose:      '人像' / '街拍' / '风光' / '夜景'（拍摄用途）
      notes:        '这卷迫冲到 1600 用'（备注）
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    data = data or {}
    if "status" not in data:
        data["status"] = "未使用"

    eid = await save_entity(
        user_id=user_id,
        entity_type="film",
        name=name,
        data=data,
    )

    # 审计日志
    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="film", entity_id=eid,
        sql_text="INSERT INTO entities (type=film)",
        sql_params={"name": name, "data_keys": list(data.keys())},
        data_after={"id": eid, "name": name, "data": data},
        rows_affected=1, tool_name="film_add",
        tool_args={"name": name, "data_keys": list(data.keys())},
        duration_ms=int((time.time() - start) * 1000),
    )

    # 消息-实体关联
    if mid:
        await create_entity_link(mid, "film", eid, "created")

    return {
        "id": eid,
        "name": name,
        "status": "ok",
        "message": f"✅ 已添加胶卷: {name}",
    }


async def film_query(filters: dict = None, limit: int = 50) -> dict:
    """
    查询胶卷库存。

    支持任意字段过滤，例如：
      {"status": "未使用", "iso": 400}
      {"type": "彩色负片", "purchase.channel": "淘宝"}
    不传 filters 则返回全部。
    """
    user_id = _current_context["user_id"]

    results = await query_entities(
        user_id=user_id,
        entity_type="film",
        filters=filters,
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "films": results,
        "message": f"找到 {len(results)} 条胶卷记录",
    }


async def film_update(entity_id: str, data: dict = None, name: str = None) -> dict:
    """
    修改胶卷记录。

    data 中只传入需要更新的字段即可，未传的字段保持不变。
    例如：data = {"status": "已使用", "storage": "已冲扫区"}
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    # 先查旧数据
    old = await get_entity(entity_id)
    if not old:
        return {"status": "error", "message": f"未找到该胶卷记录"}

    # 合并 data
    old_data = old.get("data") or {}
    if data:
        old_data.update(data)

    new_name = name or old.get("name")

    await save_entity(
        user_id=user_id,
        entity_type="film",
        name=new_name,
        data=old_data,
        entity_id=entity_id,
    )

    # 审计
    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="film", entity_id=entity_id,
        sql_text="UPDATE entities (type=film)",
        sql_params=data,
        data_before=old.get("data"),
        data_after=old_data,
        rows_affected=1, tool_name="film_update",
        tool_args={"entity_id": entity_id, "data": data},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {
        "status": "ok",
        "message": "胶卷记录已更新",
        "film": {"id": entity_id, "name": new_name, "data": old_data},
    }


async def film_delete(entity_id: str, confirmed: bool = False) -> dict:
    """删除胶卷记录（需确认）"""
    if not confirmed:
        old = await get_entity(entity_id)
        name = old["name"] if old else "该胶卷"
        return {
            "status": "error",
            "message": f"请确认是否删除「{name}」？再次调用时传 confirmed=true",
        }

    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    await delete_entity(entity_id)

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="DELETE", entity_type="film", entity_id=entity_id,
        rows_affected=1, tool_name="film_delete",
        tool_args={"entity_id": entity_id},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "胶卷记录已删除"}


async def film_search(query: str, limit: int = 10) -> dict:
    """
    全文搜索胶卷（通过 FTS5）。

    自然语言搜索，例如：
      "Portra 400 人像"
      "过期彩色负片"
      "Kodak 135"
    """
    user_id = _current_context["user_id"]

    results = await search_entities(
        user_id=user_id,
        query_text=query,
        entity_type="film",
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "results": results,
        "message": f"找到 {len(results)} 条相关胶卷",
    }


async def film_stats() -> dict:
    """获取胶卷库存统计"""
    from db.entity_store import get_stats
    stats = await get_stats(_current_context["user_id"])
    film_stats = stats.get("film", {})

    return {
        "status": "ok",
        "stats": film_stats,
        "message": (
            f"📊 共有 {film_stats.get('count', 0)} 卷胶卷，"
            f"总价值约 ¥{film_stats.get('total_price', 0):.0f}，"
            f"已过期 {film_stats.get('expired', 0)} 卷"
        ),
    }


async def film_check_expiry() -> dict:
    """检查即将过期或已过期的胶卷"""
    user_id = _current_context["user_id"]
    from datetime import datetime

    all_films = await query_entities(user_id, "film", limit=500)

    today = datetime.now().date()
    expired = []
    expiring = []

    for f in all_films:
        data = f.get("data") or {}
        exp_str = data.get("expiry")
        if exp_str:
            try:
                exp_date = datetime.strptime(str(exp_str)[:10], "%Y-%m-%d").date()
                days = (exp_date - today).days
                if days < 0:
                    expired.append({**f, "days_overdue": abs(days)})
                elif days <= 30:
                    expiring.append({**f, "days_left": days})
            except (ValueError, TypeError):
                pass

    return {
        "status": "ok",
        "expired": expired,
        "expiring_soon": expiring,
        "message": f"已过期: {len(expired)} 卷，30天内过期: {len(expiring)} 卷",
    }
