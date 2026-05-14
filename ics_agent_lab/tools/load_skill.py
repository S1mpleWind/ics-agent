from __future__ import annotations

from typing import Any

from ..skills import SkillLoader
from .base import Tool, json_result


def make_tool(skill_loader: SkillLoader | None) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        if skill_loader is None:
            return json_result(ok=False, error="Skill loader is not configured.")

        name = arguments.get("name", "").strip()
        if not name:
            return json_result(ok=False, error="`name` must be a non-empty string.")

        try:
            content = skill_loader.content(name)
        except Exception as exc:
            return json_result(ok=False, error=str(exc))

        return json_result(ok=True, name=name, content=content)

    return Tool(
        name="load_skill",
        description="Load the full body of a named skill from skills/<name>/SKILL.md.",
        schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
        handler=handler,
    )
