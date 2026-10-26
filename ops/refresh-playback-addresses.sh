#!/usr/bin/env bash
# Refresh only the short-lived provider address map from a clean, disposable
# worktree. This must never depend on a developer checkout being mergeable.
set -euo pipefail

OPS_HOME="${CCTV_OPS_HOME:-$HOME/.cctv-ops}"
REPO_DIR="$OPS_HOME/repository"
CACHE_DIR="$OPS_HOME/current"
LOG_FILE="${CCTV_OPS_LOG:-$OPS_HOME/refresh.log}"
LOCK_DIR="${CCTV_OPS_LOCK:-$OPS_HOME/refresh.lock}"
PUBLISH_INTERVAL_SECONDS="${CCTV_OPS_PUBLISH_INTERVAL_SECONDS:-1800}"
PUBLISH_STATE="$OPS_HOME/last_publish_epoch"
REMOTE_URL="${CCTV_OPS_REMOTE_URL:-https://github.com/pyw31337/cctv.git}"

stamp() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }
log() { echo "[$(stamp)] $*"; }

mkdir -p "$OPS_HOME" "$CACHE_DIR"
exec >> "$LOG_FILE" 2>&1

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    log 'refresh already running; skipped'
    exit 0
fi
cleanup() {
    if [[ -n "${WORK_DIR:-}" && -d "${WORK_DIR:-}" && -d "$REPO_DIR/.git" ]]; then
        git -C "$REPO_DIR" worktree remove --force "$WORK_DIR" >/dev/null 2>&1 || rm -rf "$WORK_DIR"
    fi
    rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ ! -d "$REPO_DIR/.git" ]]; then
    log 'initializing dedicated operations checkout'
    git clone --depth 1 "$REMOTE_URL" "$REPO_DIR"
fi

git -C "$REPO_DIR" fetch --depth 1 origin main
WORK_DIR="$(mktemp -d "$OPS_HOME/run.XXXXXX")"
git -C "$REPO_DIR" worktree add --detach "$WORK_DIR" origin/main >/dev/null

cd "$WORK_DIR"
log 'refreshing provider playback addresses'
python3 scripts/refresh_z3_cache.py \
    --max-age-minutes 10 \
    --force \
    --stale-ok-on-refresh-failure-hours 0.75

# Keep a local, non-Git copy for the watchdog. It is an operational artifact,
# not part of the user's development checkout.
cp data/z3_cache.json "$CACHE_DIR/z3_cache.json"
cp data/cache_status.json "$CACHE_DIR/cache_status.json"

should_publish=1
if [[ -f "$PUBLISH_STATE" ]]; then
    last="$(cat "$PUBLISH_STATE" 2>/dev/null || echo 0)"
    [[ "$last" =~ ^[0-9]+$ ]] || last=0
    if (( $(date +%s) - last < PUBLISH_INTERVAL_SECONDS )); then
        should_publish=0
    fi
fi

if git diff --quiet -- data/z3_cache.json data/cache_status.json; then
    log 'address map unchanged; no public fallback update needed'
elif (( ! should_publish )); then
    log 'public fallback publish deferred; local address map is fresh'
else
    # This worktree starts from origin/main on every run, so only the two
    # address artifacts are committed and no developer branch can conflict.
    git add data/z3_cache.json data/cache_status.json
    git -c user.name='Lets View Operations' -c user.email='actions@pyw31337.local' \
        commit -m 'AUTO: Refresh playback addresses [skip ci]'
    git push origin HEAD:main
    date +%s > "$PUBLISH_STATE"
    log 'published fresh playback address fallback'
fi

log 'refresh complete'
