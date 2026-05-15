# Memory Design Skeleton

## Objective
- Keep token usage low while retaining cross-session facts.
- Separate short-term context compaction from long-term persistent memory.
- Make memory behavior observable through trace events.

## Two-Layer Model
- Session Layer (Context Compact):
  - Triggered when message history exceeds threshold.
  - Compresses old dialogue into one short summary message.
  - Summary is session-only and must not be written to persistent memory.
- Persistent Layer (Memory Store):
  - Stores stable facts/preferences/rules across sessions.
  - Accessed on demand by key using tools.

## Persistent Store Format
- Backend: local Markdown files.
- One memory per file.
- First line: `# <key>`
- Body: memory content.
- In-memory index: `key -> Memory(key, content, path)`.

## Runtime Contracts
- System prompt includes memory key list only, not full bodies.
- Read policy:
  - If answer needs long-lived facts and key is known, call `read_memory`.
- Save policy:
  - Only save when user asks to remember/update or a stable preference is confirmed.
- Update policy:
  - Same key overwrites prior content.

## Tool Contracts
- `read_memory({key})`:
  - success: `{ok: true, key, content}`
  - failure: `{ok: false, error}`
- `save_memory({key, content})`:
  - success: `{ok: true, key, content}`
  - failure: `{ok: false, error}`

## Trace Requirements
- Emit `memory_retrieve` when `read_memory` succeeds.
- Emit `memory_write` when `save_memory` succeeds.
- Emit `context_compacted` when compaction runs.
- Keep memory trace payload minimal (key only).

## Guardrails
- Reject empty key/content.
- Return explicit error on unknown key.
- Do not invent missing memory facts.
- Prefer multiple small atomic memories over one large mixed memory.

## Suggested Key Naming
- `user.preference.language`
- `user.preference.response_style`
- `project.fact.runtime_model`
- `workflow.rule.output_format`

## Minimal Implementation Steps
1. Keep `MemoryLoader` as source of truth for file-backed storage.
2. Keep memory list in system prompt via `descriptions()`.
3. Add memory trace hooks in agent loop after tool execution.
4. Keep compaction and persistent memory strictly separated.
5. Validate with persistent recall/update evals.
