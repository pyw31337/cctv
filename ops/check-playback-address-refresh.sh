#!/usr/bin/env bash
set -euo pipefail

OPS_HOME="${CCTV_OPS_HOME:-$HOME/.cctv-ops}"
LABEL='com.pyw31337.letsview.playback-addresses'
MAX_AGE_MINUTES="${CCTV_OPS_MAX_AGE_MINUTES:-45}"

python3 - "$OPS_HOME/current/z3_cache.json" "$MAX_AGE_MINUTES" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, maximum = sys.argv[1], float(sys.argv[2])
with open(path, encoding='utf-8') as handle:
    payload = json.load(handle)
fetched = datetime.strptime(payload['fetched'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
age = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
entries = int(payload.get('entries') or len(payload.get('data') or {}))
print(f'playback-address-cache fetched={payload["fetched"]} age_minutes={age:.1f} entries={entries}')
raise SystemExit(0 if age <= maximum and entries >= 10000 else 1)
PY

launchctl print "gui/$(id -u)/$LABEL" >/dev/null
