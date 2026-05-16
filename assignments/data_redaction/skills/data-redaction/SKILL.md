---
name: data-redaction
description: Redact sensitive ticket data, preserve troubleshooting context, validate the result, and submit it.
---

## Procedure
1. Read the ticket with `read_ticket`.
2. Redact secrets with exact placeholders such as `<EMAIL>`, `<PHONE>`, `<STUDENT_ID>`, `<TOKEN>`, and `<PRIVATE_IP>`.
3. Preserve troubleshooting details, filenames, symptoms, and reproduction steps.
4. Validate the draft with `validate_redaction`.
5. Fix any remaining issues, then submit with `submit_redacted_ticket`.

## Checklist
- Remove all secrets, including partial ones.
- Keep the operational context intact.
- Validate before submitting.

## Final Answer
Keep the response brief and in English.
