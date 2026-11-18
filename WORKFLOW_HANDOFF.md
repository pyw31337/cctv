# Workflow handoff

- Canonical handoff: https://github.com/pyw31337/macmini-workflow-handoff
- Read the canonical repository `AGENTS.md` and latest `inventory/workflows.json` before changing automated jobs.
- Any change to `.github/workflows/`, collection cadence, deployment triggers, secrets names, or local scheduler replacements must update this file and the canonical handoff repository in the same change.
- Never commit secret values, `.env` files, tokens, cookies, or machine-specific paths.

The authoritative workflow files remain in this repository under `.github/workflows/`. GitHub-hosted Actions do not depend on the old Mac.

### Resilience and Self-Healing Enhancements
- `commit_and_push_changes.sh`: Auto-stashes uncommitted/untracked changes before attempting `git rebase origin/main` in push-retry loops, preventing `error: cannot rebase: You have unstaged changes` during concurrent bot pushes.
- `refresh_z3_cache.py`: When external government ITS servers (`its.go.kr`) experience transient timeouts or geoblocking from GitHub runners, existing valid cache is preserved and status is logged as `STALE_UPSTREAM_UNREACHABLE` rather than crashing the workflow.
- `browser-canary.yml` / `browser_canary.mjs`: Strict failure is scoped to structural regressions (`hard_failed > 0`). Upstream external camera outages/buffering delays in headless CI are recorded as service-impact telemetry without firing false-positive failure alerts.
- `update_cctv.yml`: Validation step safely rolls back to previous snapshot if validation encounters issues, preventing unhandled step exits.

The Mac mini playback-address launchd job runs `ops/refresh-playback-addresses.sh` from a disposable operations checkout every 30 minutes. The job records its PID in `refresh.lock/pid` and removes stale locks after an interrupted process so a crash cannot permanently suppress future refreshes. It only publishes `data/z3_cache.json` and `data/cache_status.json`; it does not alter the developer checkout.
