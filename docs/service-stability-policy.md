# CCTV Service Stability Policy

This service is optimized for catalog preservation first, then playback quality ranking.

## Operating Principles

- Keep known CCTV records visible in the catalog and on the map whenever possible.
- Do not delete, hide, or mark cameras as permanently inactive only because a probe failed.
- Health checks should rank unstable cameras lower and mark them as `manual_check` for review.
- A camera may return to `active` when a later direct playback check succeeds.
- Cache and token refresh jobs must run preservation guards before committing data changes.
- Original-site-only cameras remain in the catalog when they are useful inventory. They are filterable and ranked below direct playable streams, not deleted.
- Dashboard-facing JSON files should include a shared `time` object with `schema: cctv-quality-time-v1`.

## Status Semantics

- `active`: Recently verified or currently expected to play normally.
- `manual_check`: The camera remains visible, but recent automation found a possible playback issue.
- Destructive statuses such as `disabled`, `inactive`, `broken`, `deleted`, or `removed` are not allowed in committed data.

## Workflow Guardrails

Every data-mutating workflow should:

1. Snapshot the current `cctv_data.json`.
2. Run its update, repair, or health-marking step.
3. Run `scripts/guard_data_preservation.py --previous /tmp/cctv_data.before.json --fix-statuses`.
4. Commit only if the guard confirms that data was preserved.

The guard blocks unexpectedly large camera-count drops and converts legacy destructive statuses to `manual_check`.

Generated-data workflows that can safely preserve the previous catalog should restore their snapshot and write `data/workflow_status.json` when their collector fails. This turns noisy "Run failed" emails into actionable dashboard warnings while keeping true data-preservation failures hard-failing.

## User Experience Rule

Health information is a confidence signal, not a hard deletion signal. The UI should prefer stable nearby streams first, but still allow users to open review cameras because some provider-side failures are intermittent.
