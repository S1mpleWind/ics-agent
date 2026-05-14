from __future__ import annotations

from typing import Any

from .base import Tool, Workspace, json_result


def make_tool(workspace: Workspace) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "")
        content = arguments.get("content", "")

        target = workspace.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return json_result(ok=True, path=str(target.relative_to(workspace.resolved_root)))

    return Tool(
        name="write_file",
        description="Write a UTF-8 text file inside the lab workspace.",
        schema={
            "type": "object",
            "required": ["path", "content"],
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
        },
        handler=handler,
    )
