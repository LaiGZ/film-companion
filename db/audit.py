"""
审计日志 — 记录每条数据变更操作
"""

import json
import uuid
from datetime import datetime

from db.pool import execute


async def record_audit(
    user_id: str = "default",
    session_id: str = None,
    message_id: str = None,
    entity_link_id: str = None,
    operation: str = "INSERT",
    entity_type: str = None,
    entity_id: str = None,
    sql_text: str = None,
    sql_params: dict = None,
    data_before: dict = None,
    data_after: dict = None,
    rows_affected: int = 0,
    tool_name: str = None,
    tool_args: dict = None,
    status: str = "success",
    error_message: str = None,
    duration_ms: int = 0,
) -> str:
    """记录一条审计日志，返回 audit_id"""
    aid = str(uuid.uuid4())

    def _js(val):
        return json.dumps(val, ensure_ascii=False, default=str) if val else None

    await execute(
        """INSERT INTO data_audit_log
           (id, user_id, session_id, message_id, entity_link_id,
            operation, entity_type, entity_id,
            sql_text, sql_params,
            data_before, data_after, rows_affected,
            tool_name, tool_args,
            status, error_message, duration_ms)
           VALUES (?, ?, ?, ?, ?,
                   ?, ?, ?,
                   ?, ?,
                   ?, ?, ?,
                   ?, ?,
                   ?, ?, ?)""",
        aid,
        user_id,
        session_id,
        message_id,
        entity_link_id,
        operation,
        entity_type,
        entity_id,
        sql_text or "",
        _js(sql_params),
        _js(data_before),
        _js(data_after),
        rows_affected,
        tool_name or "",
        _js(tool_args),
        status,
        error_message,
        duration_ms,
    )
    return aid
