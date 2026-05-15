---
name: data-redaction
description: Redact sensitive ticket data, preserve troubleshooting context, validate the result, and submit it.
---

## When To Use
Use this skill to redact support tickets containing secrets or personal data, while keeping operational clues.

## Procedure
1. Call the `read_ticket` tool with `ticket_id`.
2. Replace sensitive values (emails, phones, student IDs, tokens, private IPs) with exact placeholders (e.g., `<EMAIL>`, `<PHONE>`, `<STUDENT_ID>`, `<TOKEN>`, `<PRIVATE_IP>`).
3. Carefully preserve the troubleshooting context, including error symptoms, reproduction steps, system state, and filenames.
4. Call the `validate_redaction` tool with the new `content`.
5. If the checklist is not empty, fix the remaining issues and validate again.
6. Once validation passes, call `submit_redacted_ticket` with `ticket_id` and the final `content`.

## Checklist
- Do not leave partial secrets behind.
- Do not remove important context just because it looks sensitive.
- Keep final response in English.
