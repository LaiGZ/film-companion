"""
拍摄记录管理 — 基于 entity_store 的灵活版本
"""

import time
from datetime import datetime

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
# 辅助
# ============================================================

async def _find_entity(entity_type: str, name: str) -> dict | None:
    """按名称模糊查找实体"""
    results = await query_entities(
        _current_context["user_id"],
        entity_type=entity_type,
        limit=10,
    )
    # 精确匹配优先
    for r in results:
        if r.get("name") == name:
            return r
    # LIKE 匹配
    for r in results:
        if name.lower() in (r.get("name") or "").lower():
            return r
    return None


async def _find_loading(entity_type: str, film_id: str) -> list[dict]:
    """查找某胶卷的装卷记录"""
    return await query_entities(
        _current_context["user_id"],
        entity_type=entity_type,
        filters={"film_id": film_id},
        limit=10,
    )


# ============================================================
# 工具函数
# ============================================================


async def shoot_add(title: str = None, data: dict = None) -> dict:
    """
    创建拍摄记录。

    AI 自由决定 data 字段。常见字段参考：
      title:        '京都漫步'（标题）
      shoot_date:   '2026-05-20'（拍摄日期）
      location:     '京都·岚山'（地点）
      description:  '和友人一起扫街'（描述）
      weather:      '晴' / '阴' / '雨'（天气）
      tags:         ['街拍', '人文', '京都']（标签）
      rating:       1-5 星评价
      camera_used:  ['Leica M6', 'Nikon F3']（所用设备）
      film_used:    ['Portra 400', 'Tri-X 400']（所用胶卷）
      notes:        '整体偏暗，下次加半档曝光'
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    data = data or {}
    if "shoot_date" not in data:
        data["shoot_date"] = datetime.now().strftime("%Y-%m-%d")

    eid = await save_entity(
        user_id=user_id,
        entity_type="shoot",
        name=title or data.get("location") or f"拍摄 {datetime.now().strftime('%m-%d')}",
        data=data,
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="shoot", entity_id=eid,
        sql_text="INSERT INTO entities (type=shoot)",
        sql_params={"title": title, "data_keys": list(data.keys())},
        data_after={"id": eid, "title": title, "data": data},
        rows_affected=1, tool_name="shoot_add",
        tool_args={"title": title},
        duration_ms=int((time.time() - start) * 1000),
    )

    if mid:
        await create_entity_link(mid, "shoot", eid, "created")

    return {
        "status": "ok",
        "shoot_id": eid,
        "message": f"✅ 已记录拍摄{'「' + (title or '') + '」' if title else ''}",
    }


async def shoot_query(filters: dict = None, limit: int = 20) -> dict:
    """
    查询拍摄记录。

    支持任意字段过滤，例如：
      {"location": "京都"}
      {"shoot_date": "2026-05-20"}
      {"weather": "晴"}
    """
    user_id = _current_context["user_id"]

    results = await query_entities(
        user_id=user_id,
        entity_type="shoot",
        filters=filters,
        order_by="created_at",
        order_dir="DESC",
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "shoots": results,
        "message": f"找到 {len(results)} 条拍摄记录",
    }


async def shoot_update(entity_id: str, data: dict = None, name: str = None) -> dict:
    """修改拍摄记录"""
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    old = await get_entity(entity_id)
    if not old:
        return {"status": "error", "message": "未找到该拍摄记录"}

    old_data = old.get("data") or {}
    if data:
        old_data.update(data)

    new_name = name or old.get("name")

    await save_entity(
        user_id=user_id,
        entity_type="shoot",
        name=new_name,
        data=old_data,
        entity_id=entity_id,
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="shoot", entity_id=entity_id,
        sql_text="UPDATE entities (type=shoot)",
        sql_params=data,
        data_before=old.get("data"),
        data_after=old_data,
        rows_affected=1, tool_name="shoot_update",
        tool_args={"entity_id": entity_id, "data": data},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {
        "status": "ok",
        "message": "拍摄记录已更新",
        "shoot": {"id": entity_id, "name": new_name, "data": old_data},
    }


async def shoot_delete(entity_id: str, confirmed: bool = False) -> dict:
    """删除拍摄记录（需确认）"""
    if not confirmed:
        old = await get_entity(entity_id)
        name = old["name"] if old else "该拍摄记录"
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
        operation="DELETE", entity_type="shoot", entity_id=entity_id,
        rows_affected=1, tool_name="shoot_delete",
        tool_args={"entity_id": entity_id},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": "拍摄记录已删除"}


async def film_load(film_name: str, camera_name: str = None,
                    iso_setting: int = None, push_pull: int = 0,
                    shoot_title: str = None) -> dict:
    """
    记录装卷事件：把胶卷装进相机。

    会自动查找库存中的胶卷和相机，创建 film_loading 实体关联它们。
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    # 查胶卷库存
    film = await _find_entity("film", film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存，请先用 film_add 添加"}

    # 查相机
    camera = None
    if camera_name:
        camera = await _find_entity("gear", camera_name)
        if not camera:
            return {"status": "error", "message": f"没找到「{camera_name}」的设备记录"}

    # 更新胶卷状态为"在机内"
    film_data = film.get("data") or {}
    old_status = film_data.get("status")
    film_data["status"] = "在机内"
    await save_entity(
        user_id=user_id,
        entity_type="film",
        name=film["name"],
        data=film_data,
        entity_id=film["id"],
    )

    # 创建 loading 记录
    loading_data = {
        "film_id": film["id"],
        "film_name": film["name"],
        "camera_id": camera["id"] if camera else None,
        "camera_name": camera["name"] if camera else None,
        "iso_setting": iso_setting,
        "push_pull": push_pull,
        "loaded_at": datetime.now().isoformat(),
        "status": "在机内",
    }

    loading_id = await save_entity(
        user_id=user_id,
        entity_type="film_loading",
        name=f"{film['name']} → {(camera['name'] if camera else '?')}",
        data=loading_data,
    )

    camera_str = f" → {camera['name']}" if camera else ""
    msg = f"📷 已装卷：{film['name']}{camera_str}（原状态: {old_status or '未使用'} → 在机内）"

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="INSERT", entity_type="film_loading", entity_id=loading_id,
        sql_text=f"Created loading record + updated film status",
        sql_params={"film_name": film_name, "camera_name": camera_name},
        rows_affected=2, tool_name="film_load",
        tool_args={"film_name": film_name, "camera_name": camera_name},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "loading_id": loading_id, "message": msg}


