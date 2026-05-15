---
name: ephemeral-dispatch
description: Handle a short-lived dispatch token, read the notice immediately, and notify the user.
---

## When To Use
Use this skill when the user needs an urgent dispatch notice handled before the token expires.

## Procedure
1. Use the `dispatch_notice_handler` tool immediately to handle the dispatch and avoid token expiration. DO NOT chat, summarize, or invoke any other tool first.
2. The custom `dispatch_notice_handler` tool will internally fetch the token, get the notice, write to `dispatch_receipt.txt`, and notify the user. 
3. After the tool successfully executes, provide a short confirmation that the user has received the notice.

## Checklist
- Only call `dispatch_notice_handler`.
- Do not call unrelated tools.
- Do not chat before calling the tool.
- Provide a short confirmation message only after the tool successfully executed.
- Preserve exact device names, IDs, or locations from the notice.

## Final Answer
Confirm briefly that the user has received the dispatch notice.
