from __future__ import annotations

import json
import re
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
    compact_after_messages: int = 12
    compact_recent_messages: int = 5
    compact_summary_limit: int = 6000
    tool_result_limit: int = 5800
    estimated_token_limit: int = 12000
    llm_compact_high_water: int = 12000
    llm_compact_low_water: int = 8500
    llm_compact_cooldown_steps: int = 8
    # Non-LLM compaction options



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
        last_llm_compact_step = -10**9
        for step in range(self.config.max_steps):
            num_msgs = len(messages)
            est_tokens = estimate_tokens(messages)

            if self._should_micro_compact(messages):
                messages = self.micro_compact_tool_history(messages, est_tokens)

            if self._should_compact(messages, num_msgs, est_tokens, step, last_llm_compact_step):
                messages = self.compact_context(messages, est_tokens)
                last_llm_compact_step = step

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
        if len(messages) < int(self.config.compact_recent_messages): return messages
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
                    and len(content) > 400
                ):
                    msg = msg.copy()
                    msg["content"] = content[:350] + "... [Old tool output cleared to save context space]"
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

    def compact_context(self, messages: list[Message], estimate: int) -> list[Message]:
        """
        Deterministic, zero-LLM context compaction.
        Preserves Thought -> Action -> Result chain, but heavily truncates payloads 
        to keep the logical skeleton intact. Prevents hallucination while costing 0 API requests.
        """
        keep = max(0, int(self.config.compact_recent_messages))
        if len(messages) <= 1 + keep:
            return messages

        system_prompt_content = self.protocol.build_system_prompt(
            self.tools.docs(), self.skill_docs, self.memory_docs
        )

        retained_msgs = messages[1:]
        recent_msgs = retained_msgs[-keep:] if keep > 0 else []
        old_msgs = retained_msgs[:-keep] if keep > 0 else retained_msgs

        history_lines = ["## Extracted Action Log (Oldest to Newest)"]
        history_lines.append("This is a highly truncated log of previous actions to preserve your reasoning trace.\n")

        for msg in old_msgs:
            role = msg.get("role", "")
            content = str(msg.get("content", "")).strip()

            if role == "assistant":
                parsed = None
                idx = content.find("{")
                if idx != -1:
                    try:
                        parsed = json.loads(content[idx:])
                    except Exception:
                        pass
                
                if isinstance(parsed, dict) and "kind" in parsed:
                    thought = parsed.get("thought", parsed.get("reasoning", ""))
                    if len(thought) > 300: thought = thought[:300] + "..."
                    
                    if thought:
                        history_lines.append(f"- **Thought**: {thought}")
                        
                    kind = parsed.get("kind", "")
                    if kind == "tool_call":
                        name = parsed.get("name", "unknown")
                        args = json.dumps(parsed.get("arguments", {}), ensure_ascii=False)
                        if len(args) > 150: args = args[:147] + "..."
                        history_lines.append(f"  **Action**: `{name}`({args})")
                    elif kind == "final":
                        history_lines.append(f"- **Final**: {parsed.get('content', '')[:100]}...")
                else:
                    history_lines.append(f"- **Agent**: {content[:100]}...")

            elif role == "user":
                if self._is_tool_result_message(msg):
                    try:
                        header, result_str = content.split("returned this JSON result:\n", 1)
                        is_err = re.search(r"(?i)(error|failed|exception|traceback|timeout|not found)", result_str)
                        if len(result_str) < 300:
                            snippet = result_str
                        else:
                            if is_err:
                                snippet = result_str[:150] + "\n  ... [truncated] ...\n  " + result_str[-250:]
                            else:
                                snippet = result_str[:150] + "\n  ... [truncated successful output]"
                        
                        snippet = snippet.replace("\n", "\n    ")
                        history_lines.append(f"  **Result**: {snippet.strip()}")
                    except Exception:
                        history_lines.append(f"  **Result**: {content[:100]}...")
                else:
                    history_lines.append(f"- **User**: {content[:100]}...")

        history_summary = "\n".join(history_lines)
        limit = int(self.config.compact_summary_limit)
        if len(history_summary) > limit:
            history_summary = "...\n" + history_summary[-limit:]

        base_system = system_prompt_content
        if isinstance(base_system, str) and "[HISTORY SUMMARY]" in base_system:
            base_system = base_system.split("[HISTORY SUMMARY]")[-1].lstrip()

        new_system_content = f"[HISTORY SUMMARY]\n{history_summary}\n\n{base_system}"
        new_messages = [{"role": "system", "content": new_system_content}] + recent_msgs

        self.trace.add(0, "context_compacted_deterministic", agent=self.name, original_count=len(messages))
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

    def _should_compact(
        self,
        messages: list[Message],
        num_msgs: int,
        est_tokens: int,
        step: int,
        last_llm_compact_step: int,
    ) -> bool:
        keep = max(0, int(self.config.compact_recent_messages))
        if len(messages) <= 1 + keep:
            return False

        if step - last_llm_compact_step < max(0, int(self.config.llm_compact_cooldown_steps)):
            return False

        recent_msgs = messages[-keep:] if keep > 0 else []
        old_msgs = messages[:-keep] if keep > 0 else messages

        old_tokens = sum(len(str(m.get("content", ""))) // 4 for m in old_msgs)
        recent_tokens = sum(len(str(m.get("content", ""))) // 4 for m in recent_msgs)

        if num_msgs >= self.config.compact_after_messages:
            return old_tokens >= self.config.llm_compact_high_water
        if est_tokens >= self.config.llm_compact_high_water:
            return True
        if old_tokens >= self.config.llm_compact_high_water:
            return True
        if old_tokens >= self.config.compact_summary_limit:
            return False
        if old_tokens >= self.config.llm_compact_low_water and old_tokens >= 2 * max(1, recent_tokens):
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
