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
    tool_history_compact_after_tool_calls: int = 6
    compact_after_messages: int = 15
    compact_recent_messages: int = 6
    compact_summary_limit: int = 12000
    tool_result_limit: int = 6000
    estimated_token_limit: int = 30000


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
        messages.append({"role": "user", "content": user_input})

        def estimate_tokens(msgs: list[Message]) -> int:
            return sum(len(str(m.get("content", ""))) // 4 for m in msgs)

        parse_repairs_used = 0
        for step in range(self.config.max_steps):
            num_msgs = len(messages)
            est_tokens = estimate_tokens(messages)

            if self._should_micro_compact(messages):
                messages = self.micro_compact_tool_history(messages, est_tokens)

            # if self._should_llm_compact(messages, num_msgs, est_tokens):
            #     messages = self.compact_context(messages, est_tokens)

            response = self.llm.complete(messages)
            self.trace.add(step, "llm_response", agent=self.name, raw=response)
            parsed_res = self.protocol.parse(response)

            if isinstance(parsed_res, ParseError):
                self.trace.add(step, "parse_error", agent=self.name, raw=parsed_res.raw, reason=parsed_res.reason)
                if parse_repairs_used >= self.config.max_parse_repairs:
                    fallback = "I could not produce a valid JSON response after several retries."
                    self.trace.add(step, "final", agent=self.name, content=fallback)
                    return fallback
                parse_repairs_used += 1
                messages.append({"role": "user", "content": self.protocol.repair_prompt(parsed_res.raw, parsed_res.reason)})
                continue
            
            if parsed_res.kind == "tool_call":
                tool_name = parsed_res.name or ""
                tool_arguments = parsed_res.arguments or {}
                raw_tool_result = self.tools.run(tool_name, tool_arguments)
                self._record_memory_trace(step, tool_name, raw_tool_result)

                tool_result = raw_tool_result
                if len(tool_result) > self.config.tool_result_limit:
                    tool_result = tool_result[: self.config.tool_result_limit] + "..."

                self.trace.add(step, "tool_call", agent=self.name, name=tool_name, arguments=tool_arguments, result=tool_result)
                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": f"Tool `{tool_name}` returned this JSON result:\n{tool_result}\nContinue with the protocol."
                })
                continue

            if parsed_res.kind == "final":
                final_content = parsed_res.content or ""
                self.trace.add(step, "final", agent=self.name, content=final_content)
                messages.append({"role": "assistant", "content": response})
                return final_content
            
            fallback = "Unsupported protocol message."
            self.trace.add(step, "final", agent=self.name, content=fallback)
            return fallback

        fallback = "Agent stopped after reaching maximum steps."
        self.trace.add(self.config.max_steps, "final", agent=self.name, content=fallback)
        return fallback

    def _record_memory_trace(self, step: int, tool_name: str, tool_result: str) -> None:
        if tool_name not in {"read_memory", "save_memory"}: return
        payload = self._parse_tool_json(tool_result)
        if not isinstance(payload, dict) or payload.get("ok") is not True: return
        key = payload.get("key")
        if not isinstance(key, str) or not key.strip(): return
        event = "memory_retrieve" if tool_name == "read_memory" else "memory_write"
        self.trace.add(step, event, agent=self.name, key=key)

    def _parse_tool_json(self, text: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else None
        except: return None
    
    def micro_compact_tool_history(self, messages: list[Message], estimate: int) -> list[Message]:
        """Tier 1: Intelligent local truncation using Tool Registry metadata."""
        if len(messages) < 6: return messages
        new_msgs = [messages[0]]
        tool_count = 0
        truncated_count = 0
        preserve_recent_tool_results = max(0, int(self.config.compact_recent_messages))
        
        for msg in reversed(messages[1:]):
            content = msg.get("content", "")
            if self._is_tool_result_message(msg):
                tool_count += 1
                should_preserve_recent = tool_count <= preserve_recent_tool_results
                if (
                    not should_preserve_recent
                    and tool_count > self.config.tool_history_compact_after_tool_calls
                    and len(content) > 600
                ):
                    msg = msg.copy()
                    msg["content"] = content[:500] + "... [Old tool output cleared to save context space]"
                    truncated_count += 1
            new_msgs.insert(1, msg)

        if truncated_count:
            self.trace.add(
                0,
                "tool_history_compacted",
                agent=self.name,
                original_count=len(messages),
                truncated_count=truncated_count,
            )

        return new_msgs

    def compact_context(self, messages: list[Message], estimate:int) -> list[Message]:
        #summary_char_limit = min(int(self.config.compact_summary_limit), max(2000, estimate * 2))

        max_limit = int(min(self.config.compact_summary_limit, max(2000, 0.5 * estimate)))
        min_limit = int(max(2000, estimate * 0.2))

        keep = max(0, int(self.config.compact_recent_messages))
        if len(messages) <= 1 + keep: return messages
        # use a clean base system prompt string each time
        system_prompt_content = self.protocol.build_system_prompt(
                    self.tools.docs(), self.skill_docs, self.memory_docs)
        
        retained_msgs = messages

        if len(retained_msgs) <= keep:
            return messages

        if keep > 0:
            recent_msgs = retained_msgs[-keep:]
            old_msgs = retained_msgs[:-keep]
        else:
            recent_msgs = []
            old_msgs = retained_msgs

        def render(msg: Message) -> str:
            return f"[{msg.get('role', '')}] {msg.get('content', '')}"

        old_text = "\n\n".join(render(m) for m in old_msgs)
        recent_text = "\n\n".join(render(m) for m in recent_msgs)

        # Persistent archival (Tier 3)
        # Search for any explicit 'save_memory' results in old_text to ensure they are indexed
        # if "save_memory" in old_text and "ok\": true" in old_text:
        #      # Logic to re-ensure key facts are archived if relevant
        #      pass

        instruct = (
            "Summarize the OLD history as a factual bulleted list.\n"
            "REQUIREMENTS:\n"
            "1. KEEP all file paths, function names, and variable definitions.\n"
            "2. KEEP all tool execution statuses (OK/Error) and critical return values.\n"
            "3. Use RECENT_CTX only to decide what can be safely omitted from OLD HISTORY.\n"
            "4. Do not repeat RECENT_CTX verbatim unless it is essential to preserve a fact.\n"
            f"5. Ensure the length of summary is between {min_limit} and {max_limit}\n"
        )
        summary_messages = [
            {"role": "system", "content": instruct},
            {"role": "user", "content": f"OLD HISTORY:\n{old_text}\n\nRECENT_CTX:\n{recent_text}"}
        ]
        try:
            summary = (self.llm.complete(summary_messages) or "").strip()
            if len(summary) > max_limit:
                summary = summary[:max_limit].rstrip() + "..."
        except:
            summary = "(summary failed)"

        # incorporate the base system prompt into the summary and place the
        # compressed summary at the beginning of a single system message.
        base_system = system_prompt_content
        if isinstance(base_system, str) and "[HISTORY SUMMARY]" in base_system:
            # remove any prior summary block by keeping the tail after last marker
            base_system = base_system.split("[HISTORY SUMMARY]")[-1].lstrip()

        new_system_content = f"[HISTORY SUMMARY]\n{summary}\n\n{base_system}"
        new_system_msg = {"role": "system", "content": new_system_content}
        new_messages = [new_system_msg] + recent_msgs

        self.trace.add(0, "context_compacted", agent=self.name, original_count=len(messages))
        return new_messages

    def _should_micro_compact(self, messages: list[Message]) -> bool:
        tool_result_count = sum(1 for msg in messages if self._is_tool_result_message(msg))
        if tool_result_count >= self.config.tool_history_compact_after_tool_calls:
            return True

        return any(
            isinstance(msg.get("content", ""), str)
            and len(msg.get("content", "")) > self.config.tool_result_limit
            for msg in messages
        )

    def _should_llm_compact(self, messages: list[Message], num_msgs: int, est_tokens: int) -> bool:
        keep = max(0, int(self.config.compact_recent_messages))
        if len(messages) <= 1 + keep:
            return False

        # retained_msgs = [msg for msg in messages[1:] if not self._is_history_summary_message(msg)]
        if len(messages) <= keep:
            return False

        recent_msgs = messages[-keep:] if keep > 0 else []
        old_msgs = messages[:-keep] if keep > 0 else messages

        old_tokens = sum(len(str(m.get("content", ""))) // 4 for m in old_msgs)
        recent_tokens = sum(len(str(m.get("content", ""))) // 4 for m in recent_msgs)

        if num_msgs >= self.config.compact_after_messages:
            return True
        if est_tokens >= self.config.estimated_token_limit:
            return True
        if old_tokens >= self.config.compact_summary_limit:
            return True
        if old_tokens >= max(3000, self.config.estimated_token_limit * 0.6) and old_tokens >= 2 * max(1, recent_tokens):
            return True

        return False

    def _is_tool_result_message(self, message: Message) -> bool:
        content = message.get("content", "")
        return (
            message.get("role") == "user"
            and isinstance(content, str)
            and content.startswith("Tool `")
            and "returned this JSON result:" in content
        )

    # def _is_history_summary_message(self, message: Message) -> bool:
    #     return (
    #         message.get("role") == "system"
    #         and isinstance(message.get("content"), str)
    #         and message["content"].startswith("[HISTORY SUMMARY]")
    #     )
