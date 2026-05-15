#!/usr/bin/env bash
set -euo pipefail

ROOT="${CCTV_ROOT:-/home/ubuntu/cctv}"
LOCK_FILE="${CCTV_QUALITY_LOCK:-/tmp/cctv_quality_cron.lock}"
LOG_FILE="${CCTV_QUALITY_LOG:-$ROOT/sentinel.log}"

mkdir -p "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "[$(date -Is)] previous quality cron still running; skip" >> "$LOG_FILE"
  exit 0
fi

cd "$ROOT"

if command -v git >/dev/null 2>&1; then
  git fetch --depth=1 origin main >> "$LOG_FILE" 2>&1 || true
  git checkout -q main >> "$LOG_FILE" 2>&1 || true
  git pull --ff-only origin main >> "$LOG_FILE" 2>&1 || true
fi

if [ -x ".venv/bin/python" ]; then
  PYTHON=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
else
  PYTHON="python3"
fi

echo "[$(date -Is)] start regional sentinel" >> "$LOG_FILE"
"$PYTHON" scripts/sentinel.py >> "$LOG_FILE" 2>&1
echo "[$(date -Is)] finish regional sentinel" >> "$LOG_FILE"

# Warm the local status endpoint so the public app can read the fresh result
# from Oracle before falling back to GitHub Pages' static data/status.json.
curl -fsS --max-time 5 "http://127.0.0.1:8080/health-status" >/dev/null 2>&1 || true
