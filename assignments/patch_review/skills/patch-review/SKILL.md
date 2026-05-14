---
name: patch-review
description: Review a patch for behavioral and security risk, then submit a structured verdict and comments.
---

## When To Use
Use this skill when the user asks you to review a patch, diff, or code change for risk.

## Procedure
1. Read the diff first.
2. Read extra patch fixture files only when the diff is not enough to judge risk.
3. Check workspace boundaries, path handling, input validation, exception handling, and missing tests.
4. Treat direct user-controlled file paths without workspace-safe resolution as a traversal risk.
5. Decide on a clear verdict such as `request_changes` or an acceptable alternative allowed by the task.
6. Write comments that explain the concrete risk, how it happens, and what to change.
7. Include a test recommendation for each important risk.
8. Submit the review and then return a short confirmation.

## Checklist
- Verdict must be explicit.
- Comments must be actionable, not just descriptive.
- Mention security and behavior regressions separately when relevant.
- Keep the final response and tool arguments in English when possible.

## Final Answer
Summarize the verdict briefly and mention that the review was submitted.
