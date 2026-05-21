"""
FastAPI Web 服务 — 聊天 API + 数据查看 API + SSE 流式聊天
"""

import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================
# 请求/响应模型
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    images: list[str] = []  # base64 data URI 列表，如 ["data:image/jpeg;base64,..."]


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    tool_calls: list = []


# ============================================================
# 全局状态（延迟初始化，启动后由 main.py 注入）
# ============================================================

class AppState:
    def __init__(self):
        self.llm_provider = None
        self.plugin_registry = None
        self.session_id = None
        self.turn_index = 0
        self.user_count = 0


state = AppState()


def init_web_app(provider, registry):
    """由 main.py 调用，注入 LLM provider 和插件注册表"""
    state.llm_provider = provider
    state.plugin_registry = registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    from db.pool import init_pool
    await init_pool()
    print("✅ Web 服务: 数据库连接池已就绪")
    yield
    from db.pool import close_pool
    await close_pool()
    print("👋 Web 服务: 已关闭")


app = FastAPI(
    title="胶片伴侣 AI API",
    version="0.2.0",
    lifespan=lifespan,
)

# 挂载静态文件
web_dir = os.path.join(os.path.dirname(__file__))
dist_dir = os.path.join(os.path.dirname(__file__), "dist")
# 优先使用 dist 目录（Vue 构建产物）
static_dir = dist_dir if os.path.exists(dist_dir) else web_dir
if os.path.exists(dist_dir):
    print(f"📦 前端: Vite 构建产物 (dist)")
else:
    print(f"📦 前端: 开发模式 (静态文件)")
app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

# 上传文件存储
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# 注册认证路由
from web.auth import router as auth_router, get_current_user
app.include_router(auth_router)


