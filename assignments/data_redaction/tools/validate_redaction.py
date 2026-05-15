from __future__ import annotations

from typing import Any

from ics_agent_lab.tools.base import Tool, Workspace
import json
def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

from assignments.data_redaction.service import validate_redaction

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        content = arguments.get("content")
        if not content:
            return json_result(ok=False, error="No valid content is received")
            
        checklist = validate_redaction(content)
        if checklist is None:
            return json_result(ok=False, error=f"No checklist received.")
        # 返回校验项列表（空列表表示通过）
        return json_result(ok=True, checklist=checklist)

    return Tool(
        name="validate_redaction",
        description="Validate a candidate redacted ticket. Returns a checklist of issues (empty list = pass).",
        schema={
            "type": "object",
            "required": ["content"],
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The candidate redacted ticket text to validate."
                }
            },
        },
        handler=handler,
    )
