#!/usr/bin/env bash
# Install the dedicated low-impact address refresher on this Mac.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPS_HOME="${CCTV_OPS_HOME:-$HOME/.cctv-ops}"
LABEL='com.pyw31337.letsview.playback-addresses'
PLIST_SOURCE="$ROOT/ops/launchd/$LABEL.plist"
PLIST_TARGET="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$OPS_HOME"
chmod +x "$ROOT/ops/refresh-playback-addresses.sh"
# Bootstrap a clean dedicated clone before launchd can invoke its copy.
bash "$ROOT/ops/refresh-playback-addresses.sh"
cp "$PLIST_SOURCE" "$PLIST_TARGET"

uid="$(id -u)"
# Retire the pre-isolation jobs. They use the developer checkout, can trigger
# expensive rebases, and must not revive automatically at the next login.
mkdir -p "$OPS_HOME/disabled-launchagents"
for legacy_label in com.pyw31337.cctv.z3-cache-refresh com.pyw31337.cctv.z3-cache-monitor; do
  launchctl bootout "gui/$uid/$legacy_label" >/dev/null 2>&1 || true
  legacy_plist="$HOME/Library/LaunchAgents/$legacy_label.plist"
  if [[ -f "$legacy_plist" ]]; then
    mv "$legacy_plist" "$OPS_HOME/disabled-launchagents/"
  fi
done
launchctl bootout "gui/$uid/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$uid" "$PLIST_TARGET"
launchctl kickstart -k "gui/$uid/$LABEL"
echo "Installed $LABEL. It refreshes provider address maps every 30 minutes in $OPS_HOME."