# ============================================================
# 页面路由
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def chat_page():
    """聊天页面"""
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        with open(html_path, encoding="utf-8") as f:
            return f.read()
    # 降级到旧版 chat.html
    legacy = os.path.join(web_dir, "chat.html")
    if os.path.exists(legacy):
        with open(legacy, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>页面未找到</h1>", status_code=404)


@app.get("/data", response_class=HTMLResponse)
async def data_page():
    """数据查看页面 — Vue Router hash 模式，重定向到 /"""
    # hash 模式下 /data 由前端路由处理
    return await chat_page()


# ============================================================
# 辅助：构建 system prompt
# ============================================================

async def _build_system_prompt(user_id: str) -> str:
    """构建当前会话的 system prompt"""
    from memory.long_term import load_memories_for_session
    memories_text = await load_memories_for_session(user_id)

    available_tools = json.dumps(
        state.plugin_registry.get_tool_descriptions(),
        indent=2, ensure_ascii=False
    )

    return f"""你是"胶片伴侣 AI"，一个对话式胶片摄影管理助手。

## 你的能力
你可以帮助用户管理胶卷库存、摄影器材。所有操作通过自然语言完成。

### 胶卷管理
- 记录新买的胶卷（型号、数量、ISO、类型、购买地点等）
- 查询库存（按类型、ISO、状态等筛选）
- 修改/补充胶卷信息
- 删除胶卷记录（需用户确认）
- 检查快过期/已过期的胶卷并提醒

### 设备管理
- 记录新买的器材（相机、镜头、三脚架等）
- 查询设备列表（按类型、品牌、状态筛选）
- 修改设备信息（状态流转：在用/闲置/待出/已出/维修中）
- 删除设备记录（需用户确认）

### 拍摄记录管理
- 创建拍摄活动（"昨天去故宫拍了" → 自动创建 shoot + 关联胶卷和设备）
- 记录装卷/退卷事件（一卷胶卷可在多台相机间切换）
- 记录胶卷拍完（自动扣库存、累计张数）
- 查询相机里有什么卷 / 哪些卷拍到一半
- 按地点/日期查询历史拍摄记录

## 操作规则
1. 用户说"买了/入了/收了 ××" → 调用 add_film 或 add_gear
2. 用户说"有哪些/查一下/看看/还有多少" → 调用 query_film 或 query_gear
3. 用户说"快过期了" → 调用 check_expiring_film
4. 用户说"改成/补充/更新" → 先查数据，再调用 update_film 或 update_gear
5. 删除操作必须确认

## 回答风格
- 简洁友好
- 查询结果用表格或列表呈现
- 胶卷快过期时主动提醒

## 可用工具
{available_tools}

{memories_text}"""


# ============================================================
# 会话管理 API
# ============================================================

@app.get("/api/sessions")
async def list_sessions(
    limit: int = Query(50),
    current_user: dict = Depends(get_current_user),
):
    """获取会话列表"""
    from db.schema import list_sessions
    sessions = await list_sessions(user_id=current_user["id"], limit=limit)
    return {"status": "ok", "sessions": sessions}


@app.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """获取单个会话详情"""
    from db.schema import get_session_by_id, get_recent_messages
    sess = await get_session_by_id(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 数据权限：只能查看自己的会话
    if sess["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权访问该会话")

    msgs = await get_recent_messages(session_id, 200)
    # 只保留 user 和 assistant 消息，供前端展示
    display_msgs = []
    for m in msgs:
        role = m["role"]
        if role in ("user", "assistant"):
            display_msgs.append({
                "role": role,
                "content": m["content"],
                "created_at": m.get("created_at", ""),
                "turn_index": m["turn_index"],
            })

    return {"status": "ok", "session": sess, "messages": display_msgs[::-1]}


@app.post("/api/sessions")
async def create_session(current_user: dict = Depends(get_current_user)):
    """创建新会话"""
    from memory.context import init_session
    session_id = await init_session(user_id=current_user["id"], platform="web")
    return {"status": "ok", "session_id": session_id}


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除会话（只能删除自己的）"""
    from db.schema import get_session_by_id
    sess = await get_session_by_id(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="会话不存在")
    if sess["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="无权删除该会话")
    from db.pool import execute
    await execute("DELETE FROM chat_message WHERE session_id = ?", session_id)
    await execute("DELETE FROM chat_session WHERE id = ?", session_id)
    return {"status": "ok", "deleted": session_id}


@app.post("/api/upload")
async def upload_image(
    file: UploadFile = File(...),
    request: Request = None,
    current_user: dict = Depends(get_current_user),
):
    """上传图片 —— 返回完整可访问 URL（Doubao API 需要 http/https）"""
    import uuid
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # 构造完整 URL（Doubao API 不支持相对路径）
    base = str(request.base_url).rstrip("/")
    url = f"{base}/uploads/{filename}"

    print(f"🖼️ 图片已上传: {filename} ({len(content)} bytes)")
    return {"status": "ok", "url": url, "filename": filename}


# ============================================================
# SSE 流式聊天 — 核心接口
# ============================================================

async def _chat_event_stream(session_id: str, user_input: str, user_id: str, images: list[str] = None):
    """SSE 事件生成器 — 处理多轮对话（含工具调用）"""
    from memory.context import record_user_message, record_assistant_message, get_context
    from memory.context import record_tool_call, record_tool_result
    from plugins.film import tools as film_tools
    from plugins.gear import tools as gear_tools

    system_prompt = await _build_system_prompt(user_id)
    context = await get_context(session_id)

    # 构建用户消息内容（支持多模态：文本 + 图片）
    user_content = user_input
    if images:
        parts = [{"type": "text", "text": user_input}]
        for img in images:
            parts.append({"type": "image_url", "image_url": {"url": img}})
        user_content = parts

    current_messages = context + [{"role": "user", "content": user_content}]

    # 记录用户消息（存储为 JSON 字符串便于还原）
    import json
    stored_content = json.dumps(user_content, ensure_ascii=False) if isinstance(user_content, list) else user_content
    state.turn_index += 1
    msg_id = await record_user_message(session_id, stored_content, state.turn_index)
    state.user_count += 1

    # 自动生成会话标题（第一条用户消息）
    from db.pool import execute as db_execute
    msg_count = await db_execute(
        "SELECT COUNT(*) AS cnt FROM chat_message WHERE session_id = ? AND role = 'user'",
        session_id
    )
    user_msg_count = msg_count[0]["cnt"] if msg_count else 0
    if user_msg_count == 1:
        title = user_input[:48] + ("..." if len(user_input) > 48 else "")
        await db_execute(
            "UPDATE chat_session SET title = ? WHERE id = ? AND (title IS NULL OR title = '')",
            title, session_id
        )

    # 设置插件上下文
    from plugins.film import tools as film_tools
    from plugins.gear import tools as gear_tools
    from plugins.shoot import tools as shoot_tools
    film_tools.set_context(
        user_id=user_id, session_id=session_id, message_id=msg_id
    )
    gear_tools.set_context(
        user_id=user_id, session_id=session_id, message_id=msg_id
    )
    shoot_tools.set_context(
        user_id=user_id, session_id=session_id, message_id=msg_id
    )

    max_rounds = 5  # 最多 5 轮工具调用
    round_num = 0
    full_reply = ""

    while round_num < max_rounds:
        round_num += 1
        round_text = ""

        # 流式调用 LLM
        async for event in state.llm_provider.chat_stream(
            messages=current_messages,
            tools=state.plugin_registry.get_tool_descriptions(),
            system_prompt=system_prompt,
        ):
            if event["type"] == "token":
                round_text += event["content"]
                yield f"data: {json.dumps({'type': 'token', 'content': event['content']}, ensure_ascii=False)}\n\n"

            elif event["type"] == "error":
                yield f"data: {json.dumps({'type': 'error', 'content': event['content']}, ensure_ascii=False)}\n\n"
                return

            elif event["type"] == "done":
                tool_calls = event.get("tool_calls", [])
                if not tool_calls:
                    # 纯文本回复，完成
                    full_reply += round_text
                    state.turn_index += 1
                    await record_assistant_message(
                        session_id, full_reply, state.turn_index
                    )
                    yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"

                    # 每 5 轮提取长期记忆（不阻塞 SSE 回复）
                    if state.user_count > 0 and state.user_count % 5 == 0:
                        from memory.long_term import extract_memories
                        from db.schema import get_recent_messages as _get_msgs
                        recent = await _get_msgs(session_id, 20)
                        asyncio.create_task(
                            extract_memories(user_id, recent, state.llm_provider)
                        )
                    return

                # 有工具调用：记录 LLM 的 tool_call
                state.turn_index += 1
                await record_tool_call(
                    session_id, json.dumps(tool_calls, ensure_ascii=False), state.turn_index
                )

                # 通知前端工具开始
                tool_names = [tc["function"]["name"] for tc in tool_calls]
                yield f"data: {json.dumps({'type': 'tool_start', 'tools': tool_names}, ensure_ascii=False)}\n\n"

                # 执行每个工具
                tool_results = []
                for tc in tool_calls:
                    tool_name = tc["function"]["name"]
                    try:
                        tool_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        tool_args = {}

                    result = await state.plugin_registry.execute_tool_async(
                        tool_name, tool_args
                    )

                    tool_results.append({
                        "tool_call_id": tc["id"],
                        "result": result,
                    })

                    yield f"data: {json.dumps({'type': 'tool_result', 'name': tool_name, 'result': str(result)[:200]}, ensure_ascii=False)}\n\n"

                # 记录工具结果
                state.turn_index += 1
                await record_tool_result(
                    session_id,
                    json.dumps(tool_results, ensure_ascii=False),
                    state.turn_index
                )

                # 获取更新后的 context，准备下一轮
                updated_context = await get_context(session_id)
                current_messages = updated_context
                full_reply += round_text
                break  # 继续 while 循环，走下一轮

    # 超轮次保护
    yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
    if not full_reply:
        full_reply = "处理完成，请继续告诉我需要什么帮助。"
    state.turn_index += 1
    await record_assistant_message(session_id, full_reply, state.turn_index)

    # 每 5 轮提取长期记忆
    if state.user_count > 0 and state.user_count % 5 == 0:
        from memory.long_term import extract_memories
        from db.schema import get_recent_messages as _get_msgs
        recent = await _get_msgs(session_id, 20)
        asyncio.create_task(
            extract_memories(state.user_id, recent, state.llm_provider)
        )


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """SSE 流式聊天 — 长连接，逐 token 推送"""
    if not state.llm_provider or not state.plugin_registry:
        raise HTTPException(status_code=503, detail="服务未就绪，请等待初始化完成")

    user_id = current_user["id"]

    # 初始化或复用会话
    session_id = request.session_id or state.session_id
    if not session_id:
        from memory.context import init_session
        session_id = await init_session(user_id=user_id, platform="web")
        state.session_id = session_id

    user_input = request.message.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息不能为空")

    return StreamingResponse(
        _chat_event_stream(session_id, user_input, user_id, images=request.images or None),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 兼容旧版 POST /api/chat（非流式）
# ============================================================

@app.post("/api/chat")
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
):
    """兼容旧版聊天 API — 非流式版本"""
    if not state.llm_provider or not state.plugin_registry:
        raise HTTPException(status_code=503, detail="服务未就绪，请等待初始化完成")

    user_id = current_user["id"]

    session_id = request.session_id or state.session_id
    if not session_id:
        from memory.context import init_session
        session_id = await init_session(user_id=user_id, platform="web")
        state.session_id = session_id

    user_input = request.message.strip()
    if not user_input:
        raise HTTPException(status_code=400, detail="消息不能为空")

    # 收集 SSE 流的结果
    full_reply = ""
    tool_names = []
    async for event in _chat_event_stream(session_id, user_input, user_id):
        if event.startswith("data: "):
            data = json.loads(event[6:])
            if data["type"] == "token":
                full_reply += data["content"]
            elif data["type"] == "tool_start":
                tool_names = data.get("tools", [])
            elif data["type"] == "done":
                break

    return ChatResponse(
        reply=full_reply,
        session_id=session_id,
        tool_calls=[{"name": n, "args": {}} for n in tool_names],
    )


# ============================================================
# 数据查询 API（保持不变）
# ============================================================

@app.get("/api/film")
async def list_film(
    film_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    iso_min: Optional[int] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("DESC"),
    limit: int = Query(100),
    current_user: dict = Depends(get_current_user),
):
    """查询胶卷列表（基于 entities 统一存储）"""
    from db.entity_store import query_entities

    user_id = current_user["id"]

    # 实体查询（精确匹配）
    filters = {}
    if status:
        filters["status"] = status
    if film_type:
        filters["type"] = film_type

    result = await query_entities(
        user_id=user_id,
        entity_type="film",
        filters=filters if filters else None,
        order_by=sort,
        order_dir=order,
        limit=limit * 2,  # 多取一些用于后过滤
    )

    # 将 data JSON 展平为前端可读的 flat 格式
    flat_results = []
    from datetime import datetime
    today = datetime.now().date()
    for e in result:
        d = e.get("data") or {}
        if iso_min and (d.get("iso") is None or d.get("iso") < iso_min):
            continue
        flat = {
            "id": e["id"],
            "name": e["name"],
            "film_type": d.get("type"),
            "iso": d.get("iso"),
            "format": d.get("format"),
            "quantity": d.get("quantity", 1),
            "status": d.get("status", "未使用"),
            "price": d.get("purchase", {}).get("price") if isinstance(d.get("purchase"), dict) else d.get("price"),
            "purchase_date": d.get("purchase", {}).get("date") if isinstance(d.get("purchase"), dict) else None,
            "expiry_date": d.get("expiry"),
            "storage_location": d.get("storage"),
            "created_at": e["created_at"],
            "updated_at": e["updated_at"],
        }
        # 过期状态
        if flat.get("expiry_date"):
            try:
                exp = datetime.fromisoformat(str(flat["expiry_date"])[:10]).date()
                days = (exp - today).days
                flat["expiry_status"] = "expired" if days < 0 else "expiring" if days <= 30 else "ok"
                flat["days_left"] = days
            except (ValueError, TypeError):
                flat["expiry_status"] = "unknown"
        else:
            flat["expiry_status"] = "unknown"

        flat_results.append(flat)

    return {"status": "ok", "count": len(flat_results), "films": flat_results[:limit]}


@app.get("/api/gear")
async def list_gear(
    gear_type: Optional[str] = Query(None),
    brand: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    order: str = Query("DESC"),
    limit: int = Query(100),
    current_user: dict = Depends(get_current_user),
):
    """查询设备列表（基于 entities 统一存储）"""
    from db.entity_store import query_entities

    user_id = current_user["id"]

    filters = {}
    if gear_type:
        filters["gear_type"] = gear_type
    if brand:
        filters["brand"] = brand
    if status:
        filters["status"] = status

    result = await query_entities(
        user_id=user_id,
        entity_type="gear",
        filters=filters if filters else None,
        order_by=sort,
        order_dir=order,
        limit=limit,
    )

    # 将 data JSON 展平
    flat_results = []
    for e in result:
        d = e.get("data") or {}
        flat = {
            "id": e["id"],
            "name": e["name"],
            "gear_type": d.get("gear_type"),
            "brand": d.get("brand"),
            "model": d.get("model"),
            "nickname": d.get("nickname"),
            "category": d.get("category"),
            "condition": d.get("condition"),
            "status": d.get("status", "在用"),
            "price": d.get("purchase", {}).get("price") if isinstance(d.get("purchase"), dict) else d.get("price"),
            "purchase_date": d.get("purchase", {}).get("date") if isinstance(d.get("purchase"), dict) else None,
            "storage_location": d.get("storage"),
            "serial_number": d.get("serial_number"),
            "lens_mount": d.get("lens_mount"),
            "camera_type": d.get("camera_type"),
            "format_support": d.get("format_support"),
            "created_at": e["created_at"],
            "updated_at": e["updated_at"],
        }
        flat_results.append(flat)

    return {"status": "ok", "count": len(flat_results), "gear": flat_results[:limit]}


@app.get("/api/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """获取统计数据（基于 entities 统一存储）"""
    from db.entity_store import get_stats as entity_stats

    user_id = current_user["id"]
    stats = await entity_stats(user_id)

    film = stats.get("film", {})
    gear = stats.get("gear", {})

    return {
        "status": "ok",
        "stats": {
            "film_count": film.get("count", 0),
            "gear_count": gear.get("count", 0),
            "total_film_price": film.get("total_price", 0),
            "total_gear_price": gear.get("total_price", 0),
            "total_value": film.get("total_price", 0) + gear.get("total_price", 0),
            "film_types": film.get("statuses", {}),
            "gear_types": {},
            "film_statuses": film.get("statuses", {}),
            "expired_count": film.get("expired", 0),
            "expiring_count": 0,
        }
    }
