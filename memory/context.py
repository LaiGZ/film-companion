"""
短期上下文管理 — 当前会话的滑动窗口 + 自动摘要
"""

import asyncio
import json
import os

import yaml

from db.schema import (
    add_message,
    get_recent_messages,
    count_session_messages,
    update_session_activity,
    create_session,
)


# 加载配置
def _get_max_rounds() -> int:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data.get("memory", {}).get("short_term_max_rounds", 20)
    return 20


MAX_ROUNDS = _get_max_rounds()


async def init_session(user_id: str = "default", platform: str = "cli") -> str:
    """初始化新会话，返回 session_id"""
    session_id = await create_session(user_id, platform)
    return session_id


async def record_user_message(session_id: str, content: str,
                              turn_index: int, meta: dict = None) -> str:
    """记录用户消息"""
    return await add_message(
        session_id=session_id,
        role="user",
        content=content,
        turn_index=turn_index,
        meta=meta,
    )


async def record_assistant_message(session_id: str, content: str,
                                   turn_index: int, meta: dict = None) -> str:
    """记录 AI 回复"""
    return await add_message(
        session_id=session_id,
        role="assistant",
        content=content,
        turn_index=turn_index,
        meta=meta,
    )


async def record_tool_call(session_id: str, content: str,
                           turn_index: int, meta: dict = None) -> str:
    """记录工具调用"""
    return await add_message(
        session_id=session_id,
        role="tool_call",
        content=content,
        turn_index=turn_index,
        meta=meta,
    )


async def record_tool_result(session_id: str, content: str,
                             turn_index: int, meta: dict = None) -> str:
    """记录工具返回结果"""
    return await add_message(
        session_id=session_id,
        role="tool_result",
        content=content,
        turn_index=turn_index,
        meta=meta,
    )


async def get_context(session_id: str) -> list:
    """获取当前会话的上下文（给 LLM 的 messages）"""
    # 更新最后活动时间
    await update_session_activity(session_id)

    # 取最近 N 轮对话（最新在前），翻转回时间顺序
    messages = await get_recent_messages(session_id, MAX_ROUNDS)
    messages.reverse()

    # 转为 LLM messages 格式
    context = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role in ("user", "assistant"):
            context.append({"role": role, "content": content})
        elif role == "tool_call":
            # tool_call 消息转为 LLM 的 assistant + function_call 消息
            try:
                tc_data = json.loads(content) if isinstance(content, str) else content
                context.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [tc_data] if isinstance(tc_data, dict) else tc_data,
                })
            except (json.JSONDecodeError, TypeError):
                context.append({"role": "assistant", "content": content})
        elif role == "tool_result":
            try:
                result_data = json.loads(content) if isinstance(content, str) else content
                if isinstance(result_data, list):
                    # 流式模式：多条工具结果存储为一个 list
                    for rd in result_data:
                        context.append({
                            "role": "tool",
                            "tool_call_id": rd.get("tool_call_id", ""),
                            "content": json.dumps(rd.get("result", rd), ensure_ascii=False),
                        })
                else:
                    # 旧模式：单条工具结果
                    context.append({
                        "role": "tool",
                        "tool_call_id": result_data.get("tool_call_id", ""),
                        "content": json.dumps(result_data.get("result", result_data), ensure_ascii=False),
                    })
            except (json.JSONDecodeError, TypeError):
                context.append({"role": "tool", "content": content})

    # 安全保障：移除末尾孤立的 tool_call（没有后续 tool 消息）
    while context and context[-1].get("role") == "assistant" and context[-1].get("tool_calls"):
        context.pop()

    return context


async def should_compress(session_id: str) -> bool:
    """判断是否需要压缩历史"""
    count = await count_session_messages(session_id)
    return count > MAX_ROUNDS * 2
