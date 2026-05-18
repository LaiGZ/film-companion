"""
设备管理 — 工具函数实现（异步）
"""

import time

from db.schema import (
    add_gear as db_add_gear,
    query_gear as db_query_gear,
    update_gear as db_update_gear,
    delete_gear as db_delete_gear,
    create_entity_link,
)
from db.audit import record_audit


# ============================================================
# 全局上下文
# ============================================================

_current_context = {
    "user_id": "default",
    "session_id": None,
    "message_id": None,
}


def set_context(user_id: str = "default", session_id: str = None, message_id: str = None):
    """设置当前上下文"""
    _current_context["user_id"] = user_id
    _current_context["session_id"] = session_id
    _current_context["message_id"] = message_id


# ============================================================
# 工具函数（全部 async）
# ============================================================

async def add_gear(name: str, gear_type: str,
                   category: str = None,
                   brand: str = None, model: str = None,
                   nickname: str = None, serial_number: str = None,
                   camera_type: str = None, lens_mount: str = None,
                   shutter_type: str = None, format_support: str = None,
                   purchase_date: str = None, price: float = None,
                   condition: str = None, status: str = "在用",
                   storage_location: str = None, meta: dict = None) -> dict:
    """添加设备记录"""
    start = time.time()
    user_id = _current_context["user_id"]

    # 自动推断 category
    auto_category = category
    if not auto_category:
        if gear_type in ("相机",):
            auto_category = "主机"
        elif gear_type in ("镜头",):
            auto_category = "镜头"
        else:
            auto_category = "配件"

    gid = await db_add_gear(
        user_id=user_id,
        name=name,
        gear_type=gear_type,
        category=auto_category,
        brand=brand,
        model=model,
        nickname=nickname,
        serial_number=serial_number,
        camera_type=camera_type,
        lens_mount=lens_mount,
        shutter_type=shutter_type,
        format_support=format_support,
        purchase_date=purchase_date,
        purchase_price=price,
        price=price,
        condition=condition,
        status=status,
        storage_location=storage_location,
        meta=meta or {},
    )

    # 审计日志
    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="INSERT",
        entity_type="gear",
        entity_id=gid,
        sql_text="INSERT INTO gear ...",
        sql_params={"name": name, "gear_type": gear_type},
        data_after={"id": gid, "name": name, "gear_type": gear_type},
        rows_affected=1,
        tool_name="add_gear",
        tool_args={"name": name, "gear_type": gear_type},
        duration_ms=int((time.time() - start) * 1000),
    )

    # 消息-实体关联
    if _current_context["message_id"]:
        await create_entity_link(
            message_id=_current_context["message_id"],
            entity_type="gear",
            entity_id=gid,
            action="created",
        )

    return {
        "id": gid,
        "name": name,
        "gear_type": gear_type,
        "status": "ok",
        "message": f"已添加设备: {name}"
    }


async def query_gear(filters: dict = None, order_by: str = "created_at",
                     order_dir: str = "DESC", limit: int = 50) -> dict:
    """查询设备"""
    user_id = _current_context["user_id"]

    results = await db_query_gear(
        user_id=user_id,
        filters=filters,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "gear": results,
        "message": f"找到 {len(results)} 件设备"
    }


async def update_gear(gear_id: str, **kwargs) -> dict:
    """修改设备记录"""
    start = time.time()
    user_id = _current_context["user_id"]

    # 查旧数据
    old_data = await db_query_gear(user_id, {"id": gear_id})
    data_before = old_data[0] if old_data else None

    await db_update_gear(gear_id, **kwargs)

    # 查新数据
    new_data = await db_query_gear(user_id, {"id": gear_id})
    data_after = new_data[0] if new_data else None

    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="UPDATE",
        entity_type="gear",
        entity_id=gear_id,
        sql_text="UPDATE gear ...",
        sql_params=kwargs,
        data_before=data_before,
        data_after=data_after,
        rows_affected=1,
        tool_name="update_gear",
        tool_args=kwargs,
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "设备记录已更新", "gear": data_after}


async def delete_gear(gear_id: str, confirmed: bool = False) -> dict:
    """删除设备记录"""
    if not confirmed:
        return {"status": "error",
                "message": "需要用户确认后才能删除，请先展示设备信息并询问用户是否确认删除"}

    start = time.time()
    user_id = _current_context["user_id"]

    await db_delete_gear(gear_id)

    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="DELETE",
        entity_type="gear",
        entity_id=gear_id,
        rows_affected=1,
        tool_name="delete_gear",
        tool_args={"gear_id": gear_id},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "设备记录已删除"}
