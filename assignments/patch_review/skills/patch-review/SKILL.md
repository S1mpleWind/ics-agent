---
name: patch-review
description: Review a patch for behavioral and security risk, then submit a structured verdict and comments.
---

## When To Use
Use this skill when the user asks you to review a patch, diff, or code change for risk.

## Procedure
1. use `read_diff` to read the diff first, Read extra patch fixture files only when the diff is not enough to judge risk.
2. Check boundary safety, path handling, input validation, exceptions, missing tests.
3. Treat user-controlled paths without workspace-safe resolution as traversal risk.
4. Decide on a clear verdict such as `request_changes` or an acceptable alternative allowed by the task.
5. Write comments explain the concrete risk
6. Include a test recommendation for each important risk.
7. Call `submit_review` to submit the review and return a confirmation.

## Checklist
- Verdict must be explicit.
- Comments must be actionable
- Mention security and behavior regressions separately when relevant

## Final Answer
Summarize the verdict briefly and mention that the review was submitted.
