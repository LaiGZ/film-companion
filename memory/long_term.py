"""
长期记忆管理 — 跨会话提取值得记住的用户信息
"""

import asyncio
import json
import os

import yaml
from db.schema import (
    add_memory as db_add_memory,
    get_active_memories as db_get_active_memories,
    find_similar_memory as db_find_similar,
    refresh_memory as db_refresh_memory,
)


def _is_long_term_enabled() -> bool:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return data.get("memory", {}).get("enable_long_term", True)
    return True


async def extract_memories(user_id: str, session_messages: list,
                           llm_provider=None):
    """会话结束时，从对话中提取值得长期记住的信息

    调用 LLM 分析整段对话，提取偏好、习惯、稳定事实。
    """
    if not _is_long_term_enabled():
        return []

    if not llm_provider:
        return []

    # 将消息转为文本
    dialog_text = "\n".join([
        f"{m.get('role', 'unknown')}: {m.get('content', '')}"
        for m in session_messages
        if m.get('role') in ('user', 'assistant')
    ])

    prompt = f"""从以下对话中提取值得长期记住的信息。

规则：
1. 只提取稳定的事实和明确的偏好（"我喜欢…"、"我更喜欢…"、"我习惯…"）
2. 忽略临时话题、一次性操作（如"帮我查一下"）
3. 只提取对后续对话有帮助的信息
4. 如果没有值得记住的信息，返回空数组

返回 JSON 格式的数组，每个元素：
{{"memory_type": "preference/fact/pattern", "category": "film/gear/shooting/general", "content": "记忆内容", "tags": ["标签1", "标签2"]}}

对话内容：
{dialog_text}
"""

    try:
        response = await llm_provider.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一个记忆提取助手。只返回 JSON 数组，不要其他文字。"
        )

        if not response.content:
            return []

        # 解析 JSON
        try:
            memories = json.loads(response.content)
        except json.JSONDecodeError:
            # 尝试从 markdown code block 中提取
            import re
            match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', response.content)
            if match:
                memories = json.loads(match.group(1))
            else:
                return []

        saved = []
        for mem in memories:
            if not isinstance(mem, dict) or not mem.get("content"):
                continue

            # 检查是否已存在相似记忆
            existing = await db_find_similar(user_id, mem["content"])
            if existing:
                await db_refresh_memory(existing["id"])
                saved.append({"id": existing["id"], "action": "refreshed"})
            else:
                mid = await db_add_memory(
                    user_id=user_id,
                    memory_type=mem.get("memory_type", "fact"),
                    category=mem.get("category", "general"),
                    content=mem["content"],
                    tags=mem.get("tags", []),
                    source="session_extraction",
                )
                saved.append({"id": mid, "action": "created"})

        return saved

    except Exception as e:
        print(f"  提取记忆时出错: {e}")
        return []


async def load_memories_for_session(user_id: str, limit: int = 10) -> str:
    """加载长期记忆，格式化为 System Prompt 文本"""
    if not _is_long_term_enabled():
        return ""

    memories = await db_get_active_memories(user_id, limit)
    if not memories:
        return ""

    lines = ["\n## 关于你的长期记忆"]
    for mem in memories:
        tag_str = f" [{', '.join(mem.get('tags', []))}]" if mem.get('tags') else ""
        lines.append(f"- {mem['content']}{tag_str}")

    return "\n".join(lines)


async def add_user_preference(user_id: str, content: str,
                              category: str = "general",
                              tags: list = None) -> str:
    """手动添加一条用户偏好记忆"""
    existing = await db_find_similar(user_id, content)
    if existing:
        await db_refresh_memory(existing["id"])
        return existing["id"]

    mid = await db_add_memory(
        user_id=user_id,
        memory_type="preference",
        category=category,
        content=content,
        tags=tags,
        source="manual",
    )
    return mid
