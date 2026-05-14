from __future__ import annotations

from typing import Any

from ..memory import MemoryLoader
from .base import Tool, json_result


def make_tool(memory_loader: MemoryLoader | None) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        if memory_loader is None:
            return json_result(ok=False, error="Memory loader is not configured.")

        key = arguments.get("key", "")
        content = arguments.get("content", "")

        try:
            saved = memory_loader.save(key, content)
        except Exception as exc:
            return json_result(ok=False, error=str(exc))

        return json_result(ok=True, key=saved.key, content=saved.content)

    return Tool(
        name="save_memory",
        description=(
            "Save or replace one persistent Markdown memory. Use this only for "
            "stable facts, user preferences, or instructions that should survive "
            "future sessions."
        ),
        schema={
            "type": "object",
            "required": ["key", "content"],
            "properties": {
                "key": {"type": "string"},
                "content": {"type": "string"},
            },
        },
        handler=handler,
    )
