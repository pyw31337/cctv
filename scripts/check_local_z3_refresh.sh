#!/usr/bin/env bash
set -euo pipefail

ROOT="${CCTV_ROOT:-/Users/pyw31337/Developer/cctv}"
ORACLE_URL="${CCTV_Z3_ORACLE_URL:-https://158.179.194.163.sslip.io/z3-cache.json}"
LABEL="${CCTV_Z3_LAUNCHD_LABEL:-com.pyw31337.cctv.z3-cache-refresh}"
MAX_LOCAL_AGE_MINUTES="${CCTV_Z3_MAX_LOCAL_AGE_MINUTES:-70}"
MAX_ORACLE_AGE_MINUTES="${CCTV_Z3_MAX_ORACLE_AGE_MINUTES:-70}"
LOG_FILE="${CCTV_LOCAL_Z3_MONITOR_LOG:-$ROOT/logs/local_z3_cache_monitor.log}"
STATE_FILE="${CCTV_LOCAL_Z3_MONITOR_STATE:-$ROOT/logs/local_z3_cache_monitor.state}"
NOTIFY="${1:-}"

stamp() {
  date -u "+%Y-%m-%dT%H:%M:%SZ"
}

mkdir -p "$(dirname "$LOG_FILE")"

cd "$ROOT"

read -r LOCAL_FETCHED LOCAL_AGE LOCAL_ENTRIES < <(
  python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path

path = Path("data/z3_cache.json")
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
    fetched = payload.get("fetched") or ""
    entries = payload.get("entries") or len(payload.get("data") or {})
    dt = datetime.strptime(fetched, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age = round((datetime.now(timezone.utc) - dt).total_seconds() / 60, 1)
    print(fetched, age, entries)
except Exception:
    print("missing", 999999, 0)
PY
)

ORACLE_PAYLOAD="$(mktemp "${TMPDIR:-/tmp}/cctv-z3-oracle.XXXXXX")"
if curl -fsS --max-time 12 "${ORACLE_URL}?ts=$(date +%s)" -o "$ORACLE_PAYLOAD" 2>/dev/null; then
  read -r ORACLE_FETCHED ORACLE_AGE ORACLE_ENTRIES < <(
    python3 - "$ORACLE_PAYLOAD" <<'PY'
import json
import sys
from datetime import datetime, timezone

try:
    with open(sys.argv[1], encoding="utf-8") as f:
        payload = json.load(f)
    fetched = payload.get("fetched") or ""
    entries = payload.get("entries") or len(payload.get("data") or {})
    dt = datetime.strptime(fetched, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    age = round((datetime.now(timezone.utc) - dt).total_seconds() / 60, 1)
    print(fetched, age, entries)
except Exception:
    print("unreachable", 999999, 0)
PY
  )
else
  ORACLE_FETCHED="unreachable"
  ORACLE_AGE="999999"
  ORACLE_ENTRIES="0"
fi
rm -f "$ORACLE_PAYLOAD"

LAUNCHD_STATUS="missing"
if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  LAUNCHD_STATUS="installed"
fi

STATUS="OK"
REASON="local=${LOCAL_AGE}m oracle=${ORACLE_AGE}m entries=${LOCAL_ENTRIES}/${ORACLE_ENTRIES} launchd=${LAUNCHD_STATUS}"

if [ "$LAUNCHD_STATUS" != "installed" ]; then
  STATUS="FAIL"
  REASON="launchd job is not installed"
elif python3 - "$LOCAL_AGE" "$MAX_LOCAL_AGE_MINUTES" <<'PY'
import sys
raise SystemExit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)
PY
then
  STATUS="FAIL"
  REASON="local Z3 cache is stale: ${LOCAL_AGE}m"
elif python3 - "$ORACLE_AGE" "$MAX_ORACLE_AGE_MINUTES" <<'PY'
import sys
raise SystemExit(0 if float(sys.argv[1]) > float(sys.argv[2]) else 1)
PY
then
  STATUS="FAIL"
  REASON="Oracle Z3 cache is stale or unreachable: ${ORACLE_AGE}m"
elif [ "$LOCAL_ENTRIES" -lt 10000 ] || [ "$ORACLE_ENTRIES" -lt 10000 ]; then
  STATUS="WARN"
  REASON="Z3 entry count is unexpectedly low: local=${LOCAL_ENTRIES} oracle=${ORACLE_ENTRIES}"
fi

LINE="[$(stamp)] ${STATUS} ${REASON} local_fetched=${LOCAL_FETCHED} oracle_fetched=${ORACLE_FETCHED}"
echo "$LINE" | tee -a "$LOG_FILE"

PREVIOUS_STATUS=""
if [ -f "$STATE_FILE" ]; then
  PREVIOUS_STATUS="$(cat "$STATE_FILE" 2>/dev/null || true)"
fi
echo "$STATUS" > "$STATE_FILE"

if [ "$NOTIFY" = "--notify" ] && [ "$STATUS" != "OK" ] && [ "$PREVIOUS_STATUS" != "$STATUS" ]; then
  /usr/bin/osascript -e "display notification \"$REASON\" with title \"CCTV Z3 Cache ${STATUS}\"" >/dev/null 2>&1 || true
fi

[ "$STATUS" != "FAIL" ]
