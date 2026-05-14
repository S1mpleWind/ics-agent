from __future__ import annotations

from typing import Any

from .base import Tool, Workspace, json_result


def make_tool(workspace: Workspace) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        path = arguments.get("path", "")
        target = workspace.resolve(path)

        if not target.exists():
            return json_result(ok=False, error=f"Path not found: {path}")

        root = workspace.resolved_root
        files: list[str] = []
        if target.is_file():
            files.append(target.relative_to(root).as_posix())
        else:
            # Stable order keeps tool output deterministic for evals.
            for child in sorted(target.rglob("*")):
                if child.is_file():
                    files.append(child.relative_to(root).as_posix())

        return json_result(ok=True, path=target.relative_to(root).as_posix(), files=files)

    return Tool(
        name="list_files",
        description="List files inside the lab workspace.",
        schema={
            "type": "object",
            "required": ["path"],
            "properties": {"path": {"type": "string"}},
        },
        handler=handler,
    )
