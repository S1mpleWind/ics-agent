---
name: data-redaction
description: Redact sensitive ticket data, preserve troubleshooting context, validate the result, and submit it.
---

## When To Use
Use this skill when the user asks to redact a support ticket or any incident report that may contain secrets or personal data.

## Procedure
1. Read the original ticket first.
2. Identify sensitive values such as email addresses, phone numbers, student IDs, access tokens, and private/internal IPs.
3. Replace sensitive values with placeholders, but keep the troubleshooting story intact.
4. Preserve the error symptoms, reproduction steps, system state, and any exact file or service names that help debugging.
5. Call the validation tool before submitting.
6. If validation reports issues, revise the text and validate again.
7. Submit only after the redacted text passes validation.

## Checklist
- Do not remove important incident context just because it looks sensitive.
- Do not leave partial secrets behind.
- Prefer clear placeholders like `<EMAIL>`, `<PHONE>`, `<STUDENT_ID>`, `<TOKEN>`, or `<PRIVATE_IP>`.
- Keep the final response and tool arguments in English when possible.

## Final Answer
State briefly that the redacted ticket was submitted successfully.
