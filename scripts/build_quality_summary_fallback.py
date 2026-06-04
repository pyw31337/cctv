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
from urllib.parse import urlparse
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "cctv_data.json"
CANARY_FILE = ROOT / "data" / "canary_status.json"
OPS_FILE = ROOT / "data" / "ops_status.json"
STATUS_FILE = ROOT / "data" / "status.json"
OUTPUT_FILE = ROOT / "data" / "quality_summary.json"
SOURCE_ONLY_CATEGORIES = {"frame_only", "frame_or_bad_content", "html_or_frame"}
SOURCE_ONLY_REASONS = {"iframe_only_source", "html_not_direct_video"}
SOURCE_ONLY_SOURCES = {"GANGWON", "GIGAEYES", "KNPS", "CCTVWORLD"}
MONITOR_UNVERIFIED_SOURCES = {"SPATIC", "ULSAN"}
MONITOR_UNVERIFIED_HOSTS = {"trafficcctv.paju.go.kr", "strm1.spatic.go.kr", "strm2.spatic.go.kr", "strm3.spatic.go.kr", "strm4.spatic.go.kr", "webcctv.its.ulsan.kr"}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def latest_stamp(*values: Any) -> str:
    stamps = [str(value) for value in values if value]
    return max(stamps) if stamps else utc_stamp()


def is_source_only_evidence(source: str, category: Any, reason: Any) -> bool:
    category_text = str(category or "")
    reason_text = str(reason or "")
    return (
        category_text in SOURCE_ONLY_CATEGORIES
        or reason_text in SOURCE_ONLY_REASONS
        or (source in SOURCE_ONLY_SOURCES and category_text in {"unknown", "not_checked"})
    )


def is_monitor_unverified_evidence(source: str, category: Any, reason: Any, url: Any) -> bool:
    if str(category or "") != "timeout" and str(reason or "") != "timeout":
        return False
    parsed = urlparse(str(url or ""))
    if not parsed.scheme.startswith("http"):
        return False
    if not str(parsed.path or "").lower().endswith(".m3u8"):
        return False
    return source in MONITOR_UNVERIFIED_SOURCES or parsed.netloc.lower() in MONITOR_UNVERIFIED_HOSTS


