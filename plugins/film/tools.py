"""
胶卷管理 — 工具函数实现（异步）
"""

import json
import time
from datetime import datetime

from db.schema import (
    add_film as db_add_film,
    query_film as db_query_film,
    update_film as db_update_film,
    delete_film as db_delete_film,
    create_entity_link,
)
from db.audit import record_audit


# ============================================================
# 全局上下文（由 chat_loop 或 web server 设置）
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

async def add_film(name: str, quantity: int = 1, iso: int = None,
                   film_type: str = None, format: str = "135",
                   frames: int = None, sheet_count: int = None,
                   purchase_date: str = None, expiry_date: str = None,
                   price: float = None, storage_location: str = None,
                   status: str = "未使用", meta: dict = None) -> dict:
    """添加胶卷记录"""
    start = time.time()
    user_id = _current_context["user_id"]

    # 根据名称和格式自动推断张数
    auto_frames = frames
    if auto_frames is None and sheet_count is None:
        fmt = (format or "135").strip()
        if fmt == "135":
            auto_frames = 36
        elif fmt == "120":
            auto_frames = 12  # 6x6 默认
        elif fmt in ("4x5", "4×5", "5x7", "5×7", "8x10", "8×10"):
            pass  # 大画幅默认不设 frames，用 sheet_count
        elif fmt in ("半格", "half-frame"):
            auto_frames = 72

    fid = await db_add_film(
        user_id=user_id,
        name=name,
        film_type=film_type,
        iso=iso,
        format=format,
        frames=auto_frames,
        sheet_count=sheet_count,
        quantity=quantity,
        purchase_date=purchase_date,
        expiry_date=expiry_date,
        purchase_price=price,
        price=price,
        storage_location=storage_location,
        status=status,
        meta=meta or {},
    )

    # 记录审计日志
    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="INSERT",
        entity_type="film",
        entity_id=fid,
        sql_text="INSERT INTO film ...",
        sql_params={"name": name, "quantity": quantity, "iso": iso},
        data_after={"id": fid, "name": name, "quantity": quantity, "iso": iso},
        rows_affected=1,
        tool_name="add_film",
        tool_args={"name": name, "quantity": quantity},
        duration_ms=int((time.time() - start) * 1000),
    )

    # 建立消息-实体关联
    if _current_context["message_id"]:
        await create_entity_link(
            message_id=_current_context["message_id"],
            entity_type="film",
            entity_id=fid,
            action="created",
        )

    return {
        "id": fid,
        "name": name,
        "quantity": quantity,
        "iso": iso,
        "status": "ok",
        "message": f"已添加胶卷: {name} × {quantity}"
    }


async def query_film(filters: dict = None, order_by: str = "created_at",
                     order_dir: str = "DESC", limit: int = 50) -> dict:
    """查询胶卷库存"""
    user_id = _current_context["user_id"]

    results = await db_query_film(
        user_id=user_id,
        filters=filters,
        order_by=order_by,
        order_dir=order_dir,
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "films": results,
        "message": f"找到 {len(results)} 条胶卷记录"
    }


async def update_film(film_id: str, **kwargs) -> dict:
    """修改胶卷记录"""
    start = time.time()
    user_id = _current_context["user_id"]

    # 先查旧数据
    old_data = await db_query_film(user_id, {"id": film_id})
    data_before = old_data[0] if old_data else None

    await db_update_film(film_id, **kwargs)

    # 查新数据
    new_data = await db_query_film(user_id, {"id": film_id})
    data_after = new_data[0] if new_data else None

    # 审计日志
    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="UPDATE",
        entity_type="film",
        entity_id=film_id,
        sql_text="UPDATE film ...",
        sql_params=kwargs,
        data_before=data_before,
        data_after=data_after,
        rows_affected=1,
        tool_name="update_film",
        tool_args=kwargs,
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "胶卷记录已更新", "film": data_after}


async def delete_film(film_id: str, confirmed: bool = False) -> dict:
    """删除胶卷记录（需确认）"""
    if not confirmed:
        return {"status": "error",
                "message": "需要用户确认后才能删除，请先展示胶卷信息并询问用户是否确认删除"}

    start = time.time()
    user_id = _current_context["user_id"]

    await db_delete_film(film_id)

    await record_audit(
        user_id=user_id,
        session_id=_current_context["session_id"],
        message_id=_current_context["message_id"],
        operation="DELETE",
        entity_type="film",
        entity_id=film_id,
        rows_affected=1,
        tool_name="delete_film",
        tool_args={"film_id": film_id},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "胶卷记录已删除"}


async def check_expiring_film() -> dict:
    """检查即将过期或已过期的胶卷"""
    user_id = _current_context["user_id"]

    # 查所有胶卷
    films = await db_query_film(user_id, limit=500)
    today = datetime.now().date()
    expiring = []
    already_expired = []

    for f in films:
        if f.get("expiry_date"):
            try:
                exp_date = datetime.fromisoformat(f["expiry_date"]).date()
                days_left = (exp_date - today).days
                if days_left < 0:
                    already_expired.append({**f, "days_overdue": abs(days_left)})
                elif days_left <= 30:
                    expiring.append({**f, "days_left": days_left})
            except (ValueError, TypeError):
                pass

    return {
        "status": "ok",
        "expired": already_expired,
        "expiring_soon": expiring,
        "message": f"已过期: {len(already_expired)} 卷, 即将过期: {len(expiring)} 卷"
    }
