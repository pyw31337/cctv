#!/usr/bin/env python3
"""Append a lightweight workflow status event for operator dashboards.

Use this for non-destructive data-source failures that should not delete data or
spam GitHub failure email. True data preservation failures should still fail the
workflow.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

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
    payload = load(path)
    events = payload.get("events") if isinstance(payload.get("events"), list) else []
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
    events.append(event)
    events = events[-200:]
    payload = {
        "generated_at": utc_stamp(),
        "time": {
            "generated_at": utc_stamp(),
            "source_updated_at": event["at"],
        "served_at": utc_stamp(),
        "normalized_at": utc_stamp(),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {path} {event['workflow']} {event['status']} impact={event['impact']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
