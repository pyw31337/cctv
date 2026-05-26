# Z3 Local Cache Fallback

GitHub Actions minutes are exhausted until the monthly reset, so Z3 appUrl cache
refresh runs locally on the Mac and deploys the generated cache to Oracle.

## Active Jobs

- `com.pyw31337.cctv.z3-cache-refresh`
  - Runs every 30 minutes.
  - Refreshes `data/z3_cache.json` and `data/cache_status.json`.
  - Syncs fresh data to Oracle.
  - Commits generated JSON with `[skip ci]` so GitHub Actions minutes are not consumed.
- `com.pyw31337.cctv.z3-cache-monitor`
  - Runs every 15 minutes.
  - Checks local cache age, Oracle cache age, entry count, and launchd registration.
  - Shows a macOS notification only when the status changes to a non-OK state.

## Manual Checks

```bash
launchctl print "gui/$(id -u)/com.pyw31337.cctv.z3-cache-refresh"
launchctl print "gui/$(id -u)/com.pyw31337.cctv.z3-cache-monitor"
scripts/check_local_z3_refresh.sh
tail -f logs/local_z3_cache_refresh.log
tail -f logs/local_z3_cache_monitor.log
```

## Reset Plan

When GitHub Actions minutes reset, restore a conservative GitHub schedule only
after confirming the local fallback is healthy:

1. Keep local launchd enabled for one more day as a safety net.
2. Re-enable `.github/workflows/z3_cache_refresh.yml` on an offset schedule.
3. Confirm the workflow succeeds twice.
4. Disable the local refresh job only if GitHub and Oracle freshness remain OK.

Recommended GitHub schedule after reset:

```yaml
schedule:
  - cron: '23 1,5,9,13,17,21 * * *'
```

Do not delete local fallback scripts. They are the emergency path when Actions
minutes, GitHub availability, or workflow credentials fail.
