---
name: patch-review
description: Review a patch for behavioral and security risk, then submit a structured verdict and comments.
---

## Procedure
1. Use `read_diff` to check the changes. Use `read_patch_file` only if context is missing.
2. Look for missing tests, input validation, and workspace boundary issues. Treat paths without workspace resolution as traversal risks.
3. Form a clear verdict (e.g., `request_changes`).
4. Submit via `submit_review`. Your comments MUST include: (a) risk explanation, (b) actionable fix (e.g. workspace parsing), and (c) a request for regression tests.
5. Provide a short final answer in English confirming the submission.

## Checklist
- Make the verdict explicit.
- Comments must be actionable, not just descriptive.
- Keep tool arguments and final response in English.
