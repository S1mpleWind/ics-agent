from __future__ import annotations

from typing import Any

from .base import Tool, Workspace, json_result


def make_tool(workspace: Workspace) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "")
        old_text = arguments.get("old_text", "")
        new_text = arguments.get("new_text", "")

        target = workspace.resolve(path)
        if not target.exists() or not target.is_file():
            return json_result(ok=False, error=f"File not found: {path}")

        content = target.read_text(encoding="utf-8")
        index = content.find(old_text)
        if index < 0:
            return json_result(ok=False, error="`old_text` was not found in file.")

        # Replace only the first exact match to avoid unrelated edits.
        updated = content.replace(old_text, new_text, 1)
        target.write_text(updated, encoding="utf-8")
        return json_result(ok=True, path=str(target.relative_to(workspace.resolved_root)))

    return Tool(
        name="edit_file",
        description="Replace the first exact text match in a UTF-8 file inside the lab workspace.",
        schema={
            "type": "object",
            "required": ["path", "old_text", "new_text"],
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
        },
        handler=handler,
    )
