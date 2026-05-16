---
name: patch-review
description: Review a patch for behavioral and security risk, then submit a structured verdict and comments.
---

## When To Use
Use this skill when the user asks you to review a patch, diff, or code change for risk.

## Procedure
1. Call `read_diff()` first and inspect the diff; avoid enumerating repository directories.
2. Only call `read_patch_file(path)` when the diff references a file you need to inspect.
3. Build evidence from the tool outputs, then decide a clear verdict (usually `request_changes` when risk is present).
4. Prepare `comments` in English that: explain how the risk occurs, propose concrete fixes, and require regression tests.
5. The comments must explicitly mention `workspace.resolve` when recommending how to fix file-reading code.
6. Call `submit_review(verdict, comments)` once. If the service rejects the submission, amend comments only once to include any missing required phrases (e.g., `workspace.resolve`, `regression test`) and resubmit a single time.

## Checklist
- **Path Traversal & Boundaries:** Verify file reads use workspace-safe resolution; recommend `workspace.resolve` in fixes.
- **Input validation & Exception handling:** Ensure inputs are validated and errors are handled.
- **Missing tests:** Require regression tests that cover normal behavior and boundary/attack cases.

## Final Answer
Confirm the review submission, give the short verdict, and ensure `review.txt` was written.
