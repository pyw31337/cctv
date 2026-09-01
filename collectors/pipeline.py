"""Shared collection pipeline helpers.

This module keeps the merge, dedupe, and recovery rules in one place so the
main collector script can stay thin and the behavior is easier to audit.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Callable, Iterable

import requests

from cctv_runtime import (
    append_query_parameter,
    apply_camera_id_aliases,
    apply_namyangju_golden_mappings,
    camera_identity,
    camera_source_id,
    env_float,
    env_int,
    first_env,
    validate_namyangju_golden_mappings,
    validate_stream_identity,
)

SOURCE_PRIORITY = {
    'KBS': 1,
    'ULLEUNG': 1,
    'NOWJEJU': 1,
    'JEJU': 1,
    'GIGAEYES': 1,
    'YT_CUSTOM': 1,
    'SPATIC': 1,
    'GITS': 2,
    'TOPIS': 2,
    'DAEJEON': 2,
    'ULSAN': 2,
    'DAEGU': 2,
    'SEJONG': 2,
    'GWANGJU': 2,
    'BUSAN_ITS': 3,
    'INCHEON_ITS': 3,
    'DAEJEON_ITS': 3,
    'GANGWON': 3,
    'UTIC': 5,
    'NTIC': 6,
}

DEFAULT_COLLECTION_WORKERS = env_int("CCTV_COLLECTION_WORKERS", 6)
DEFAULT_REFINE_WORKERS = env_int("CCTV_REFINE_INSPECTION_WORKERS", 10)
DEFAULT_REFINE_DELAY_SECONDS = env_float("CCTV_REFINE_INSPECTION_DELAY_SECONDS", 0.05)


def load_existing_data(filepath: str) -> dict[str, dict[str, Any]]:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        normalized_items = [normalize_cctv_record(item) for item in data if isinstance(item, dict)]
        return {item["id"]: item for item in normalized_items if item.get("id")}
    except Exception as exc:
        print(f"Error loading existing data: {exc}")
        return {}


def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlng / 2) ** 2
    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def find_duplicate_index(new_item: dict[str, Any], existing_items: list[dict[str, Any]]) -> int:
    try:
        nlat = float(new_item["lat"])
        nlng = float(new_item["lng"])
        nid = camera_source_id(new_item)
        nsource = str(new_item.get("source", "")).upper()
        nkey = camera_identity(new_item)

        for idx, existing in enumerate(existing_items):
            if camera_identity(existing) == nkey:
                return idx

            ex_source = str(existing.get("source", "")).upper()
            ex_id = camera_source_id(existing)
            if nsource == ex_source and nid and ex_id and nid != ex_id:
                continue

            elat = float(existing["lat"])
            elng = float(existing["lng"])
            if abs(nlat - elat) > 0.002 or abs(nlng - elng) > 0.002:
                continue
            if _distance_meters(nlat, nlng, elat, elng) < 200:
                return idx
    except Exception:
        return -1
    return -1


def _backup_entry(item: dict[str, Any]) -> dict[str, Any]:
    backup = {"source": item.get("source"), "url": item.get("url")}
    original_id = camera_source_id(item)
    if original_id:
        backup["original_id"] = original_id
    if item.get("id"):
        backup["id"] = item["id"]
    return backup


def _copy_main_fields(existing: dict[str, Any], new_item: dict[str, Any]) -> None:
    for key in (
        "id",
        "canonical_id",
        "original_id",
        "source_id",
        "name",
        "lat",
        "lng",
        "url",
        "source",
        "status",
        "address",
        "aspectRatio",
    ):
        if key in new_item and new_item[key] is not None:
            existing[key] = new_item[key]


def normalize_cctv_record(item: dict[str, Any]) -> dict[str, Any]:
    """Return a camera record with stable identity fields filled in."""

    normalized = dict(item or {})
    source = str(normalized.get("source") or "").strip().upper()
    if source:
        normalized["source"] = source

    source_id = camera_source_id(normalized)
    if source_id and not normalized.get("source_id"):
        normalized["source_id"] = source_id
    if source_id and not normalized.get("original_id"):
        normalized["original_id"] = source_id

    canonical_id = normalized.get("canonical_id") or camera_identity(normalized)
    if canonical_id:
        normalized["canonical_id"] = canonical_id

    if not normalized.get("id"):
        normalized["id"] = canonical_id or source_id or normalized.get("name") or "camera"

    backup_urls = normalized.get("backup_urls")
    normalized["backup_urls"] = backup_urls if isinstance(backup_urls, list) else []
    return normalized


def merge_cctv_item(
    target_list: list[dict[str, Any]],
    new_item: dict[str, Any],
    priority_map: dict[str, int] | None = None,
) -> str:
    """Merge a single camera record into target_list."""

    priority_map = priority_map or SOURCE_PRIORITY
    new_item = normalize_cctv_record(new_item)

    idx = find_duplicate_index(new_item, target_list)
    if idx == -1:
        target_list.append(new_item)
        return "added"

    existing = normalize_cctv_record(target_list[idx])
    target_list[idx] = existing

    p_new = priority_map.get(str(new_item.get("source")), 99)
    p_old = priority_map.get(str(existing.get("source")), 99)

    is_better = False
    if p_new < p_old:
        is_better = True
    elif p_new == p_old:
        new_is_direct = ".m3u8" in str(new_item.get("url", "")).lower()
        old_is_direct = ".m3u8" in str(existing.get("url", "")).lower()
        if new_is_direct and not old_is_direct:
            is_better = True

    existing_urls = [backup.get("url") for backup in existing["backup_urls"]] + [existing.get("url")]
    if new_item.get("url") in existing_urls:
        return "skipped_duplicate_url"

    if is_better:
        existing["backup_urls"].append(_backup_entry(existing))
        _copy_main_fields(existing, new_item)
        if new_item["backup_urls"]:
            existing["backup_urls"].extend(new_item["backup_urls"])
        return "upgraded"

    existing["backup_urls"].append(_backup_entry(new_item))
    return "added_backup"


def collect_in_parallel(
    tasks: Iterable[tuple[str, Callable[[], Any]]],
    *,
    label: str = "collector",
    max_workers: int | None = None,
) -> dict[str, Any]:
    """Run independent collectors concurrently and keep failures isolated."""

    task_list = list(tasks)
    if not task_list:
        return {}

    worker_count = max_workers or min(DEFAULT_COLLECTION_WORKERS, len(task_list))
    results: dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_map = {
            executor.submit(fetcher): name
            for name, fetcher in task_list
        }
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception as exc:
                print(f"[WARNING] {label} {name} failed: {exc}")
                results[name] = []
    return results


def merge_named_batches(
    target_list: list[dict[str, Any]],
    batches: Iterable[tuple[str, Iterable[dict[str, Any]]]],
    *,
    priority_map: dict[str, int] | None = None,
) -> dict[str, dict[str, int]]:
    """Merge multiple named batches and return per-batch stats."""

    priority_map = priority_map or SOURCE_PRIORITY
    stats_by_name: dict[str, dict[str, int]] = {}
    for name, data in batches:
        stats = {"added": 0, "upgraded": 0, "added_backup": 0, "skipped": 0, "skipped_duplicate_url": 0}
        for item in data or []:
            result = merge_cctv_item(target_list, item, priority_map=priority_map)
            stats[result] = stats.get(result, 0) + 1
        stats_by_name[name] = stats
        print(f"Merged {name}: {stats}")
    return stats_by_name


def refine_cctv_data(
    cctv_list: list[dict[str, Any]],
    *,
    max_workers: int | None = None,
    delay_seconds: float | None = None,
) -> list[dict[str, Any]]:
    """Resolve direct stream URLs for wrapper pages and unstable endpoints."""

    if not cctv_list:
        return cctv_list

    print(f"Refining {len(cctv_list)} items for Deep Inspection...")
    optimized_count = 0
    for item in cctv_list:
        url = item.get("url", "")
        if item.get("source") == "UTIC" and "jsp" in url:
            if "cctvip=210.95.12.126" in url or "cctvip=211.114.87.164" in url:
                match = re.search(r"[?&]id=([^&]+)", url)
                if match:
                    real_id = match.group(1)
                    ip = "210.95.12.126" if "cctvip=210.95.12.126" in url else "211.114.87.164"
                    item["url"] = f"http://{ip}/media/{real_id}/chunklist.m3u8"
                    optimized_count += 1

    print(f"Direct Pattern Optimization applied to {optimized_count} items (Instant).")

    targets = [
        item for item in cctv_list
        if item.get("source") == "UTIC"
        and ("openDataCctvStream.jsp" in item.get("url", "") or "cctvPopup.do" in item.get("url", ""))
    ]
    print(f"Found {len(targets)} items needing Deep Inspection (JSP wrapper/HRFCO).")
    if not targets:
        return cctv_list

    worker_count = max_workers or min(DEFAULT_REFINE_WORKERS, len(targets))
    sleep_seconds = DEFAULT_REFINE_DELAY_SECONDS if delay_seconds is None else delay_seconds

    def inspect_item(item: dict[str, Any]) -> bool:
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        url = item["url"]
        try:
            request_url = url
            if item.get("source") == "UTIC":
                utic_key = first_env("UTIC_API_KEY", "UTIC_KEY")
                if utic_key:
                    request_url = append_query_parameter(url, "key", utic_key)
            resp = requests.get(request_url, timeout=4, verify=False)
            if resp.status_code != 200:
                return False

            html = resp.text
            patterns = [
                r'src="([^"]+\.m3u8[^"]*)"',
                r'src="([^"]+\.mp4[^"]*)"',
                r'source\s+src="([^"]+)"\s+type="application/x-mpegURL"',
                r'var\s+[lh]url\s*=\s*"([^"]+)"',
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    new_url = match.group(1)
                    if new_url.startswith("http"):
                        item["url"] = new_url
                        return True
        except Exception:
            return False
        return False

    print(f"Starting concurrent inspection of {len(targets)} items...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        modified_count = sum(executor.map(inspect_item, targets))

    print(f"Deep Inspection completed. Optimized {modified_count} URLs.")
    return cctv_list


def preserve_direct_urls(
    items: list[dict[str, Any]],
    existing_data_map: dict[str, dict[str, Any]],
) -> int:
    preserved_count = 0
    for item in items:
        item_id = item.get("id")
        if not item_id or item_id not in existing_data_map:
            continue
        existing = existing_data_map[item_id]
        if "directUrl" in existing and "directUrl" not in item:
            item["directUrl"] = existing["directUrl"]
            preserved_count += 1
    return preserved_count


def rename_multiview_cameras(items: list[dict[str, Any]]) -> int:
    name_loc_map: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = {}
    for item in items:
        key = (item.get("name"), item.get("lat"), item.get("lng"))
        name_loc_map.setdefault(key, []).append(item)

    renamed_count = 0
    for _, group in name_loc_map.items():
        if len(group) <= 1:
            continue
        for idx, item in enumerate(group, 1):
            item["name"] = f"{item['name']} ({idx})"
            renamed_count += 1
    return renamed_count


def apply_golden_overrides(
    items: list[dict[str, Any]],
    override_file: str = "cctv_overrides.json",
) -> int:
    if not os.path.exists(override_file):
        return 0

    print(f"Applying final authority from {override_file}...")
    try:
        with open(override_file, "r", encoding="utf-8") as f:
            overrides = json.load(f)
        override_map = {item["id"]: item for item in overrides if isinstance(item, dict) and item.get("id")}

        override_count = 0
        for item in items:
            if item.get("id") not in override_map:
                continue
            ovr = override_map[item["id"]]
            for key in ("url", "name", "aspectRatio", "status", "lat", "lng", "address", "canonical_id", "original_id", "source_id"):
                if key in ovr:
                    item[key] = ovr[key]
            override_count += 1
        print(f"Safeguard: Applied {override_count} golden overrides.")
        return override_count
    except Exception as exc:
        print(f"Warning: Failed to apply golden overrides: {exc}")
        return 0


def finalize_cctv_records(
    items: list[dict[str, Any]],
    *,
    priority_map: dict[str, int] | None = None,
    override_file: str = "cctv_overrides.json",
) -> list[dict[str, Any]]:
    priority_map = priority_map or SOURCE_PRIORITY
    print("Running final sorting...")
    items[:] = [normalize_cctv_record(item) for item in items]
    apply_camera_id_aliases(items)
    items.sort(key=lambda x: (priority_map.get(x.get("source"), 99), x.get("id", "")))

    unique_items: list[dict[str, Any]] = []
    seen = set()
    for item in items:
        identity = camera_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        unique_items.append(item)

    print("Renaming cameras with same name and location (multi-view)...")
    renamed_count = rename_multiview_cameras(unique_items)
    print(f"Renaming Pass: Applied suffixes to {renamed_count} cameras.")

    apply_golden_overrides(unique_items, override_file=override_file)
    apply_namyangju_golden_mappings(unique_items)
    mapping_errors = validate_namyangju_golden_mappings(unique_items)
    if mapping_errors:
        raise ValueError("Golden stream mapping validation failed: " + "; ".join(mapping_errors))
    identity_errors = validate_stream_identity(unique_items)
    if identity_errors:
        raise ValueError("Stream identity validation failed: " + "; ".join(identity_errors))
    return unique_items
