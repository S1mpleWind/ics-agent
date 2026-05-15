---
name: patch-review
description: Review a patch for behavioral and security risk, then submit a structured verdict and comments.
---

## When To Use
Use this skill when the user asks you to review a patch, diff, or code change for risk.

## Procedure
1. Use `read_diff` first to understand the change.
2. Use `read_patch_file` only if the diff is not enough to judge the risk.
3. Check path safety, input validation, exception handling, and missing tests.
4. Decide on a clear verdict, usually `request_changes` when risk is real.
5. Write short, actionable comments that explain the concrete risk and any test recommendation.
6. Call `submit_review` to submit the review and return a confirmation.

## Checklist
- Verdict must be explicit.
- Comments must be actionable.
- Mention security and behavior regressions separately when relevant.

## Final Answer
Summarize the verdict briefly and mention that the review was submitted.
