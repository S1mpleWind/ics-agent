from __future__ import annotations
from typing import Any
import json
from ics_agent_lab.tools.base import Tool, Workspace
from assignments.patch_review.service import read_patch_file

def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        path = arguments.get("path")
        if not path:
            return json_result(ok=False, error="path is required")
        
        content = read_patch_file(path)
        if content is None:
            return json_result(ok=False, error=f"File {path} not found in patch fixture.")
        
        return json_result(ok=True, content=content)

    return Tool(
        name="read_patch_file",
        description="Reads a specific file from the patch fixture to get more context around the diff.",
        schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string", "description": "The file path to read (e.g. from the diff header)."}
            },
        },
        handler=handler,
    )
