---
name: ephemeral-dispatch
description: Handle a short-lived dispatch token, read the notice immediately, and notify the user.
---

## Procedure
1. Call `dispatch_notice_handler` **once immediately**.
2. Do not call any other tool or add preamble before the call.
3. After success, give a very short confirmation.

## Checklist
- Only call `dispatch_notice_handler`.
- Keep the final reply short.
- Preserve exact device names, IDs, and locations from the notice.

## Final Answer
Confirm briefly that the notice was handled.
