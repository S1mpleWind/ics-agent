from __future__ import annotations

import subprocess
from typing import Any

from .base import Tool, Workspace, json_result


def make_tool(workspace: Workspace) -> Tool:

    def handler(arguments: dict[str, Any]) -> str:
        command = arguments.get("command", "").strip()
        if not command:
            return json_result(ok=False, error="`command` must be a non-empty string.")

        # Keep the filter small but explicit: block clearly destructive patterns.
        blocked_patterns = ["rm -rf /", "shutdown", "reboot", ":(){:|:&};:"]
        lowered = command.lower()
        for pattern in blocked_patterns:
            if pattern in lowered:
                return json_result(ok=False, error=f"Blocked unsafe command pattern: {pattern}")

        try:
            completed = subprocess.run(
                command,
                shell=True,
                cwd=str(workspace.resolved_root),
                capture_output=True,
                text=True,
                timeout=12,
            )
            return json_result(
                ok=True,
                exit_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        except subprocess.TimeoutExpired as exc:
            return json_result(
                ok=False,
                error="Command timed out.",
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )

    return Tool(
        name="bash",
        description="Run a shell command in the lab workspace with timeout and basic safety checks.",
        schema={
            "type": "object",
            "required": ["command"],
            "properties": {"command": {"type": "string"}},
        },
        handler=handler,
    )
