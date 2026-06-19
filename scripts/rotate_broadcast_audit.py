#!/usr/bin/env python3
"""Rotating broadcast audit for local and global CCTV catalogs.

The audit is designed as an operations SLO loop, not a one-off cleanup:

- cover every retained local and global camera within a 48 hour window;
- prioritize never checked, failed, and stale cameras first;
- try local backup URLs before marking a camera unavailable;
- classify global source-only cameras separately from in-app playable streams;
- write compact per-camera state so later runs continue where the last one left
  off instead of repeatedly probing the same popular providers.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import math
import os
import re
import socket
import ssl
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DATA_PATH = ROOT / "cctv_data.json"
GLOBAL_DATA_PATH = ROOT / "data" / "world_tour_cams.json"
DEFAULT_STATUS_PATH = ROOT / "data" / "broadcast_audit_status.json"

DEFAULT_WINDOW_HOURS = 48
DEFAULT_SCHEDULE_HOURS = 4
DEFAULT_LOCAL_BUDGET = 1700
DEFAULT_GLOBAL_BUDGET = 240
DEFAULT_WORKERS = 32
DEFAULT_TIMEOUT = 8.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (cctv-broadcast-audit/1.0; +https://pyw31337.github.io/cctv/) Chrome/124",
    "Accept": "*/*",
}
SSL_CONTEXT = ssl._create_unverified_context()
HTML_RE = re.compile(r"<\s*(html|body|iframe|script|title)\b", re.I)
BLOCKED_RE = re.compile(r"(403\s+forbidden|access\s+denied|connection\s+refused|refused\s+to\s+connect|not\s+found)", re.I)
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|gif|webp)(?:$|[?#])", re.I)
HLS_EXT_RE = re.compile(r"\.m3u8(?:$|[?#])", re.I)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def utc_stamp(now: dt.datetime | None = None) -> str:
    value = now or utc_now()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(value: Any) -> dt.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
    except ValueError:
        try:
            return dt.datetime.strptime(text.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc)
        except ValueError:
            return None


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except Exception as error:
        print(f"[WARN] failed to load {path}: {error}", file=sys.stderr)
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def compute_budget(total: int, window_hours: int = DEFAULT_WINDOW_HOURS, schedule_hours: int = DEFAULT_SCHEDULE_HOURS) -> int:
    runs_per_window = max(1, math.floor(window_hours / max(1, schedule_hours)))
    return max(1, math.ceil(total / runs_per_window)) if total > 0 else 0


def camera_key(scope: str, item: dict[str, Any]) -> str:
    raw = item.get("id") or item.get("original_id") or item.get("title") or item.get("name") or item.get("url")
    return f"{scope}:{str(raw or '').strip()}"


def source_of(scope: str, item: dict[str, Any]) -> str:
    return str(item.get("sourceType") if scope == "global" else item.get("source") or "UNKNOWN")


def normalize_status_items(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = payload.get("items") if isinstance(payload, dict) else None
    return items if isinstance(items, dict) else {}


def is_ok_status(entry: dict[str, Any] | None) -> bool:
    return bool(entry and entry.get("ok") is True)


def sort_priority(scope: str, item: dict[str, Any], state_items: dict[str, dict[str, Any]], now: dt.datetime) -> tuple:
    key = camera_key(scope, item)
    state = state_items.get(key, {})
    checked_at = parse_stamp(state.get("checkedAt"))
    age_seconds = (now - checked_at).total_seconds() if checked_at else float("inf")
    never_rank = 0 if checked_at is None else 1
    failed_rank = 0 if state and not is_ok_status(state) else 1
    stale_rank = -age_seconds
    status = str(state.get("status") or "")
    high_risk = 0 if status in {"timeout", "http_error", "blocked", "bad_manifest", "source_page_blocked"} else 1
    return (never_rank, failed_rank, high_risk, stale_rank, source_of(scope, item), key)


def select_due_items(
    scope: str,
    items: list[dict[str, Any]],
    state_items: dict[str, dict[str, Any]],
    budget: int,
    now: dt.datetime | None = None,
) -> list[dict[str, Any]]:
    if budget <= 0:
        return []
    value_now = now or utc_now()
    return sorted(items, key=lambda item: sort_priority(scope, item, state_items, value_now))[: min(budget, len(items))]


def request_url(url: str, timeout: float, method: str = "GET") -> tuple[int, str, bytes]:
    req = Request(url, headers=HEADERS, method=method)
    with urlopen(req, timeout=timeout, context=SSL_CONTEXT) as response:
        status = int(getattr(response, "status", 200) or 200)
        content_type = str(response.headers.get("Content-Type") or "").lower()
        body = response.read(256 * 1024)
    return status, content_type, body


def classify_response(url: str, status: int, content_type: str, body: bytes) -> tuple[bool, str, str]:
    text_sample = body[:4096].decode("utf-8", errors="ignore")
    lower_type = content_type.lower()
    if status >= 400:
        return False, "http_error", f"http_{status}"
    if IMAGE_EXT_RE.search(url) or lower_type.startswith("image/"):
        return False, "snapshot_only", "image_response"
    if HLS_EXT_RE.search(url):
        if b"#EXTM3U" in body:
            return True, "manifest_ok", "hls_manifest_ok"
        return False, "bad_manifest", "m3u8_without_extm3u"
    if lower_type.startswith("video/") or lower_type in {"application/vnd.apple.mpegurl", "application/x-mpegurl"}:
        return True, "video_ok", lower_type or "video_response"
    if b"#EXTM3U" in body:
        return True, "manifest_ok", "hls_manifest_ok"
    if BLOCKED_RE.search(text_sample):
        return False, "blocked", "blocked_page_signature"
    if HTML_RE.search(text_sample):
        return False, "html_not_video", "html_response"
    if body:
        return True, "reachable", lower_type or "non_empty_response"
    return False, "empty_response", "empty_response"


def probe_url(url: str, timeout: float) -> tuple[bool, str, str, int]:
    started = time.monotonic()
    try:
        status, content_type, body = request_url(url, timeout=timeout)
        ok, audit_status, reason = classify_response(url, status, content_type, body)
        elapsed = int((time.monotonic() - started) * 1000)
        return ok, audit_status, reason, elapsed
    except HTTPError as error:
        elapsed = int((time.monotonic() - started) * 1000)
        status = getattr(error, "code", 0) or 0
        try:
            body = error.read(4096)
        except Exception:
            body = b""
        reason = f"http_{status}"
        if BLOCKED_RE.search(body.decode("utf-8", errors="ignore")) or status in {401, 403, 451}:
            return False, "blocked", reason, elapsed
        if status == 404:
            return False, "not_found", reason, elapsed
        return False, "http_error", reason, elapsed
    except (TimeoutError, socket.timeout):
        elapsed = int((time.monotonic() - started) * 1000)
        return False, "timeout", "request_timeout", elapsed
    except (URLError, OSError, ssl.SSLError) as error:
        elapsed = int((time.monotonic() - started) * 1000)
        reason = str(getattr(error, "reason", error))[:160]
        return False, "network_error", reason, elapsed


def local_url_candidates(item: dict[str, Any]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for field, label in (("directUrl", "direct"), ("url", "primary")):
        value = str(item.get(field) or "").strip()
        if value:
            candidates.append((label, value))
    backups = item.get("backup_urls")
    if isinstance(backups, list):
        for index, value in enumerate(backups, start=1):
            url = str(value.get("url") if isinstance(value, dict) else value or "").strip()
            if url:
                candidates.append((f"backup_{index}", url))
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append((label, url))
    return unique


def global_url_candidates(item: dict[str, Any]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for field, label in (("playUrl", "play"), ("embedUrl", "embed"), ("sourceUrl", "source")):
        value = str(item.get(field) or "").strip()
        if value:
            candidates.append((label, value))
    video_id = str(item.get("videoId") or "").strip()
    if video_id:
        candidates.append(("youtube_watch", f"https://www.youtube.com/watch?v={video_id}"))
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for label, url in candidates:
        if url not in seen:
            seen.add(url)
            unique.append((label, url))
    return unique


@dataclass(frozen=True)
class AuditTarget:
    scope: str
    item: dict[str, Any]
    timeout: float


def audit_target(target: AuditTarget) -> tuple[str, dict[str, Any]]:
    item = target.item
    scope = target.scope
    key = camera_key(scope, item)
    candidates = local_url_candidates(item) if scope == "local" else global_url_candidates(item)
    checked_at = utc_stamp()
    base = {
        "checkedAt": checked_at,
        "scope": scope,
        "name": str(item.get("name") or item.get("title") or "")[:160],
        "source": source_of(scope, item),
    }
    if not candidates:
        return key, {**base, "ok": False, "status": "missing_url", "reason": "no_probe_url", "elapsedMs": 0}

    first_failure: dict[str, Any] | None = None
    total_elapsed = 0
    for label, url in candidates:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            result = {"ok": False, "status": "unsupported_url", "reason": parsed.scheme or "missing_scheme", "urlKind": label}
            first_failure = first_failure or result
            continue
        ok, status, reason, elapsed = probe_url(url, target.timeout)
        total_elapsed += elapsed
        if scope == "global" and label in {"source", "youtube_watch"} and status == "html_not_video":
            return key, {
                **base,
                "ok": True,
                "status": "source_page_ok",
                "reason": "source_html_page_reachable",
                "urlKind": label,
                "elapsedMs": total_elapsed,
            }
        if ok:
            audit_status = "fallback_ok" if label.startswith("backup_") else status
            if scope == "global" and label in {"source", "youtube_watch"} and not item.get("playUrl"):
                audit_status = "source_page_ok"
            return key, {
                **base,
                "ok": True,
                "status": audit_status,
                "reason": reason,
                "urlKind": label,
                "elapsedMs": total_elapsed,
            }
        failure = {"ok": False, "status": status, "reason": reason, "urlKind": label, "elapsedMs": elapsed}
        first_failure = first_failure or failure

    failure = first_failure or {"ok": False, "status": "probe_failed", "reason": "all_candidates_failed", "elapsedMs": 0}
    return key, {**base, **failure, "elapsedMs": total_elapsed or int(failure.get("elapsedMs") or 0)}


def summarize_scope(
    scope: str,
    all_items: list[dict[str, Any]],
    selected_count: int,
    state_items: dict[str, dict[str, Any]],
    now: dt.datetime,
    window_hours: int,
) -> dict[str, Any]:
    keys = [camera_key(scope, item) for item in all_items]
    cutoff = now - dt.timedelta(hours=window_hours)
    current_entries = [state_items.get(key) for key in keys if state_items.get(key)]
    covered = [entry for entry in current_entries if (parse_stamp(entry.get("checkedAt")) or dt.datetime.min.replace(tzinfo=dt.timezone.utc)) >= cutoff]
    ok_covered = [entry for entry in covered if is_ok_status(entry)]
    failed_covered = [entry for entry in covered if entry and not is_ok_status(entry)]
    oldest = min((parse_stamp(entry.get("checkedAt")) for entry in current_entries if parse_stamp(entry.get("checkedAt"))), default=None)
    return {
        "total": len(all_items),
        "selectedThisRun": selected_count,
        "checkedEver": len(current_entries),
        "coverageWindowHours": window_hours,
        "coveredInWindow": len(covered),
        "coverageRate": round(len(covered) / len(all_items), 4) if all_items else 1.0,
        "okInWindow": len(ok_covered),
        "failedInWindow": len(failed_covered),
        "oldestCheckedAt": utc_stamp(oldest) if oldest else None,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    now = utc_now()
    local_items = load_json(args.local_data, [])
    if not isinstance(local_items, list):
        raise ValueError(f"{args.local_data} must contain a list")
    global_payload = load_json(args.global_data, {})
    global_items = global_payload.get("items", []) if isinstance(global_payload, dict) else []
    if not isinstance(global_items, list):
        raise ValueError(f"{args.global_data} must contain items[]")

    status_payload = load_json(args.output, {"items": {}})
    state_items = normalize_status_items(status_payload)
    local_budget = args.local_budget if args.local_budget is not None else compute_budget(len(local_items), args.window_hours, args.schedule_hours)
    global_budget = args.global_budget if args.global_budget is not None else compute_budget(len(global_items), args.window_hours, args.schedule_hours)
    selected_local = select_due_items("local", local_items, state_items, local_budget, now)
    selected_global = select_due_items("global", global_items, state_items, global_budget, now)
    targets = [AuditTarget("local", item, args.timeout) for item in selected_local]
    targets.extend(AuditTarget("global", item, args.timeout) for item in selected_global)

    results: dict[str, dict[str, Any]] = {}
    if targets:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            for key, entry in executor.map(audit_target, targets):
                results[key] = entry

    active_keys = {camera_key("local", item) for item in local_items}
    active_keys.update(camera_key("global", item) for item in global_items)
    next_items = {key: value for key, value in state_items.items() if key in active_keys}
    next_items.update(results)

    next_payload = {
        "generatedAt": utc_stamp(now),
        "policy": {
            "name": "48h-rotating-broadcast-audit",
            "windowHours": args.window_hours,
            "scheduleHours": args.schedule_hours,
            "localBudget": local_budget,
            "globalBudget": global_budget,
            "workers": args.workers,
            "timeoutSeconds": args.timeout,
            "description": (
                "Every run audits the least-recently checked local/global cameras first, retries local backup URLs, "
                "and records source-only global pages separately from in-app playable HLS/video streams."
            ),
        },
        "summary": {
            "local": summarize_scope("local", local_items, len(selected_local), next_items, now, args.window_hours),
            "global": summarize_scope("global", global_items, len(selected_global), next_items, now, args.window_hours),
            "checkedThisRun": len(results),
            "okThisRun": sum(1 for entry in results.values() if is_ok_status(entry)),
            "failedThisRun": sum(1 for entry in results.values() if not is_ok_status(entry)),
        },
        "statusCountsThisRun": count_statuses(results.values()),
        "items": next_items,
    }
    if not args.dry_run:
        write_json(args.output, next_payload)
    return next_payload


def count_statuses(entries: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-data", type=Path, default=LOCAL_DATA_PATH)
    parser.add_argument("--global-data", type=Path, default=GLOBAL_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_STATUS_PATH)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS)
    parser.add_argument("--schedule-hours", type=int, default=DEFAULT_SCHEDULE_HOURS)
    parser.add_argument("--local-budget", type=int, default=DEFAULT_LOCAL_BUDGET)
    parser.add_argument("--global-budget", type=int, default=DEFAULT_GLOBAL_BUDGET)
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    result = run(args)
    print(json.dumps({"summary": result["summary"], "statusCountsThisRun": result["statusCountsThisRun"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
