# Agent handoff rules

Before changing automation, read `WORKFLOW_HANDOFF.md` and the canonical private handoff repository: https://github.com/pyw31337/macmini-workflow-handoff

When changing `.github/workflows/`, schedules, deployment triggers, secret names, or local scheduler replacements:
1. Preserve the existing trigger and rollback behavior unless the task explicitly changes it.
2. Update `WORKFLOW_HANDOFF.md` in this repository.
3. Update the canonical handoff inventory via its scheduled/manual sync workflow.
4. Never commit secret values, `.env` files, tokens, cookies, or machine-specific paths.
