from __future__ import annotations

from typing import Any

from ics_agent_lab.tools.base import Tool, Workspace
import json
def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

from assignments.data_redaction.service import submit_redacted_ticket

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        ticket_id = arguments.get("ticket_id")
        content = arguments.get("content")
        if not ticket_id:
            return json_result(ok=False, error="ticket_id is required")
        if not content:
            return json_result(ok=False, error="content is required")

        result = submit_redacted_ticket(ticket_id, content)
        # service returns 'REDACTION ACCEPTED' on success
        if result != "REDACTION ACCEPTED":
            return json_result(ok=False, error=f"Submission failed: {result}")

        # 写入评测 workspace 中的最终文件
        try:
            target = workspace.resolve("redacted_ticket.txt")
            target.write_text(content, encoding="utf-8")
        except ValueError as exc:
            return json_result(ok=False, error=str(exc))

        return json_result(ok=True, result=result, receipt="redacted_ticket.txt")

    return Tool(
        name="submit_redacted_ticket",
        description="Submit a redacted ticket. Writes `redacted_ticket.txt` on success.",
        schema={
            "type": "object",
            "required": ["ticket_id", "content"],
            "properties": {
                "ticket_id": {"type": "string"},
                "content": {"type": "string"},
            },
        },
        handler=handler,
    )
