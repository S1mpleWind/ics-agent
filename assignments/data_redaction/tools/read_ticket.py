from __future__ import annotations

from typing import Any

from ics_agent_lab.tools.base import Tool, Workspace
import json
def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

from assignments.data_redaction.service import read_ticket

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        ticket_id = arguments.get("ticket_id")
        if not ticket_id:
            return json_result(ok=False, error="ticket_id is required")
            
        content = read_ticket(ticket_id)
        if content is None:
            return json_result(ok=False, error=f"Ticket {ticket_id} not found.")
            
        return json_result(ok=True, content=content)

    return Tool(
        name="read_ticket",
        description="Reads the content of a raw ticket given its ID.",
        schema={
            "type": "object",
            "required": ["ticket_id"],
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": "The ID of the ticket to read."
                }
            },
        },
        handler=handler,
    )
