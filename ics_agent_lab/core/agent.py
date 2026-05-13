from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..llm import LLMTransport, Message
from ..memory import MemoryLoader
from ..tools import ToolRegistry
from .protocol import ManualJsonProtocol, ParseError
from .trace import TraceRecorder


@dataclass
class AgentConfig:
    max_steps: int = 100
    max_parse_repairs: int = 2
    compact_after_messages: int = 20
    compact_recent_messages: int = 4
    compact_summary_limit: int = 12000
    tool_result_limit: int = 6000


class Agent:
    def __init__(
        self,
        llm: LLMTransport,
        tools: ToolRegistry,
        *,
        config: AgentConfig | None = None,
        protocol: ManualJsonProtocol | None = None,
        trace: TraceRecorder | None = None,
        skill_docs: str = "(no skills available)",
        memory_docs: str = "(no memory available)",
        name: str = "main",
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.config = config or AgentConfig()
        self.protocol = protocol or ManualJsonProtocol()
        self.trace = trace or TraceRecorder()
        self.skill_docs = skill_docs
        self.memory_docs = memory_docs
        self.name = name

    def save_trace(self, path: Path) -> None:
        self.trace.save_jsonl(path)

    def run(self, user_input: str) -> str:
        messages = self.new_session()
        return self.run_turn(messages, user_input)

    def new_session(self) -> list[Message]:
        return [
            {
                "role": "system",
                "content": self.protocol.build_system_prompt(
                    self.tools.docs(), self.skill_docs, self.memory_docs
                ),
            }
        ]

    def run_turn(self, messages: list[Message], user_input: str) -> str:
        messages.append(
            {
                "role": "user",
                "content": user_input,
            }
        )

        parse_repairs_used = 0

        for step in range(self.config.max_steps):
            response = self.llm.complete(messages)
            self.trace.add(step, "llm_response", agent=self.name, raw=response)

            parsed_res = self.protocol.parse(response)

            # error: add info to trace
            if isinstance(parsed_res, ParseError):
                self.trace.add(
                    step,
                    "parse_error",
                    agent=self.name,
                    raw=parsed_res.raw,
                    reason=parsed_res.reason,
                )

                if parse_repairs_used >= self.config.max_parse_repairs:
                    fallback = (
                        "I could not produce a valid JSON response after several retries."
                    )
                    self.trace.add(step, "final", agent=self.name, content=fallback)
                    return fallback

                # try to repair
                parse_repairs_used += 1
                messages.append(
                    {
                        "role": "user",
                        "content": self.protocol.repair_prompt(
                            parsed_res.raw, parsed_res.reason
                        ),
                    }
                )
                continue
            
            # ParsedMessages:
            if parsed_res.kind == "tool_call":

                # run the tool
                tool_name = parsed_res.name or ""
                tool_arguments = parsed_res.arguments or {}
                tool_result = self.tools.run(tool_name, tool_arguments)

                if len(tool_result) > self.config.tool_result_limit:
                    tool_result = tool_result[: self.config.tool_result_limit] + "..."

                # add the result of tool calling
                self.trace.add(
                    step,
                    "tool_call",
                    agent=self.name,
                    name=tool_name,
                    arguments=tool_arguments,
                    result=tool_result,
                )
                
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Tool `{tool_name}` returned this JSON result:\n"
                            f"{tool_result}\n"
                            "Continue with the protocol and respond with exactly one JSON object."
                        ),
                    }
                )
                continue

            if parsed_res.kind == "final":
                final_content = parsed_res.content or ""
                self.trace.add(step, "final", agent=self.name, content=final_content)
                messages.append({"role": "assistant", "content": response})
                return final_content

            fallback = "The assistant produced an unsupported protocol message."
            self.trace.add(step, "final", agent=self.name, content=fallback)
            return fallback

        fallback = "Agent stopped after reaching the maximum number of steps."
        self.trace.add(self.config.max_steps, "final", agent=self.name, content=fallback)
        return fallback
