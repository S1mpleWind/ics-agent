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
    compact_after_messages: int = 12
    compact_recent_messages: int = 4
    compact_summary_limit: int = 12000
    tool_result_limit: int = 1200
    # Add a token estimation threshold for aggressive compaction
    estimated_token_limit: int = 6500


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
        loader = MemoryLoader.current()
        if loader is not None:
            loader.reload()
            self.memory_docs = loader.descriptions()

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

        # TODO: compress happens here, use user or assistant?
        # compress according to total message count (including assistant/tool messages).
        # Note: repair prompts are also 'user' role; counting raw message count avoids
        # misclassifying internal repair prompts as additional user rounds.
        # Determine if we should compact based on message count OR token estimation
        def estimate_tokens(msgs: list[Message]) -> int:
            return sum(len(str(m.get("content", ""))) // 4 for m in msgs)

        num_msgs = len(messages)
        est_tokens = estimate_tokens(messages)

        should_compact = (
            num_msgs > self.config.compact_after_messages or 
            est_tokens > self.config.estimated_token_limit
        )

        if not should_compact:
            # Continue normally
            pass
        else:
            messages = self.micro_compact_tool_history(messages)

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

                #TODO reload memory after writing mem? no need to 
                raw_tool_result = self.tools.run(tool_name, tool_arguments)

                # if tool_name == "save_memory":
                #     self.memory_docs=MemoryLoader.reload()

                # Record memory-specific events from raw JSON before truncation.
                self._record_memory_trace(step, tool_name, raw_tool_result)

                tool_result = raw_tool_result

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
            
            # this will never happen
            fallback = "The assistant produced an unsupported protocol message."
            self.trace.add(step, "final", agent=self.name, content=fallback)
            return fallback

        fallback = "Agent stopped after reaching the maximum number of steps."
        self.trace.add(self.config.max_steps, "final", agent=self.name, content=fallback)
        return fallback

    def _record_memory_trace(self, step: int, tool_name: str, tool_result: str) -> None:
        """Emit memory trace events without bloating trace payload size.

        Memory evals expect explicit read/write events. We only record minimal
        metadata (key and success) and avoid writing full memory body content.
        """
        if tool_name not in {"read_memory", "save_memory"}:
            return

        payload = self._parse_tool_json(tool_result)
        if not isinstance(payload, dict):
            return
        if payload.get("ok") is not True:
            return

        key = payload.get("key")
        if not isinstance(key, str) or not key.strip():
            return

        event = "memory_retrieve" if tool_name == "read_memory" else "memory_write"
        self.trace.add(step, event, agent=self.name, key=key)

    def _parse_tool_json(self, text: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        return payload
    
    def micro_compact_tool_history(self, messages: list[Message]) -> list[Message]:
        """Tier 1: Ultra-fast local truncation of large tool results.
        Only keeps the last 2 tool results fully intact, truncates others to 500 chars.
        """
        if len(messages) < 6:
            return messages
            
        new_msgs = [messages[0]] # Keep system prompt
        tool_count = 0
        
        # Reverse iterate to find the most recent tool results
        for msg in reversed(messages[1:]):
            content = msg.get("content", "")
            if "Tool `" in content and "returned this JSON result:" in content:
                tool_count += 1
                if tool_count > 5 and len(content) > 150:
                    # Truncate old large results
                    msg = msg.copy()
                    msg["content"] = content[:150] + "... [TRUNCATED BY TIER-1]"
            new_msgs.insert(1, msg)
            # this is old msg
            
        return self.compact_context(new_msgs)

    def compact_context(self, messages: list[Message]) -> list[Message]:
        """Compact old messages into a short summary and keep recent messages.

        Returns a new messages list where messages earlier than the last
        `compact_recent_messages` are replaced by a single `system` summary
        message. Records a `context_compacted` trace event.
        """
        # Determine how many recent messages to keep (preserve roles and order)
        keep = max(0, int(self.config.compact_recent_messages))

        if len(messages) <= 1 + keep:
            # only system prompt + recent messages present, nothing to compact
            return messages

        # Keep the original system prompt at index 0
        system_msg = messages[0]

        recent_msgs = messages[-keep:] if keep > 0 else []
        old_msgs = messages[1 : len(messages) - keep] if keep > 0 else messages[1:]

        # Build a single text block from old messages for summarization
        def render(msg: Message) -> str:
            role = msg.get("role", "")
            content = msg.get("content", "")
            return f"[{role}] {content}"

        old_text = "\n\n".join(render(m) for m in old_msgs)
        if not old_text.strip():
            # no need to 
            return messages
        


        recent_text = "\n\n".join(render(m) for m in recent_msgs)
        if not recent_text.strip():
            #TODO should raise error here
            return messages
        


        # Prompt the LLM to produce a compact summary. Use a messages list so the
        # transport receives structured role/content data (compatible with LLMTransport).
        instruct = (
            "You are a conversation compaction assistant. Compress the provided OLD "
            "conversation history into a short, factual bulleted summary.\n\n"
            "CRITICAL RULES:\n"
            "1) DO NOT summarize the RECENT conversation. It is provided only for context.\n"
            "2) DO NOT add any new facts, reasoning, or responses — only extract explicit facts.\n"
            "3) Focus on outstanding tasks, key results (tool outputs, IDs, file paths), and user preferences.\n"
            "4) Format: concise bulleted list.\n"
            f"5) Length constraint: aim to keep under {self.config.compact_summary_limit} characters.\n\n"
        )

        summary_messages = [
            {"role": "system", "content": instruct},
            {
                "role": "user",
                "content": (
                    "OLD HISTORY TO COMPRESS:\n" + old_text + "\n\n"
                    "RECENT HISTORY (for context only - DO NOT SUMMARIZE):\n" + recent_text
                ),
            },
        ]

        # # Tier 3: Persistent Memory update (Side-effect during Tier 2 compaction)
        # # We peek at the old history to see if there are user preferences to save
        # if "user_preferred_name" in old_text or "prefers" in old_text.lower():
        #     self.tools.run("save_memory", {"key": "session_context", "content": "Compaction triggered. Archiving key facts."})

        try:
            summary = self.llm.complete(summary_messages) or ""
        except Exception as exc:  # best-effort: don't break the main loop
            summary = f"(failed to summarize context: {exc})"

        # Truncate summary if too long
        if len(summary) > self.config.compact_summary_limit:
            summary = summary[: self.config.compact_summary_limit] + "..."

        # Build new messages: keep original system prompt, add summary as system,
        # then append recent messages
        summary_msg = {
            "role": "system",
            "content": "[COMPRESSED HISTORY]\n" + summary,
        }

        new_messages: list[Message] = [system_msg, summary_msg] + recent_msgs

        # Record trace event
        self.trace.add(
            0,
            "context_compacted",
            agent=self.name,
            kept_recent=len(recent_msgs),
            original_messages=len(messages) - 1,
            summary_length=len(summary),
            summary_preview=(summary[:200] + "...") if len(summary) > 200 else summary,
        )

        return new_messages