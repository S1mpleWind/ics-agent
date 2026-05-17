from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class ParsedMessage:
    kind: Literal["tool_call", "final"]
    name: str | None = None
    arguments: dict[str, Any] | None = None
    content: str | None = None


@dataclass(frozen=True)
class ParseError:
    raw: str
    reason: str


class ManualJsonProtocol:

    def build_system_prompt(
        self,
        tool_docs: str,
        skill_docs: str = "(none)",
        memory_docs: str = "(none)",
    ) -> str:
        return (
            "You are a helpful assistant.\n"
            "Respond with exactly one JSON object only, ensure nothing outside JSON.\n"
            "\n"
            "2 Allowed response template:\n"
            '{"type":"tool_call","name":"tool_name","arguments":{k:v}}\n'
            '{"type":"final","content":"final answer for the user"}\n'
            "\n"
            "Rules:\n"
            "- Carefully choose Tool name from tool docs and Use tool_call when you need a tool.\n"
            "- Tool arguments must be a JSON object.\n"
            "- Use final only when you are done.\n"
            "- If the user asks for a task-specific workflow, consult the skill docs first and VERY STRICTLY follow its instruction.\n"
            "- If a long-lived fact is needed, consult the memory docs and use memory tools as needed.\n"
            "\n"
            "Available tools:\n"
            f"{tool_docs}\n"
            "\n"
            "Available skills:\n"
            f"{skill_docs}\n"
            "\n"
            "Available memories:\n"
            f"{memory_docs}"
        )

    def parse(self, text: str) -> ParsedMessage | ParseError:
        raw = text.strip()
        if not raw:
            return ParseError(raw=text, reason="Empty assistant response.")
        
        #* tolerate some cases
        # TODO: are there more efficient ways?
        # the form of "```json{}```"
        if raw.startswith("```"):
            fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", raw, re.DOTALL)
            if fenced:
                raw = fenced.group(1).strip()
        
        # pair the brackets
        candidate_texts = [raw]
        if raw and not raw.startswith("{"):
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate_texts.append(raw[start : end + 1].strip())

        last_error = "Invalid JSON response."
        for candidate in candidate_texts:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError as exc:
                last_error = f"Invalid JSON: {exc.msg}."
                continue

            if not isinstance(payload, dict):
                last_error = "Top-level JSON value must be an object."
                continue
            
            # go in the right way
            kind = payload.get("type")
            if kind == "tool_call":
                name = payload.get("name")
                arguments = payload.get("arguments")
                if not isinstance(name, str) or not name.strip():
                    return ParseError(raw=text, reason="tool_call is missing a valid string `name`.")
                if not isinstance(arguments, dict):
                    return ParseError(raw=text, reason="tool_call `arguments` must be a JSON object.")
                return ParsedMessage(kind="tool_call", name=name, arguments=arguments)
            
            if kind == "final":
                content = payload.get("content")
                if not isinstance(content, str):
                    return ParseError(raw=text, reason="final `content` must be a string.")
                return ParsedMessage(kind="final", content=content)

            last_error = "JSON object must have `type` equal to `tool_call` or `final`."

        return ParseError(raw=text, reason=last_error)

    def repair_prompt(self, bad_text: str, reason: str) -> str:
        return (
            "Your previous response was invalid for the JSON protocol.\n"
            f"Reason: {reason}\n\n"
            "Repair it now. Output exactly one JSON object and no Markdown.\n"
            f"Previous response:\n{bad_text}"
        )
