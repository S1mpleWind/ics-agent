from __future__ import annotations

from typing import Any

from ics_agent_lab.tools.base import Tool, Workspace
import json
def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

from assignments.ephemeral_dispatch.service import (
    request_dispatch_token,
    read_dispatch_notice,
    notify_user,
)

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        # 在同一个函数里连续调用，避开 200ms 的过期限制
        token = request_dispatch_token()
        notice = read_dispatch_notice(token)
        
        if not notice:
            return json_result(ok=False, error="Failed to read notice. Token might have expired.")
            
        # 写入凭证文件到评测的 workspace
        try:
            target = workspace.resolve("dispatch_receipt.txt")
            target.write_text(notice, encoding="utf-8")
        except ValueError as exc:
            return json_result(ok=False, error=str(exc))
            
        # 通知用户
        notify_res = notify_user(notice)
        
        return json_result(ok=True, receipt="dispatch_receipt.txt", notify_result=notify_res)

    return Tool(
        name="dispatch_notice_handler",
        description="Gets the ephemeral token, reads the dispatch notice, writes it to a receipt file, and notifies the user immediately to avoid token expiration.",
        schema={
            "type": "object",
            "properties": {},
        },
        handler=handler,
    )