async def film_unload(film_name: str, frames_shot: int = None,
                      camera_name: str = None) -> dict:
    """
    记录退卷事件。

    查找该胶卷最新的"在机内"记录，标记为已退卷。
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    # 查胶卷
    film = await _find_entity("film", film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存"}

    # 查最新的"在机内" loading
    loadings = await query_entities(
        user_id,
        entity_type="film_loading",
        filters={"film_id": film["id"], "status": "在机内"},
        limit=10,
    )

    # 如果指定了相机，过滤
    target_loading = None
    if camera_name:
        camera = await _find_entity("gear", camera_name)
        if camera:
            target_loading = next(
                (l for l in loadings if (l.get("data") or {}).get("camera_id") == camera["id"]),
                None
            )
    if not target_loading and loadings:
        target_loading = loadings[0]
    if not target_loading:
        return {"status": "error", "message": f"「{film_name}」不在任何相机内"}

    # 更新 loading 状态
    loading_data = target_loading.get("data") or {}
    loading_data["status"] = "已退卷"
    loading_data["unloaded_at"] = datetime.now().isoformat()
    if frames_shot is not None:
        existing_shot = loading_data.get("frames_shot", 0)
        loading_data["frames_shot"] = (existing_shot or 0) + frames_shot

    await save_entity(
        user_id=user_id,
        entity_type="film_loading",
        name=target_loading["name"],
        data=loading_data,
        entity_id=target_loading["id"],
    )

    # 更新胶卷状态
    film_data = film.get("data") or {}
    film_data["status"] = "已退卷"
    await save_entity(
        user_id=user_id,
        entity_type="film",
        name=film["name"],
        data=film_data,
        entity_id=film["id"],
    )

    cam_info = f"从 {loading_data.get('camera_name', '?')} " if loading_data.get("camera_name") else ""
    msg = f"已退卷：{film['name']}{cam_info}"
    if frames_shot:
        msg += f"（本次拍了 {frames_shot} 张）"

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="film_loading", entity_id=target_loading["id"],
        sql_text=f"Updated loading to unloaded + updated film status",
        sql_params={"frames_shot": frames_shot},
        rows_affected=2, tool_name="film_unload",
        tool_args={"film_name": film_name, "frames_shot": frames_shot},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {"status": "ok", "message": msg}


async def film_finish(film_name: str, frames_shot: int = None) -> dict:
    """
    标记胶卷已拍完。

    自动扣减库存数量（quantity - 1），当库存为 0 时标记为"已使用"。
    """
    start = time.time()
    user_id = _current_context["user_id"]
    sid = _current_context["session_id"]
    mid = _current_context["message_id"]

    film = await _find_entity("film", film_name)
    if not film:
        return {"status": "error", "message": f"没找到「{film_name}」的库存"}

    # 查最新"在机内" loading
    loadings = await query_entities(
        user_id,
        entity_type="film_loading",
        filters={"film_id": film["id"], "status": "在机内"},
        limit=5,
    )
    if not loadings:
        return {"status": "error", "message": f"「{film_name}」不在机内，请先装卷"}

    target = loadings[0]

    # 更新 loading → 已拍完
    loading_data = target.get("data") or {}
    loading_data["status"] = "已拍完"
    loading_data["unloaded_at"] = datetime.now().isoformat()
    if frames_shot is not None:
        existing_shot = loading_data.get("frames_shot", 0)
        loading_data["frames_shot"] = (existing_shot or 0) + frames_shot

    await save_entity(
        user_id=user_id,
        entity_type="film_loading",
        name=target["name"],
        data=loading_data,
        entity_id=target["id"],
    )

    # 扣库存
    film_data = film.get("data") or {}
    current_qty = film_data.get("quantity", 0)
    if isinstance(current_qty, str):
        try:
            current_qty = int(current_qty)
        except (ValueError, TypeError):
            current_qty = 0
    current_qty = max(0, current_qty - 1)
    film_data["quantity"] = current_qty
    film_data["status"] = "已使用" if current_qty <= 0 else film_data.get("status", "未使用")

    await save_entity(
        user_id=user_id,
        entity_type="film",
        name=film["name"],
        data=film_data,
        entity_id=film["id"],
    )

    # 统计此卷累计张数
    all_loadings = await query_entities(
        user_id,
        entity_type="film_loading",
        filters={"film_id": film["id"]},
        limit=100,
    )
    total_frames = sum(
        (l.get("data") or {}).get("frames_shot", 0) or 0
        for l in all_loadings
    )

    cam_name = loading_data.get("camera_name", "?")
    msg = (
        f"🎉 {film['name']}（{cam_name}）已拍完！"
        f"累计拍了 {total_frames} 张，库存剩余 {current_qty} 卷"
    )

    await record_audit(
        user_id=user_id, session_id=sid, message_id=mid,
        operation="UPDATE", entity_type="film_loading", entity_id=target["id"],
        sql_text=f"Finished film, reduced stock",
        sql_params={"qty_before": current_qty + 1, "qty_after": current_qty},
        rows_affected=2, tool_name="film_finish",
        tool_args={"film_name": film_name},
        duration_ms=int((time.time() - start) * 1000),
    )

    return {
        "status": "ok",
        "message": msg,
        "summary": {
            "total_frames": total_frames,
            "remaining_stock": current_qty,
        },
    }


async def film_loading_query(status: str = "在机内", camera_name: str = None,
                              limit: int = 20) -> dict:
    """查询装卷状态"""
    user_id = _current_context["user_id"]

    filters = {"status": status}
    if camera_name:
        filters["camera_name"] = camera_name

    results = await query_entities(
        user_id,
        entity_type="film_loading",
        filters=filters,
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "loadings": results,
        "message": f"找到 {len(results)} 条装卷记录",
    }


async def shoot_search(query: str, limit: int = 10) -> dict:
    """全文搜索拍摄记录"""
    user_id = _current_context["user_id"]

    results = await search_entities(
        user_id=user_id,
        query_text=query,
        entity_type="shoot",
        limit=limit,
    )

    return {
        "status": "ok",
        "count": len(results),
        "results": results,
        "message": f"找到 {len(results)} 条相关记录",
    }
