from __future__ import annotations
from typing import Any
import json
from ics_agent_lab.tools.base import Tool, Workspace
from assignments.patch_review.service import read_diff

def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        diff_text = read_diff()
        return json_result(ok=True, diff=diff_text)

    return Tool(
        name="read_diff",
        description="Reads the diff of the patch under review. Call this tool first to understand the proposed changes.",
        schema={
            "type": "object",
            "properties": {},
        },
        handler=handler,
    )