def row_from_result(result: dict[str, Any], region_label: str) -> dict[str, Any]:
    ok = bool(result.get("ok"))
    elapsed = int(result.get("elapsed_ms") or 0)
    samples = 1
    source = str(result.get("source") or "UNKNOWN")
    source_only = (not ok) and is_source_only_evidence(source, result.get("category"), result.get("reason"))
    monitor_unverified = (not ok) and is_monitor_unverified_evidence(source, result.get("category"), result.get("reason"), result.get("url"))
    failure = 0 if ok or source_only or monitor_unverified else 1
    return {
        "camera_name": result.get("name") or result.get("id") or "UNKNOWN",
        "source": source,
        "region": region_label,
        "samples": samples,
        "success": 1 if ok else 0,
        "failure": failure,
        "slow": 1 if ok and elapsed >= 8000 else 0,
        "fallback": 0,
        "source_only": 1 if source_only else 0,
        "monitor_unverified": 1 if monitor_unverified else 0,
        "direct_playable_samples": 0 if source_only or monitor_unverified else 1,
        "success_rate": 1 if ok else 0,
        "failure_rate": failure / samples if samples else 0,
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
    category = (failed_sample or {}).get("category")
    reason = (failed_sample or {}).get("reason")
    source_only = (not ok) and is_source_only_evidence(source, category, reason)
    monitor_unverified = (not ok) and is_monitor_unverified_evidence(source, category, reason, (failed_sample or {}).get("url") or (cam or {}).get("url") or (cam or {}).get("directUrl"))
    failure = 0 if ok or source_only or monitor_unverified else 1
    return {
        "camera_name": name,
        "source": source,
        "region": region_key,
        "samples": 1,
        "success": 1 if ok else 0,
        "failure": failure,
        "slow": 0,
        "fallback": 0,
        "source_only": 1 if source_only else 0,
        "monitor_unverified": 1 if monitor_unverified else 0,
        "direct_playable_samples": 0 if source_only or monitor_unverified else 1,
        "success_rate": 1 if ok else 0,
        "failure_rate": failure / 1,
        "slow_rate": 0,
        "fallback_rate": 0,
        "avg_first_frame_ms": elapsed if ok else 0,
        "avg_fail_ms": 0 if ok else elapsed,
        "avg_width": 0,
        "avg_height": 0,
        "updated_at": checked_at,
        "quality_basis": "regional_health_sample",
        "reason": (failed_sample or {}).get("reason"),
        "category": category,
        "recommended_action": (((failed_sample or {}).get("diagnosis") or {}).get("recommended_action") or ((region.get("failure_breakdown") or {}).get("dominant") or {}).get("recommended_action")),
    }


def row_from_check_registry(
    camera_id: str,
    entry: dict[str, Any],
    cam: dict[str, Any] | None,
) -> dict[str, Any]:
    ok = bool(entry.get("last_ok"))
    source = str(entry.get("source") or (cam or {}).get("source") or "UNKNOWN")
    region_key = str(entry.get("region") or source_region_from_camera(cam or {}))
    name = entry.get("name") or (cam or {}).get("name") or camera_id
    category = entry.get("last_category")
    reason = entry.get("last_reason")
    source_only = (not ok) and is_source_only_evidence(source, category, reason)
    monitor_unverified = (not ok) and is_monitor_unverified_evidence(
        source,
        category,
        reason,
        entry.get("last_url") or (cam or {}).get("url") or (cam or {}).get("directUrl"),
    )
    failure = 0 if ok or source_only or monitor_unverified else 1
    return {
        "camera_name": name,
        "source": source,
        "region": region_key,
        "samples": 1,
        "success": 1 if ok else 0,
        "failure": failure,
        "slow": 0,
        "fallback": 0,
        "source_only": 1 if source_only else 0,
        "monitor_unverified": 1 if monitor_unverified else 0,
        "direct_playable_samples": 0 if source_only or monitor_unverified else 1,
        "success_rate": 1 if ok else 0,
        "failure_rate": failure / 1,
        "slow_rate": 0,
        "fallback_rate": 0,
        "avg_first_frame_ms": 0,
        "avg_fail_ms": 0,
        "avg_width": 0,
        "avg_height": 0,
        "updated_at": entry.get("last_checked_at"),
        "quality_basis": "cumulative_camera_check_registry",
        "reason": reason,
        "category": category,
        "recommended_action": entry.get("recommended_action"),
    }


def add_rollup(bucket: dict[str, Any], row: dict[str, Any]) -> None:
    bucket["samples"] += int(row.get("samples") or 0)
    bucket["success"] += int(row.get("success") or 0)
    bucket["failure"] += int(row.get("failure") or 0)
    bucket["slow"] += int(row.get("slow") or 0)
    bucket["fallback"] += int(row.get("fallback") or 0)
    bucket["source_only"] += int(row.get("source_only") or 0)
    bucket["monitor_unverified"] += int(row.get("monitor_unverified") or 0)
    bucket["direct_playable_samples"] += int(row.get("direct_playable_samples") or 0)
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
    source_only = int(bucket.get("source_only") or 0)
    monitor_unverified = int(bucket.get("monitor_unverified") or 0)
    direct_playable_samples = int(bucket.get("direct_playable_samples") or max(0, samples - source_only - monitor_unverified))
    direct_success_rate = success / direct_playable_samples if direct_playable_samples else None
    return {
        "samples": samples,
        "success": success,
        "failure": failure,
        "slow": slow,
        "fallback": fallback,
        "source_only": source_only,
        "monitor_unverified": monitor_unverified,
        "direct_playable_samples": direct_playable_samples,
        "success_rate": success / samples if samples else 0,
        "direct_success_rate": direct_success_rate,
        "source_only_rate": source_only / samples if samples else 0,
        "monitor_unverified_rate": monitor_unverified / samples if samples else 0,
        "failure_rate": failure / direct_playable_samples if direct_playable_samples else 0,
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

    # The regional sample above represents the current run. The status file also
    # keeps a cumulative camera_checks registry, which is the source of truth for
    # catalog coverage. Include it so the dashboard does not under-report quality
    # samples after the checker has already covered most of the catalog.
    for camera_id, entry in (status.get("camera_checks") or {}).items():
        if not isinstance(entry, dict) or camera_id in cameras:
            continue
        row = row_from_check_registry(str(camera_id), entry, catalog_index.get(str(camera_id)))
        cameras[str(camera_id)] = row
        add_rollup(source_buckets[row["source"]], row)
        add_rollup(region_buckets[row["region"]], row)

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

    generated_at = latest_stamp(canary.get("generated_at"), status.get("last_updated"), ops.get("generated_at"))
    payload = {
        "generated_at": generated_at,
        "window_hours": 24,
        "quality_basis": "core_canary_fallback",
        "telemetry_status": "fallback_from_regional_health_and_canary",
        "telemetry_note": "실사용 Worker 요약이 비어 있거나 접근 불가할 때 지역 헬스 샘플 전체와 핵심 카나리 점검 결과로 대시보드를 채웁니다.",
        "service_status": ops.get("service_status"),
        "inventory_total": len(catalog) if isinstance(catalog, list) else 0,
        "status_region_count": len(status.get("regions", {}) or {}),
        "sampling_policy": status.get("sampling_policy") or {},
        "coverage": status.get("coverage") or {},
        "cameras": cameras,
        "sources": {key: finalize_rollup(value) for key, value in source_buckets.items()},
        "regions": {key: finalize_rollup(value) for key, value in region_buckets.items()},
    }
    OUTPUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_FILE} cameras={len(cameras)} sources={len(payload['sources'])} regions={len(payload['regions'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
