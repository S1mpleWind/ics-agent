from __future__ import annotations
from typing import Any
import json
from ics_agent_lab.tools.base import Tool, Workspace
from assignments.patch_review.service import submit_review

def json_result(**kwargs: Any) -> str:
    return json.dumps(kwargs)

def make_tool(workspace: Workspace) -> Tool:
    def handler(arguments: dict[str, Any]) -> str:
        verdict = arguments.get("verdict")
        comments = arguments.get("comments")
        if not verdict or not comments:
            return json_result(ok=False, error="verdict and comments are required")
            
        result = submit_review(verdict, comments)
        
        if result == "REVIEW SUBMITTED":
            try:
                target = workspace.resolve("review.txt")
                target.write_text(f"Verdict: {verdict}\n\nComments:\n{comments}", encoding="utf-8")
            except ValueError as exc:
                return json_result(ok=False, error=str(exc))
            
        return json_result(ok=True, result=result, receipt="review.txt")

    return Tool(
        name="submit_review",
        description="Submits the final patch review with a verdict and detailed comments. Writes the review to review.txt on success.",
        schema={
            "type": "object",
            "required": ["verdict", "comments"],
            "properties": {
                "verdict": {
                    "type": "string", 
                    "description": "The review verdict, e.g., 'request_changes', 'approve'."
                },
                "comments": {
                    "type": "string", 
                    "description": "Detailed review comments explaining risks, suggesting fixes, and requesting regression tests."
                }
            },
        },
        handler=handler,
    )
