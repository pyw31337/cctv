#!/usr/bin/env python3
"""Guard CCTV data preservation invariants.

Service philosophy:
- Never remove known cameras just because a health probe failed.
- Health probes may mark cameras for review, but the UI should still show them.
- Large count drops are treated as data-loss incidents unless explicitly reviewed.

This script is intentionally lightweight so every data-mutating workflow can run
it before committing results.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DESTRUCTIVE_STATUSES = {"disabled", "inactive", "broken", "deleted", "removed"}
REVIEW_STATUS = "manual_check"
DEFAULT_MIN_COUNT = 10_000
DEFAULT_MAX_DROP_RATIO = 0.03


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_items(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise SystemExit(f"[guard] {path} must contain a JSON list")
    return data


def save_items(path: Path, items: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def normalize_destructive_statuses(items: list[dict]) -> int:
    changed = 0
    now = utc_stamp()
    for item in items:
        status = str(item.get("status") or "").lower()
        if status not in DESTRUCTIVE_STATUSES:
            continue
        reason = (
            item.get("health_reason")
            or item.get("disabled_reason")
            or item.get("status_note")
            or f"legacy_{status}_status"
        )
        item["status"] = REVIEW_STATUS
        item["health_reason"] = reason
        item.setdefault("health_checked_at", item.get("disabled_at") or now)
        item["previous_status"] = status
        item.pop("disabled_reason", None)
        item.pop("disabled_at", None)
        changed += 1
    return changed


def duplicate_ids(items: list[dict]) -> list[str]:
    counts = Counter(str(item.get("id") or "") for item in items)
    return sorted(key for key, count in counts.items() if key and count > 1)


def check_previous(current: list[dict], previous: list[dict], max_drop_ratio: float) -> list[str]:
    errors: list[str] = []
    current_ids = {str(item.get("id") or "") for item in current if item.get("id")}
    previous_ids = {str(item.get("id") or "") for item in previous if item.get("id")}
    if len(current) < len(previous) * (1 - max_drop_ratio):
        errors.append(
            f"camera count dropped too much: {len(previous):,} -> {len(current):,} "
            f"(limit {max_drop_ratio:.1%})"
        )
    lost_ids = previous_ids - current_ids
    if len(lost_ids) > max(25, int(len(previous_ids) * max_drop_ratio)):
        sample = ", ".join(sorted(lost_ids)[:12])
        errors.append(f"too many camera IDs disappeared: {len(lost_ids):,}; sample: {sample}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", default="cctv_data.json", help="CCTV data file to validate")
    parser.add_argument("--previous", help="previous CCTV data file for count/ID drop checks")
    parser.add_argument("--fix-statuses", action="store_true", help="convert destructive statuses to manual_check")
    parser.add_argument("--min-count", type=int, default=DEFAULT_MIN_COUNT)
    parser.add_argument("--max-drop-ratio", type=float, default=DEFAULT_MAX_DROP_RATIO)
    args = parser.parse_args()

    path = Path(args.path)
    items = load_items(path)
    if args.fix_statuses:
        changed = normalize_destructive_statuses(items)
        if changed:
            save_items(path, items)
            print(f"[guard] converted {changed:,} destructive statuses to manual_check")

    status_counts = Counter(str(item.get("status") or "") for item in items)
    source_counts = Counter(str(item.get("source") or "UNKNOWN") for item in items)
    errors: list[str] = []

    if len(items) < args.min_count:
        errors.append(f"camera count below minimum: {len(items):,} < {args.min_count:,}")

    destructive = sum(status_counts.get(status, 0) for status in DESTRUCTIVE_STATUSES)
    if destructive:
        errors.append(f"destructive statuses remain: {dict((s, status_counts[s]) for s in DESTRUCTIVE_STATUSES if status_counts[s])}")

    dupes = duplicate_ids(items)
    if dupes:
        errors.append(f"duplicate ids found: {len(dupes):,}; sample: {', '.join(dupes[:12])}")

    if args.previous:
        previous = load_items(Path(args.previous))
        errors.extend(check_previous(items, previous, args.max_drop_ratio))

    print(f"[guard] total={len(items):,}")
    print(f"[guard] status={dict(status_counts.most_common())}")
    print(f"[guard] top_sources={dict(source_counts.most_common(10))}")

    if errors:
        print("[guard] FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("[guard] OK: dataset preserved; review cameras remain visible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
