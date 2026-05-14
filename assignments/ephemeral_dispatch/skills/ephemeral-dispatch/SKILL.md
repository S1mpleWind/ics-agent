---
name: ephemeral-dispatch
description: Handle a short-lived dispatch token, read the notice immediately, and notify the user.
---

## When To Use
Use this skill when the user needs an urgent dispatch notice handled before the token expires.

## Procedure
1. Use the dispatch tools immediately; do not chat first.
2. Request the token and read the notice as soon as you have it.
3. If the notice is missing, invalid, or expired, retry only if the workflow still allows it.
4. Send the notice to the user through the notification tool.
5. Write the final notice text to the workspace receipt file if the tool flow requires it.
6. Return a short confirmation only after delivery succeeds.

## Checklist
- Keep the workflow as short as possible.
- Do not call unrelated tools.
- Do not summarize the notice unless the task explicitly asks for a summary.
- Preserve exact device names, IDs, or locations from the notice.

## Final Answer
Confirm briefly that the user has received the dispatch notice.
