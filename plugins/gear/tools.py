"""
设备管理 — 基于 entity_store 的灵活版本
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
# 全局上下文
# ============================================================

_current_context = {
    "user_id": "web_user",
    "session_id": None,
    "message_id": None,
}


def set_context(user_id: str = "web_user", session_id: str = None, message_id: str = None):
    _current_context["user_id"] = user_id
    _current_context["session_id"] = session_id
    _current_context["message_id"] = message_id


# ============================================================
# 工具函数
# ============================================================


async def gear_add(name: str, data: dict = None) -> dict:
    """
    添加设备记录。

    AI 自由决定 data 字段。常见字段参考：
      gear_type:      '相机' / '镜头' / '配件' / '冲扫设备'
      brand:          'Leica' / 'Nikon' / 'Canon' / 'Hasselblad' / ...
      model:          'M6' / 'F3' / 'AE-1'
      nickname:       '小黑'（自定义昵称）
      serial_number:  'SN123456'
      category:       '主机' / '镜头' / '配件'
      condition:      '全新' / '95新' / '正常使用痕迹' / '战斗成色'
      status:         '在用' / '闲置' / '已出'
      storage:        '防潮箱-A格' / '摄影包'
      camera_type:    '旁轴' / '单反' / '双反' / '中画幅' / '大画幅' / '傻瓜机'
      lens_mount:     'M口' / 'F口' / 'EF口' / 'PK口'
      format_support: '135' / '120' / '4×5'
      purchase:       { 'date': '2026-01-15', 'price': 12000, 'channel': '闲鱼', 'currency': 'CNY' }
      sell:           { 'date': '2026-05-01', 'price': 11000 }
      notes:          '测光略偏差，-0.5EV 补偿'
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    data = data or {}
    if "status" not in data:
        data["status"] = "在用"

    eid = await save_entity(
        user_id=user_id,
        entity_type="gear",
        name=name,
        data=data,
    )

    # 审计日志
    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="gear", entity_id=eid,
        sql_text="INSERT INTO entities (type=gear)",
        sql_params={"name": name, "data_keys": list(data.keys())},
        data_after={"id": eid, "name": name, "data": data},
        rows_affected=1, tool_name="gear_add",
        tool_args={"name": name, "data_keys": list(data.keys())},
        duration_ms=int((time.time() - start) * 1000),
    )

    if mid:
        await create_entity_link(mid, "gear", eid, "created")

    return {
        "id": eid,
        "name": name,
        "status": "ok",
        "message": f"✅ 已添加设备: {name}",
    }


async def gear_query(filters: dict = None, limit: int = 50) -> dict:
    """
    查询设备。

    支持任意字段过滤，例如：
      {"gear_type": "相机", "brand": "Leica"}
      {"status": "在用"}
      {"category": "镜头", "lens_mount": "M口"}
    """
    user_id = _current_context["user_id"]

    results = await query_entities(
        user_id=user_id,
        entity_type="gear",
        filters=filters,
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "gear": results,
        "message": f"找到 {len(results)} 件设备",
    }


async def gear_update(entity_id: str, data: dict = None, name: str = None) -> dict:
    """修改设备记录"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    old = await get_entity(entity_id)
    if not old:
        return {"status": "error", "message": "未找到该设备记录"}

    old_data = old.get("data") or {}
    if data:
        old_data.update(data)

    new_name = name or old.get("name")

    await save_entity(
        user_id=user_id,
        entity_type="gear",
        name=new_name,
        data=old_data,
        entity_id=entity_id,
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="gear", entity_id=entity_id,
        sql_text="UPDATE entities (type=gear)",
        sql_params=data,
        data_before=old.get("data"),
        data_after=old_data,
        rows_affected=1, tool_name="gear_update",
        tool_args={"entity_id": entity_id, "data": data},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {
        "status": "ok",
        "message": "设备记录已更新",
        "gear": {"id": entity_id, "name": new_name, "data": old_data},
    }


async def gear_delete(entity_id: str, confirmed: bool = False) -> dict:
    """删除设备记录（需确认）"""
    if not confirmed:
        old = await get_entity(entity_id)
        name = old["name"] if old else "该设备"
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
        operation="DELETE", entity_type="gear", entity_id=entity_id,
        rows_affected=1, tool_name="gear_delete",
        tool_args={"entity_id": entity_id},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "设备记录已删除"}


async def gear_search(query: str, limit: int = 10) -> dict:
    """全文搜索设备"""
    user_id = _current_context["user_id"]

    results = await search_entities(
        user_id=user_id,
        query_text=query,
        entity_type="gear",
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "results": results,
        "message": f"找到 {len(results)} 件相关设备",
    }


async def gear_stats() -> dict:
    """设备统计"""
    from db.entity_store import get_stats
    stats = await get_stats(_current_context["user_id"])
    gear_stats = stats.get("gear", {})

    return {
        "status": "ok",
        "stats": gear_stats,
        "message": (
            f"📊 共有 {gear_stats.get('count', 0)} 件设备，"
            f"总价值约 ¥{gear_stats.get('total_price', 0):.0f}"
        ),
    }
