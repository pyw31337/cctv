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
DATA_FILE = ROOT / "cctv_data.json"
CANARY_FILE = ROOT / "data" / "canary_status.json"
OPS_FILE = ROOT / "data" / "ops_status.json"
STATUS_FILE = ROOT / "data" / "status.json"
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
        "recommended_action": result.get("recommended_action"),
    }


def camera_index(cameras: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in cameras if item.get("id")}


def source_region_from_camera(cam: dict[str, Any]) -> str:
    """Keep this coarse; dashboard inventory has the detailed source-region view."""
    source = str(cam.get("source") or "UNKNOWN")
    name = str(cam.get("name") or "")
    if source == "UTIC":
        if "kind=Z3" in str(cam.get("url") or cam.get("directUrl") or "") or str(cam.get("kind") or "").upper() == "Z3":
            return "UTIC_Z3"
        if str(cam.get("id") or "").startswith("L"):
            return "UTIC_DIRECT"
        return "UTIC_LEGACY"
    if source == "KBS":
        return "KBS"
    if source == "NTIC":
        return "NTIC"
    if "제주" in name or "서귀포" in name or source == "NOWJEJU":
        return "JEJU"
    return source


def row_from_status_sample(
    camera_id: str,
    cam: dict[str, Any] | None,
    region_key: str,
    region: dict[str, Any],
    failed_sample: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ok = failed_sample is None
    source = str((failed_sample or {}).get("source") or (cam or {}).get("source") or "UNKNOWN")
    name = (failed_sample or {}).get("name") or (cam or {}).get("name") or camera_id
    checked_at = (failed_sample or {}).get("checked_at") or region.get("checked_at")
    elapsed = int((failed_sample or {}).get("elapsed_ms") or 0)
    return {
        "camera_name": name,
        "source": source,
        "region": region_key,
        "samples": 1,
        "success": 1 if ok else 0,
        "failure": 0 if ok else 1,
        "slow": 0,
        "fallback": 0,
        "success_rate": 1 if ok else 0,
        "failure_rate": 0 if ok else 1,
        "slow_rate": 0,
        "fallback_rate": 0,
        "avg_first_frame_ms": elapsed if ok else 0,
        "avg_fail_ms": 0 if ok else elapsed,
        "avg_width": 0,
        "avg_height": 0,
        "updated_at": checked_at,
        "quality_basis": "regional_health_sample",
        "reason": (failed_sample or {}).get("reason"),
        "category": (failed_sample or {}).get("category"),
        "recommended_action": (((failed_sample or {}).get("diagnosis") or {}).get("recommended_action") or ((region.get("failure_breakdown") or {}).get("dominant") or {}).get("recommended_action")),
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
    catalog = load_json(DATA_FILE, [])
    canary = load_json(CANARY_FILE, {})
    ops = load_json(OPS_FILE, {})
    status = load_json(STATUS_FILE, {})
    catalog_index = camera_index(catalog if isinstance(catalog, list) else [])
    cameras: dict[str, Any] = {}
    source_buckets: dict[str, Any] = defaultdict(lambda: defaultdict(int))
    region_buckets: dict[str, Any] = defaultdict(lambda: defaultdict(int))

    for region_key, region in (status.get("regions") or {}).items():
        if not isinstance(region, dict):
            continue
        failed_by_id = {str(item.get("id")): item for item in (region.get("failed_samples") or []) if isinstance(item, dict) and item.get("id")}
        sample_ids = [str(item) for item in (region.get("sample_ids") or []) if item]
        if not sample_ids:
            sample_ids = [str(item) for item in (region.get("passed_ids") or []) if item] + list(failed_by_id.keys())
        for camera_id in sample_ids:
            row = row_from_status_sample(camera_id, catalog_index.get(camera_id), region_key, region, failed_by_id.get(camera_id))
            cameras[camera_id] = row
            add_rollup(source_buckets[row["source"]], row)
            add_rollup(region_buckets[region_key], row)

    for region in (canary.get("regions") or {}).values():
        region_label = region.get("label") or region.get("key") or "UNKNOWN"
        for result in region.get("results") or []:
            camera_id = str(result.get("id") or "")
            if not camera_id:
                continue
            if camera_id in cameras and cameras[camera_id].get("quality_basis") == "regional_health_sample":
                # Regional health covers all sources/regions. Keep it as the broad
                # dashboard baseline; canary remains visible in canary_status.json.
                continue
            row = row_from_result(result, region_label)
            cameras[camera_id] = row
            add_rollup(source_buckets[row["source"]], row)
            add_rollup(region_buckets[region_label], row)

    payload = {
        "generated_at": canary.get("generated_at") or utc_stamp(),
        "window_hours": 24,
        "quality_basis": "core_canary_fallback",
        "telemetry_status": "fallback_from_regional_health_and_canary",
        "telemetry_note": "실사용 Worker 요약이 비어 있거나 접근 불가할 때 지역 헬스 샘플 전체와 핵심 카나리 점검 결과로 대시보드를 채웁니다.",
        "service_status": ops.get("service_status"),
        "inventory_total": len(catalog) if isinstance(catalog, list) else 0,
        "status_region_count": len(status.get("regions", {}) or {}),
        "cameras": cameras,
        "sources": {key: finalize_rollup(value) for key, value in source_buckets.items()},
        "regions": {key: finalize_rollup(value) for key, value in region_buckets.items()},
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_FILE} cameras={len(cameras)} sources={len(payload['sources'])} regions={len(payload['regions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
