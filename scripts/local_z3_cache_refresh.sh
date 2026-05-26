#!/usr/bin/env bash
set -euo pipefail

ROOT="${CCTV_ROOT:-/Users/pyw31337/Developer/cctv}"
ORACLE_HOST="${CCTV_ORACLE_HOST:-158.179.194.163}"
KEY_FILE="${CCTV_ORACLE_KEY:-$ROOT/oracle_key}"
LOG_FILE="${CCTV_LOCAL_Z3_LOG:-$ROOT/logs/local_z3_cache_refresh.log}"
LOCK_FILE="${CCTV_LOCAL_Z3_LOCK:-/tmp/cctv_local_z3_cache_refresh.lock}"
LOCK_DIR="${LOCK_FILE}.dir"
MAX_AGE_MINUTES="${CCTV_Z3_MAX_AGE_MINUTES:-25}"
FALLBACK_HOURS="${CCTV_Z3_FALLBACK_HOURS:-8}"

stamp() {
  date -u "+%Y-%m-%dT%H:%M:%SZ"
}

mkdir -p "$(dirname "$LOG_FILE")"
exec >> "$LOG_FILE" 2>&1
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(stamp)] previous local Z3 refresh still running; skip"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT INT TERM

cd "$ROOT"
echo "[$(stamp)] start local Z3 refresh"

if [ -f "$KEY_FILE" ]; then
  chmod 600 "$KEY_FILE" || true
fi

# Keep the local worktree close to origin, but never force-reset user work.
if git diff --quiet && git diff --cached --quiet; then
  git fetch origin main || true
  git pull --ff-only origin main || true
else
  echo "[$(stamp)] local changes detected; skip pre-refresh pull"
fi

python3 scripts/refresh_z3_cache.py \
  --max-age-minutes "$MAX_AGE_MINUTES" \
  --force \
  --stale-ok-on-refresh-failure-hours "$FALLBACK_HOURS"

# Keep the dashboard useful while the telemetry Worker is unavailable.
python3 scripts/build_quality_summary_fallback.py || true

# Push fresh cache/status files directly to Oracle. JSON endpoints read these
# files without a server restart, so this avoids unnecessary downtime.
if [ -f "$KEY_FILE" ]; then
  rsync -az -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    data/z3_cache.json data/cache_status.json data/quality_summary.json \
    "ubuntu@$ORACLE_HOST:~/cctv/data/"
  ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "ubuntu@$ORACLE_HOST" \
    'curl -fsS --max-time 5 http://127.0.0.1:8080/z3-cache.json >/dev/null || true; curl -fsS --max-time 5 http://127.0.0.1:8080/ops-status >/dev/null || true' || true
else
  echo "[$(stamp)] oracle key not found; skipped Oracle rsync"
fi

# Commit and push the static GitHub Pages fallback without triggering Actions.
if ! git diff --quiet -- data/z3_cache.json data/cache_status.json data/quality_summary.json; then
  git add data/z3_cache.json data/cache_status.json data/quality_summary.json
  git commit -m "AUTO: Local Z3 cache refresh [skip ci]"
  git pull --rebase --autostash origin main || true
  git push origin main || true
else
  echo "[$(stamp)] no cache changes to commit"
fi

echo "[$(stamp)] finish local Z3 refresh"
