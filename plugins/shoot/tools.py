"""
拍摄记录管理 — 工具函数实现
"""

import json
import time
from datetime import datetime

from db.schema import (
    add_shoot as db_add_shoot,
    query_shoot as db_query_shoot,
    update_shoot as db_update_shoot,
    add_film_loading as db_add_loading,
    query_film_loading as db_query_loading,
    update_film_loading as db_update_loading,
    get_film_loading_summary,
    add_shoot_gear as db_add_shoot_gear,
    query_shoot_gear as db_query_shoot_gear,
    get_shoot_detail as db_get_shoot_detail,
    query_film as db_query_film,
    query_gear as db_query_gear,
    update_film as db_update_film,
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
    _current_context["user_id"] = user_id
    _current_context["session_id"] = session_id
    _current_context["message_id"] = message_id


# ============================================================
# 辅助
# ============================================================

def _uid() -> str:
    import uuid
    return str(uuid.uuid4())


async def _find_film(name: str) -> dict | None:
    """根据名称模糊查找库存中的胶卷"""
    films = await db_query_film(_current_context["user_id"],
                                 {"name__ilike": name}, limit=10)
    if not films:
        return None
    # 精确匹配优先
    exact = [f for f in films if f["name"] == name]
    return exact[0] if exact else films[0]


async def _find_gear(name: str, gear_type: str = None) -> dict | None:
    """根据名称模糊查找设备"""
    filters = {}
    if gear_type:
        filters["gear_type"] = gear_type
    gear_list = await db_query_gear(_current_context["user_id"], filters={"name__ilike": name})
    if not gear_list:
        gear_list = await db_query_gear(_current_context["user_id"], filters={"name": name})
    if not gear_list:
        return None
    exact = [g for g in gear_list if g["name"] == name]
    return exact[0] if exact else gear_list[0]


async def _find_or_create_shoot(title: str = None, location: str = None,
                                 shoot_date: str = None) -> str | None:
    """查找已有 shoot 或创建新的"""
    if not title and not location:
        return None
    # 按地点+日期查找
    filters = {}
    if location:
        filters["location"] = location
    if shoot_date:
        filters["shoot_date"] = shoot_date
    if not filters:
        filters["title__like"] = title or ""

    existing = await db_query_shoot(_current_context["user_id"], filters, limit=1)
    if existing:
        return existing[0]["id"]

    # 创建新 shoot
    sid = await db_add_shoot(
        user_id=_current_context["user_id"],
        title=title or location or "未命名拍摄",
        location=location,
        shoot_date=shoot_date,
    )
    return sid


# ============================================================
# 工具函数
# ============================================================

async def add_shoot(title: str = None, shoot_date: str = None,
                    location: str = None, description: str = None,
                    tags: list = None, weather: str = None) -> dict:
    """创建拍摄记录"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    shoot_id = await db_add_shoot(
        user_id=user_id,
        title=title or f"拍摄 {datetime.now().strftime('%m-%d')}",
        shoot_date=shoot_date or datetime.now().strftime('%Y-%m-%d'),
        location=location,
        description=description,
        tags=tags,
        weather=weather,
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="shoot", entity_id=shoot_id,
        sql_text="INSERT INTO shoot ...",
        sql_params={"title": title, "location": location, "date": shoot_date},
        rows_affected=1, tool_name="add_shoot",
        tool_args={"title": title, "location": location},
        duration_ms=int((time.time() - start) * 1000),
    )

    if mid:
        await create_entity_link(mid, "shoot", shoot_id, "created")

    return {
        "status": "ok",
        "shoot_id": shoot_id,
        "message": f"已记录拍摄活动{'「' + (title or '') + '」' if title else ''}"
    }


async def query_shoot(location__like: str = None,
                      date_from: str = None, date_to: str = None,
                      limit: int = 20) -> dict:
    """查询拍摄记录"""
    user_id = _current_context["user_id"]
    filters = {}
    if location__like:
        filters["location__like"] = location__like
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    results = await db_query_shoot(user_id, filters, limit=limit)
    return {
        "status": "ok",
        "count": len(results),
        "shoots": results,
        "message": f"找到 {len(results)} 条拍摄记录"
    }


async def load_film(film_name: str, camera_name: str = None,
                    iso_setting: int = None, push_pull: int = 0,
                    shoot_title: str = None) -> dict:
    """记录装卷事件"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    # 查胶卷
    film = await _find_film(film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存记录，请先添加胶卷"}

    # 查相机
    camera_id = None
    camera_name_found = None
    if camera_name:
        cam = await _find_gear(camera_name, gear_type="相机")
        if not cam:
            return {"status": "error", "message": f"没找到「{camera_name}」的设备记录"}
        camera_id = cam["id"]
        camera_name_found = cam["name"]
    else:
        # 查该卷最近一次在机内的相机
        summary = await get_film_loading_summary(film["id"])
        if summary.get("current_loading"):
            camera_id = summary["current_loading"]["camera_id"]

    # 关联拍摄
    shoot_id = None
    if shoot_title:
        shoot_id = await _find_or_create_shoot(title=shoot_title)

    loading_id = await db_add_loading(
        user_id=user_id,
        film_id=film["id"],
        camera_id=camera_id,
        shoot_id=shoot_id,
        iso_setting=iso_setting,
        push_pull=push_pull,
        status="在机内",
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="film_loading", entity_id=loading_id,
        sql_text="INSERT INTO film_loading ...",
        sql_params={"film_id": film["id"], "camera_id": camera_id},
        rows_affected=1, tool_name="load_film",
        tool_args={"film_name": film_name, "camera_name": camera_name},
        duration_ms=int((time.time() - start) * 1000),
    )

    camera_str = f" → {camera_name_found}" if camera_name_found else ""
    return {
        "status": "ok",
        "loading_id": loading_id,
        "message": f"已记录：{film['name']}{camera_str}（在机内）",
    }


async def unload_film(film_name: str, camera_name: str = None,
                      frames_shot: int = None) -> dict:
    """记录退卷事件"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    film = await _find_film(film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存"}

    # 找最近的"在机内"装卷记录
    filters = {"film_id": film["id"], "status": "在机内"}
    loadings = await db_query_loading(user_id, filters, limit=10)

    # 如果指定了相机，过滤
    target_loading = None
    if camera_name:
        cam = await _find_gear(camera_name)
        if cam:
            target_loading = next((l for l in loadings if l.get("camera_id") == cam["id"]), None)
    if not target_loading and loadings:
        target_loading = loadings[0]
    if not target_loading:
        return {"status": "error", "message": f"「{film['name']}」不在任何相机内"}

    updates = {
        "status": "已退卷",
        "unloaded_at": datetime.now().isoformat(),
    }
    if frames_shot is not None:
        updates["frames_shot"] = (target_loading.get("frames_shot") or 0) + frames_shot
    await db_update_loading(target_loading["id"], **updates)

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="film_loading", entity_id=target_loading["id"],
        sql_text="UPDATE film_loading SET status='已退卷' ...",
        sql_params=updates,
        rows_affected=1, tool_name="unload_film",
        tool_args={"film_name": film_name, "frames_shot": frames_shot},
        duration_ms=int((time.time() - start) * 1000),
    )

    cam_info = f"从 {target_loading.get('camera_name','?')} " if target_loading.get('camera_name') else ""
    msg = f"已退卷：{film['name']}{cam_info}"
    if frames_shot:
        msg += f"（本次拍了 {frames_shot} 张）"
    return {"status": "ok", "message": msg}


async def finish_film(film_name: str, frames_shot: int = None,
                      frames_total: int = None) -> dict:
    """标记胶卷已拍完"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    film = await _find_film(film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存"}

    # 查最新"在机内"记录
    loadings = await db_query_loading(user_id, {"film_id": film["id"], "status": "在机内"}, limit=5)
    if not loadings:
        return {"status": "error", "message": f"「{film['name']}」不在机内，请先装卷"}

    target = loadings[0]
    updates = {
        "status": "已拍完",
        "unloaded_at": datetime.now().isoformat(),
    }
    if frames_shot is not None:
        updates["frames_shot"] = (target.get("frames_shot") or 0) + frames_shot
    await db_update_loading(target["id"], **updates)

    # 扣库存
    current_qty = film.get("quantity", 0)
    if current_qty > 0:
        await db_update_film(film["id"], quantity=current_qty - 1)
        if current_qty - 1 <= 0:
            await db_update_film(film["id"], status="已使用")

    # 获取累计张数
    summary = await get_film_loading_summary(film["id"])

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="film_loading", entity_id=target["id"],
        sql_text="UPDATE film_loading SET status='已拍完'; UPDATE film SET quantity=qty-1",
        sql_params=updates,
        rows_affected=2, tool_name="finish_film",
        tool_args={"film_name": film_name},
        duration_ms=int((time.time() - start) * 1000),
    )

    cam_info = f"（{target.get('camera_name','?')}）" if target.get('camera_name') else ""
    return {
        "status": "ok",
        "message": f"🎉 {film['name']}{cam_info} 已拍完！累计拍了 {summary['total_frames']} 张，库存剩余 {current_qty - 1} 卷",
        "summary": summary,
    }


async def query_loading(status: str = None, camera_name: str = None,
                        limit: int = 20) -> dict:
    """查询装卷状态"""
    user_id = _current_context["user_id"]
    filters = {}

    if status:
        filters["status"] = status
    else:
        # 默认查活跃状态
        filters["status_in"] = ["在机内", "已退卷"]

    if camera_name:
        cam = await _find_gear(camera_name)
        if cam:
            filters["camera_id"] = cam["id"]

    results = await db_query_loading(user_id, filters, limit=limit)
    return {
        "status": "ok",
        "count": len(results),
        "loadings": results,
        "message": f"找到 {len(results)} 条装卷记录"
    }
