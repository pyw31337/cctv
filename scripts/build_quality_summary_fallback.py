#!/usr/bin/env python3
"""Build a non-empty quality_summary.json from canary/ops evidence.

This is a fallback for when the real user telemetry Worker is unavailable or has
not collected samples yet. It deliberately keeps the schema compatible with the
Cloudflare Worker summary so the dashboard/app can render useful quality status
instead of an empty panel.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANARY_FILE = ROOT / "data" / "canary_status.json"
OPS_FILE = ROOT / "data" / "ops_status.json"
OUTPUT_FILE = ROOT / "data" / "quality_summary.json"


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def row_from_result(result: dict[str, Any], region_label: str) -> dict[str, Any]:
    ok = bool(result.get("ok"))
    elapsed = int(result.get("elapsed_ms") or 0)
    samples = 1
    source = str(result.get("source") or "UNKNOWN")
    return {
        "camera_name": result.get("name") or result.get("id") or "UNKNOWN",
        "source": source,
        "region": region_label,
        "samples": samples,
        "success": 1 if ok else 0,
        "failure": 0 if ok else 1,
        "slow": 1 if ok and elapsed >= 8000 else 0,
        "fallback": 0,
        "success_rate": 1 if ok else 0,
        "failure_rate": 0 if ok else 1,
        "slow_rate": 1 if ok and elapsed >= 8000 else 0,
        "fallback_rate": 0,
        "avg_first_frame_ms": elapsed if ok else 0,
        "avg_fail_ms": 0 if ok else elapsed,
        "avg_width": 0,
        "avg_height": 0,
        "updated_at": result.get("checked_at"),
        "quality_basis": "core_canary_fallback",
        "reason": result.get("reason"),
        "category": result.get("category"),
    }


def add_rollup(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["samples"] += int(row.get("samples") or 0)
    bucket["success"] += int(row.get("success") or 0)
    bucket["failure"] += int(row.get("failure") or 0)
    bucket["slow"] += int(row.get("slow") or 0)
    bucket["fallback"] += int(row.get("fallback") or 0)
    bucket["first_frame_sum"] += int(row.get("avg_first_frame_ms") or 0) * int(row.get("success") or 0)
    bucket["fail_sum"] += int(row.get("avg_fail_ms") or 0) * int(row.get("failure") or 0)
    updated = row.get("updated_at")
    if updated and (not bucket.get("updated_at") or str(updated) > str(bucket.get("updated_at"))):
        bucket["updated_at"] = updated


def finalize_rollup(bucket: dict[str, Any]) -> dict[str, Any]:
    samples = int(bucket.get("samples") or 0)
    success = int(bucket.get("success") or 0)
    failure = int(bucket.get("failure") or 0)
    slow = int(bucket.get("slow") or 0)
    fallback = int(bucket.get("fallback") or 0)
    return {
        "samples": samples,
        "success": success,
        "failure": failure,
        "slow": slow,
        "fallback": fallback,
        "success_rate": success / samples if samples else 0,
        "failure_rate": failure / samples if samples else 0,
        "slow_rate": slow / samples if samples else 0,
        "fallback_rate": fallback / samples if samples else 0,
        "avg_first_frame_ms": bucket.get("first_frame_sum", 0) / success if success else 0,
        "avg_fail_ms": bucket.get("fail_sum", 0) / failure if failure else 0,
        "avg_width": 0,
        "avg_height": 0,
        "updated_at": bucket.get("updated_at"),
        "quality_basis": "core_canary_fallback",
    }


def main() -> int:
    canary = load_json(CANARY_FILE, {})
    ops = load_json(OPS_FILE, {})
    cameras: dict[str, Any] = {}
    source_buckets: dict[str, Any] = defaultdict(lambda: defaultdict(int))
    region_buckets: dict[str, Any] = defaultdict(lambda: defaultdict(int))

    for region in (canary.get("regions") or {}).values():
        region_label = region.get("label") or region.get("key") or "UNKNOWN"
        for result in region.get("results") or []:
            camera_id = str(result.get("id") or "")
            if not camera_id:
                continue
            row = row_from_result(result, region_label)
            cameras[camera_id] = row
            add_rollup(source_buckets[row["source"]], row)
            add_rollup(region_buckets[region_label], row)

    payload = {
        "generated_at": canary.get("generated_at") or utc_stamp(),
        "window_hours": 24,
        "quality_basis": "core_canary_fallback",
        "telemetry_status": "fallback_from_canary",
        "telemetry_note": "실사용 Worker 요약이 비어 있거나 접근 불가할 때 카나리 점검 결과로 대시보드를 채웁니다.",
        "service_status": ops.get("service_status"),
        "cameras": cameras,
        "sources": {key: finalize_rollup(value) for key, value in source_buckets.items()},
        "regions": {key: finalize_rollup(value) for key, value in region_buckets.items()},
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_FILE} cameras={len(cameras)} sources={len(payload['sources'])} regions={len(payload['regions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
