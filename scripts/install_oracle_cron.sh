#!/usr/bin/env bash
set -euo pipefail

ROOT="${CCTV_ROOT:-/home/ubuntu/cctv}"
SCHEDULE="${CCTV_QUALITY_SCHEDULE:-*/15 * * * *}"
JOB="${SCHEDULE} CCTV_ROOT=${ROOT} ${ROOT}/scripts/server_quality_cron.sh"
TMP_FILE="$(mktemp)"

crontab -l 2>/dev/null | grep -v "server_quality_cron.sh" > "$TMP_FILE" || true
echo "$JOB" >> "$TMP_FILE"
crontab "$TMP_FILE"
rm -f "$TMP_FILE"

echo "Installed CCTV quality cron: $JOB"
