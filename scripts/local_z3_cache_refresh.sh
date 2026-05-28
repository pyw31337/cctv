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
GITHUB_FALLBACK_PUSH_INTERVAL_MINUTES="${CCTV_Z3_GITHUB_FALLBACK_PUSH_INTERVAL_MINUTES:-360}"
GITHUB_FALLBACK_STATE_FILE="${CCTV_Z3_GITHUB_FALLBACK_STATE_FILE:-$ROOT/logs/local_z3_cache_refresh.last_github_push}"
ORACLE_BASE="${CCTV_ORACLE_BASE:-https://158.179.194.163.sslip.io}"

stamp() {
  date -u "+%Y-%m-%dT%H:%M:%SZ"
}

epoch_now() {
  date -u "+%s"
}

should_push_github_fallback() {
  if [ "$GITHUB_FALLBACK_PUSH_INTERVAL_MINUTES" = "0" ]; then
    return 1
  fi
  if [ ! -f "$GITHUB_FALLBACK_STATE_FILE" ]; then
    return 0
  fi
  local last_push
  last_push="$(cat "$GITHUB_FALLBACK_STATE_FILE" 2>/dev/null || echo 0)"
  case "$last_push" in
    ''|*[!0-9]*) last_push=0 ;;
  esac
  local elapsed=$(( $(epoch_now) - last_push ))
  [ "$elapsed" -ge $(( GITHUB_FALLBACK_PUSH_INTERVAL_MINUTES * 60 )) ]
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

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
else
  PYTHON="python3"
fi

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

"$PYTHON" scripts/refresh_z3_cache.py \
  --max-age-minutes "$MAX_AGE_MINUTES" \
  --force \
  --stale-ok-on-refresh-failure-hours "$FALLBACK_HOURS"

# Keep the dashboard useful while the telemetry Worker is unavailable.
"$PYTHON" scripts/build_quality_summary_fallback.py || true

fetch_oracle_json_fallback() {
  local endpoint="$1"
  local output="$2"
  local tmp="${output}.tmp"
  if curl -fsS --max-time 10 "${ORACLE_BASE}${endpoint}" -o "$tmp"; then
    if "$PYTHON" - "$tmp" "$output" <<'PY'; then
import json
import sys

source, target = sys.argv[1], sys.argv[2]
with open(source, encoding="utf-8") as f:
    data = json.load(f)
try:
    with open(target, encoding="utf-8") as f:
        previous = json.load(f)
except Exception:
    previous = {}
if isinstance(previous, dict) and isinstance(data, dict):
    # Oracle may temporarily serve an older health schema. Preserve the local
    # rotating coverage registry so local Z3 refresh cannot erase Sentinel's
    # cumulative check history.
    for key in ("camera_checks", "coverage", "sampling_policy"):
        if key not in data and key in previous:
            data[key] = previous[key]
with open(target, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write("\n")
PY
      rm -f "$tmp"
      echo "[$(stamp)] refreshed static fallback ${output} from Oracle ${endpoint}"
      return 0
    fi
  fi
  rm -f "$tmp"
  echo "[$(stamp)] could not refresh static fallback ${output} from Oracle ${endpoint}; keeping previous file"
  return 1
}

# Oracle is the primary checker while GitHub minutes are constrained, but the
# public app still needs a fresh GitHub Pages fallback when Oracle is briefly
# unreachable. Pull the latest operational snapshots back into the repo so
# stale multi-day status files cannot paint playable cameras red.
fetch_oracle_json_fallback "/health-status" "data/status.json" || true
fetch_oracle_json_fallback "/canary-status" "data/canary_status.json" || true
fetch_oracle_json_fallback "/ops-status" "data/ops_status.json" || true

"$PYTHON" scripts/build_quality_summary_fallback.py || true
"$PYTHON" scripts/standardize_quality_times.py --source local-z3-refresh || true

# Push fresh cache/status files directly to Oracle. JSON endpoints read these
# files without a server restart, so this avoids unnecessary downtime.
if [ -f "$KEY_FILE" ]; then
  rsync -az -e "ssh -i $KEY_FILE -o StrictHostKeyChecking=no" \
    data/z3_cache.json data/cache_status.json data/quality_summary.json data/status.json data/canary_status.json data/ops_status.json data/workflow_status.json \
    "ubuntu@$ORACLE_HOST:~/cctv/data/"
  ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no "ubuntu@$ORACLE_HOST" \
    'curl -fsS --max-time 5 http://127.0.0.1:8080/z3-cache.json >/dev/null || true; curl -fsS --max-time 5 http://127.0.0.1:8080/ops-status >/dev/null || true' || true
else
  echo "[$(stamp)] oracle key not found; skipped Oracle rsync"
fi

# Commit and push the static GitHub Pages fallback sparingly. Even with
# `[skip ci]`, GitHub Pages deployment can still run for every commit, so the
# Oracle sync above is the primary freshness path while Actions minutes are low.
if ! git diff --quiet -- data/z3_cache.json data/cache_status.json data/quality_summary.json data/status.json data/canary_status.json data/ops_status.json data/workflow_status.json; then
  if should_push_github_fallback; then
    git add data/z3_cache.json data/cache_status.json data/quality_summary.json data/status.json data/canary_status.json data/ops_status.json data/workflow_status.json
    git commit -m "AUTO: Local Z3 cache refresh [skip ci]"
    git pull --rebase --autostash origin main || true
    if git push origin main; then
      epoch_now > "$GITHUB_FALLBACK_STATE_FILE"
    fi
  else
    echo "[$(stamp)] GitHub fallback push throttled (${GITHUB_FALLBACK_PUSH_INTERVAL_MINUTES}m interval); Oracle already synced"
  fi
else
  echo "[$(stamp)] no cache changes to commit"
fi

echo "[$(stamp)] finish local Z3 refresh"
