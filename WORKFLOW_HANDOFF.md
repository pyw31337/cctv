# Workflow handoff

- Canonical handoff: https://github.com/pyw31337/macmini-workflow-handoff
- Read the canonical repository `AGENTS.md` and latest `inventory/workflows.json` before changing automated jobs.
- Any change to `.github/workflows/`, collection cadence, deployment triggers, secrets names, or local scheduler replacements must update this file and the canonical handoff repository in the same change.
- Never commit secret values, `.env` files, tokens, cookies, or machine-specific paths.

The authoritative workflow files remain in this repository under `.github/workflows/`. GitHub-hosted Actions do not depend on the old Mac.
