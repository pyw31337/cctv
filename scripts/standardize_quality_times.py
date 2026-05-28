#!/usr/bin/env python3
"""Normalize timestamp metadata for CCTV quality dashboard files.

The dashboard reads multiple JSON snapshots created by different jobs. This
adds a shared `time` object without removing the legacy fields that the app and
older scripts still use.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILES = [
    ROOT / "data" / "status.json",
    ROOT / "data" / "quality_summary.json",
    ROOT / "data" / "z3_cache.json",
    ROOT / "data" / "cache_status.json",
    ROOT / "data" / "canary_status.json",
    ROOT / "data" / "ops_status.json",
    ROOT / "data" / "workflow_status.json",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(dt: datetime | None = None) -> str:
    return (dt or utc_now()).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def first_time(*values: Any) -> str | None:
    for value in values:
        dt = parse_time(value)
        if dt:
            return stamp(dt)
    return None


def max_nested_time(payload: Any, keys=("checked_at", "updated_at", "generated_at", "last_updated", "fetched")) -> str | None:
    found: list[datetime] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys:
                    dt = parse_time(child)
                    if dt:
                        found.append(dt)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return stamp(max(found)) if found else None


def age_minutes(source_time: str | None, now: datetime) -> float | None:
    dt = parse_time(source_time)
    if not dt:
        return None
    return round((now - dt).total_seconds() / 60, 2)


def infer_source_time(path: Path, payload: dict[str, Any]) -> str | None:
    name = path.name
    if name == "status.json":
        return first_time(payload.get("last_updated"), max_nested_time(payload))
    if name == "quality_summary.json":
        return first_time(payload.get("generated_at"), max_nested_time(payload))
    if name == "z3_cache.json":
        return first_time(payload.get("fetched"), payload.get("generated_at"))
    if name == "cache_status.json":
        z3 = payload.get("z3") if isinstance(payload.get("z3"), dict) else {}
        return first_time(z3.get("fetched"), payload.get("generated_at"), max_nested_time(payload))
    if name in {"canary_status.json", "ops_status.json"}:
        return first_time(payload.get("generated_at"), max_nested_time(payload))
    if name == "workflow_status.json":
        events = payload.get("events")
        if isinstance(events, list) and events:
            latest_event = next((event.get("at") for event in reversed(events) if isinstance(event, dict) and event.get("at")), None)
            return first_time(latest_event, payload.get("generated_at"), max_nested_time(payload))
        return first_time(payload.get("generated_at"), max_nested_time(payload))
    return first_time(payload.get("generated_at"), payload.get("last_updated"), max_nested_time(payload))


def normalize_file(path: Path, now: datetime, source: str) -> bool:
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] skip {path}: {exc}")
        return False
    if not isinstance(payload, dict):
        return False

    generated_at = first_time(payload.get("generated_at"), payload.get("last_updated"), payload.get("fetched"), payload.get("_served_at")) or stamp(now)
    source_updated_at = infer_source_time(path, payload) or generated_at
    served_at = first_time(payload.get("_served_at")) or stamp(now)
    time_meta = {
        "generated_at": generated_at,
        "source_updated_at": source_updated_at,
        "served_at": served_at,
        "normalized_at": stamp(now),
        "source_age_minutes_at_normalization": age_minutes(source_updated_at, now),
        "schema": "cctv-quality-time-v1",
        "source": source,
    }
    before = payload.get("time")
    payload["time"] = time_meta
    if not payload.get("generated_at") and path.name not in {"z3_cache.json", "status.json"}:
        payload["generated_at"] = generated_at
    if path.name == "status.json" and not payload.get("last_updated"):
        payload["last_updated"] = source_updated_at
    if before == time_meta:
        return False
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    print(f"[OK] normalized {path.relative_to(ROOT)} source_updated_at={source_updated_at}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path, help="JSON files to normalize. Defaults to dashboard quality files.")
    parser.add_argument("--source", default="manual", help="Normalization caller label.")
    args = parser.parse_args()
    now = utc_now()
    files = args.files or DEFAULT_FILES
    changed = 0
    for file in files:
        path = file if file.is_absolute() else ROOT / file
        if normalize_file(path, now, args.source):
            changed += 1
    print(f"normalized_files={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
