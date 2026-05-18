import re

with open("ics_agent_lab/core/agent.py", "r") as f:
    content = f.read()

pattern = r"    def compact_context\(self, messages: list\[Message\], estimate: int\) -> list\[Message\]:.*?    def _should_micro_compact"

replacement = r'''    def compact_context(self, messages: list[Message], estimate: int) -> list[Message]:
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
        history_lines.append("This is a highly truncated log of previous actions to preserve your reasoning trace.\\n")

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
                        header, result_str = content.split("returned this JSON result:\\n", 1)
                        is_err = re.search(r"(?i)(error|failed|exception|traceback|timeout|not found)", result_str)
                        if len(result_str) < 300:
                            snippet = result_str
                        else:
                            if is_err:
                                snippet = result_str[:150] + "\\n  ... [truncated] ...\\n  " + result_str[-250:]
                            else:
                                snippet = result_str[:150] + "\\n  ... [truncated successful output]"
                        
                        snippet = snippet.replace("\\n", "\\n    ")
                        history_lines.append(f"  **Result**: {snippet.strip()}")
                    except Exception:
                        history_lines.append(f"  **Result**: {content[:100]}...")
                else:
                    history_lines.append(f"- **User**: {content[:100]}...")

        history_summary = "\\n".join(history_lines)
        limit = int(self.config.compact_summary_limit)
        if len(history_summary) > limit:
            history_summary = "...\\n" + history_summary[-limit:]

        base_system = system_prompt_content
        if isinstance(base_system, str) and "[HISTORY SUMMARY]" in base_system:
            base_system = base_system.split("[HISTORY SUMMARY]")[-1].lstrip()

        new_system_content = f"[HISTORY SUMMARY]\\n{history_summary}\\n\\n{base_system}"
        new_messages = [{"role": "system", "content": new_system_content}] + recent_msgs

        self.trace.add(0, "context_compacted_deterministic", agent=self.name, original_count=len(messages))
        return new_messages

    def _should_micro_compact'''

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

with open("ics_agent_lab/core/agent.py", "w") as f:
    f.write(new_content)
