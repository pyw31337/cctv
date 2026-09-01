#!/usr/bin/env python3
"""Append a lightweight workflow status event for operator dashboards.

Use this for non-destructive data-source failures that should not delete data or
spam GitHub failure email. True data preservation failures should still fail the
workflow.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from cctv_runtime import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "workflow_status.json"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"events": []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--job", default="")
    parser.add_argument("--status", default="warning", choices=["ok", "warning", "error"])
    parser.add_argument("--impact", default="unknown", choices=["none", "possible", "service", "unknown"])
    parser.add_argument("--message", default="")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    path = args.output if args.output.is_absolute() else ROOT / args.output
    event = {
        "at": utc_stamp(),
        "workflow": args.workflow,
        "job": args.job,
        "status": args.status,
        "impact": args.impact,
        "message": args.message[:800],
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_sha": os.environ.get("GITHUB_SHA"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)

    # Multiple scheduled jobs can report into the same snapshot. Lock the
    # read-modify-write cycle so events are not lost and JSON stays valid.
    lock_path = path.with_name(f".{path.name}.lock")
    with lock_path.open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        payload = load(path)
        events = payload.get("events") if isinstance(payload.get("events"), list) else []
        events = (events + [event])[-200:]
        now = utc_stamp()
        payload = {
            "generated_at": now,
            "time": {
                "generated_at": now,
                "source_updated_at": event["at"],
                "served_at": now,
                "normalized_at": now,
                "source_age_minutes_at_normalization": 0,
                "schema": "cctv-quality-time-v1",
                "source": "workflow-status",
            },
            "summary": {
                "recent_events": len(events),
                "recent_warnings": sum(1 for item in events[-50:] if item.get("status") == "warning"),
                "recent_errors": sum(1 for item in events[-50:] if item.get("status") == "error"),
                "service_impact_events": sum(1 for item in events[-50:] if item.get("impact") == "service"),
            },
            "events": events,
        }
        atomic_write_json(path, payload)
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    print(f"wrote {path} {event['workflow']} {event['status']} impact={event['impact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
