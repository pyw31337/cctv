#!/usr/bin/env python3
"""Adaptive scheduler for CCTV catalog refresh jobs.

The scheduler intentionally separates *when a source should be checked* from
the collector implementation. It learns from the previous run's changed
records and failures, while keeping hard minimum and maximum intervals so a
source can never be abandoned indefinitely.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cctv_runtime import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "cctv_data.json"
DEFAULT_STATE = ROOT / "data" / "collection_schedule.json"
DEFAULT_QUALITY = ROOT / "data" / "quality_summary.json"
SCHEMA_VERSION = 1

TASKS = {
    "gits_ingest": {"base_hours": 12, "min_hours": 3, "max_hours": 36, "source": "GITS"},
    "utic_renew": {"base_hours": 24, "min_hours": 6, "max_hours": 96, "source": "UTIC"},
    "full_refresh": {"base_hours": 168, "min_hours": 48, "max_hours": 336, "source": "*"},
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def snapshot(data: list[dict[str, Any]], source: str) -> dict[str, Any]:
    selected = [item for item in data if source == "*" or item.get("source") == source]
    fingerprints = {
        str(item.get("id")): {
            "url": item.get("url") or item.get("directUrl") or "",
            "name": item.get("name") or "",
            "lat": item.get("lat"),
            "lng": item.get("lng"),
        }
        for item in selected
        if item.get("id")
    }
    return {"count": len(selected), "fingerprints": fingerprints}


def change_rate(previous: dict[str, Any], current: dict[str, Any]) -> float:
    old = previous.get("fingerprints") or {}
    new = current.get("fingerprints") or {}
    if not new:
        return 1.0 if old else 0.0
    changed = sum(1 for key, value in new.items() if old.get(key) != value)
    changed += len(set(old) - set(new))
    return min(1.0, changed / max(len(old), len(new), 1))


def source_failure_rate(data: list[dict[str, Any]], source: str) -> float:
    selected = [item for item in data if source == "*" or item.get("source") == source]
    if not selected:
        return 0.0
    failed = sum(
        1
        for item in selected
        if str(item.get("status") or "").lower() in {"manual_check", "disabled", "inactive", "broken"}
    )
    return failed / len(selected)


def source_quality_signal(quality: dict[str, Any], source: str) -> dict[str, float]:
    """Return telemetry pressure with a sample-size confidence discount."""
    row = (quality.get("sources") or {}).get(source) if isinstance(quality, dict) else None
    if not isinstance(row, dict):
        return {"samples": 0.0, "failure_rate": 0.0, "slow_rate": 0.0, "first_frame_ms": 0.0, "confidence": 0.0}
    samples = max(0.0, float(row.get("samples") or 0))
    confidence = min(1.0, samples / 30.0)
    return {
        "samples": samples,
        "failure_rate": max(0.0, min(1.0, float(row.get("failure_rate") or 0))),
        "slow_rate": max(0.0, min(1.0, float(row.get("slow_rate") or 0))),
        "first_frame_ms": max(0.0, float(row.get("avg_first_frame_ms") or 0)),
        "confidence": confidence,
    }


def browser_grid_signal(quality: dict[str, Any]) -> dict[str, float]:
    """Summarize scheduled real-browser 4-panel health with sample confidence."""
    report = quality.get("browser_canary") if isinstance(quality, dict) else None
    summary = report.get("summary") if isinstance(report, dict) else None
    if not isinstance(summary, dict):
        return {"samples": 0.0, "failure_rate": 0.0, "slow_rate": 0.0, "confidence": 0.0}
    samples = max(0.0, float(summary.get("checked") or 0))
    passed = max(0.0, float(summary.get("passed") or 0))
    failure_rate = max(0.0, min(1.0, (samples - passed) / samples)) if samples else 0.0
    results = report.get("results") if isinstance(report, dict) else []
    if not isinstance(results, list):
        results = []
    slow_count = sum(1 for item in results if isinstance(item, dict) and float(item.get("first_frame_ms") or 0) >= 10000)
    slow_rate = slow_count / samples if samples else 0.0
    freshness = 1.0
    generated_at = parse_time(report.get("generated_at")) if isinstance(report, dict) else None
    if generated_at:
        age_hours = max(0.0, (now_utc() - generated_at).total_seconds() / 3600)
        freshness = max(0.0, min(1.0, 1.0 - (age_hours / 36.0)))
    return {
        "samples": samples,
        "failure_rate": failure_rate,
        "slow_rate": max(0.0, min(1.0, slow_rate)),
        "confidence": min(1.0, samples / 4.0) * freshness,
    }


def effective_interval(task: str, record: dict[str, Any], data: list[dict[str, Any]], quality: dict[str, Any] | None = None) -> float:
    config = TASKS[task]
    previous = record.get("last_snapshot") or {}
    current = snapshot(data, config["source"])
    churn = float(record.get("change_rate", change_rate(previous, current)) or 0)
    failures = source_failure_rate(data, config["source"])
    consecutive_failures = int(record.get("consecutive_failures", 0) or 0)
    telemetry = source_quality_signal(quality or {}, config["source"])
    grid = browser_grid_signal(quality or {})
    telemetry_failure = telemetry["failure_rate"]
    if config["source"] == "*":
        telemetry_failure = grid["failure_rate"]
        telemetry["slow_rate"] = grid["slow_rate"]
        telemetry["confidence"] = grid["confidence"]
    observed_failure = failures * (1 - telemetry["confidence"]) + telemetry_failure * telemetry["confidence"]

    # Stable sources may stretch to the cap. Churn, stale failures, and a
    # failed previous run shorten the next interval aggressively. Runtime
    # telemetry is blended only after enough samples exist to avoid reacting to
    # one user's transient Wi-Fi or browser failure.
    multiplier = 1.35 - (churn * 2.0) - (observed_failure * 1.5)
    multiplier -= telemetry["slow_rate"] * telemetry["confidence"] * 0.7
    if telemetry["first_frame_ms"] > 9000:
        multiplier -= 0.35 * telemetry["confidence"]
    elif telemetry["first_frame_ms"] > 6000:
        multiplier -= 0.15 * telemetry["confidence"]
    multiplier -= min(consecutive_failures * 0.25, 1.0)
    multiplier = max(0.25, min(2.0, multiplier))
    return max(config["min_hours"], min(config["max_hours"], config["base_hours"] * multiplier))


def task_status(task: str, state: dict[str, Any], data: list[dict[str, Any]], now: datetime, quality: dict[str, Any] | None = None) -> dict[str, Any]:
    record = dict((state.get("tasks") or {}).get(task) or {})
    interval = effective_interval(task, record, data, quality)
    last_success = parse_time(record.get("last_success_at"))
    last_attempt = parse_time(record.get("last_attempt_at"))
    anchor = last_success or last_attempt
    age_hours = (now - anchor).total_seconds() / 3600 if anchor else math.inf
    due = anchor is None or age_hours >= interval
    telemetry = source_quality_signal(quality or {}, TASKS[task]["source"])
    if TASKS[task]["source"] == "*":
        telemetry = browser_grid_signal(quality or {})
    return {
        "task": task,
        "due": due,
        "interval_hours": round(interval, 2),
        "age_hours": round(age_hours, 2) if math.isfinite(age_hours) else None,
        "consecutive_failures": int(record.get("consecutive_failures", 0) or 0),
        "change_rate": round(float(record.get("change_rate", 0) or 0), 4),
        "failure_rate": round(source_failure_rate(data, TASKS[task]["source"]), 4),
        "telemetry": telemetry,
    }


def plan(args: argparse.Namespace) -> int:
    data = load_json(Path(args.data), [])
    if not isinstance(data, list):
        raise SystemExit(f"{args.data} must contain a JSON list")
    state = load_json(Path(args.state), {"version": SCHEMA_VERSION, "tasks": {}})
    quality = load_json(Path(args.quality), {})
    now = now_utc()
    statuses = [task_status(task, state, data, now, quality) for task in TASKS]
    selected = next((item["task"] for item in statuses if item["due"]), "")
    result = {"generated_at": now.isoformat(), "selected_task": selected, "tasks": statuses}
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.github_output:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            for task in TASKS:
                handle.write(f"due_{task}={'true' if any(x['task'] == task and x['due'] for x in statuses) else 'false'}\n")
            handle.write(f"selected_task={selected}\n")
    return 0


def record(args: argparse.Namespace) -> int:
    data_path = Path(args.data)
    state_path = Path(args.state)
    data = load_json(data_path, [])
    state = load_json(state_path, {"version": SCHEMA_VERSION, "tasks": {}})
    state.setdefault("version", SCHEMA_VERSION)
    state.setdefault("tasks", {})
    record = dict(state["tasks"].get(args.task) or {})
    config = TASKS[args.task]
    current = snapshot(data, config["source"])
    previous = record.get("last_snapshot") or {}
    rate = change_rate(previous, current)
    stamp = now_utc().isoformat()
    record.update({"last_attempt_at": stamp, "last_snapshot": current, "change_rate": rate})
    if args.result == "success":
        record.update({"last_success_at": stamp, "consecutive_failures": 0})
    else:
        record["consecutive_failures"] = int(record.get("consecutive_failures", 0) or 0) + 1
    state["tasks"][args.task] = record
    atomic_write_json(state_path, state, sort_keys=False)
    print(json.dumps({"task": args.task, "result": args.result, "change_rate": round(rate, 4)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "record"))
    parser.add_argument("--task", choices=tuple(TASKS))
    parser.add_argument("--result", choices=("success", "failure"))
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--state", default=str(DEFAULT_STATE))
    parser.add_argument("--quality", default=str(DEFAULT_QUALITY))
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()
    if args.command == "plan":
        return plan(args)
    if not args.task or not args.result:
        parser.error("record requires --task and --result")
    return record(args)


if __name__ == "__main__":
    raise SystemExit(main())
