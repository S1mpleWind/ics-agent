from __future__ import annotations

from typing import Any

from .base import Tool, Workspace, json_result


def make_tool(workspace: Workspace) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "")
        limit = arguments.get("limit")

        target = workspace.resolve(path)
        if not target.exists() or not target.is_file():
            return json_result(ok=False, error=f"File not found: {path}")

        content = target.read_text(encoding="utf-8")
        truncated = False

        # Line-based limit keeps response compact but predictable for the model.
        if isinstance(limit, int) and limit >= 0:
            lines = content.splitlines()
            if len(lines) > limit:
                content = "\n".join(lines[:limit])
                truncated = True

        return json_result(
            ok=True,
            path=str(target.relative_to(workspace.resolved_root)),
            content=content,
            truncated=truncated,
        )

    return Tool(
        name="read_file",
        description="Read a UTF-8 text file inside the lab workspace.",
        schema={
            "type": "object",
            "required": ["path"],
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
        handler=handler,
    )
