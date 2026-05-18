#!/usr/bin/env python3
"""Sample CCTV stream stability by source/pattern.

This is intentionally lightweight: it does not try to prove every camera works.
It finds source families that behave like Daejeon timestamp MP4/HLS paths:
missing recent media, slow manifests, HTML/player-only responses, or resolver
timeouts. Use it for operator triage before changing ranking or collectors.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import socket
import ssl
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "cctv_data.json"
ORACLE_BASE = "https://158.179.194.163.sslip.io"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
TIMEOUT = 4.0

ssl._create_default_https_context = ssl._create_unverified_context


def http_get_headers(url: str, headers: dict[str, str]) -> tuple[int, str]:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.headers.get("Content-Type", "")
    except HTTPError as error:
        return error.code, error.headers.get("Content-Type", "")


def get_url_param(url: str, key: str) -> str | None:
    try:
        values = parse_qs(urlparse(url or "").query).get(key)
        return values[0] if values else None
    except Exception:
        return None


def normalize_daejeon_stream_id(raw_id: str | None) -> str | None:
    raw = str(raw_id or "").strip()
    if not raw:
        return None
    match = re.match(r"DAEJEON_(CCTV\d+)$", raw, re.I)
    if match:
        raw = match.group(1)
    match = re.match(r"CCTV(\d+)$", raw, re.I)
    if match:
        return f"CTV{match.group(1).zfill(4)}"
    match = re.match(r"CTV(\d+)$", raw, re.I)
    if match:
        return f"CTV{match.group(1).zfill(4)}"
    return None


def daejeon_stream_id(item: dict) -> str | None:
    url = item.get("directUrl") or item.get("url") or ""
    for candidate in (
        get_url_param(url, "cctvpasswd"),
        get_url_param(url, "id"),
        item.get("original_id"),
        item.get("id"),
    ):
        stream_id = normalize_daejeon_stream_id(candidate)
        if stream_id:
            return stream_id
    return None


def daejeon_media_path(item: dict, stream_id: str) -> str:
    url = item.get("directUrl") or item.get("url") or ""
    cctvip = str(get_url_param(url, "cctvip") or "")
    if cctvip == "118" or "210.99.67.118" in url:
        return "01"
    if cctvip == "119" or "210.99.67.119" in url:
        return "02"
    match = re.match(r"CTV0*(\d+)$", stream_id, re.I)
    if match:
        return "01" if int(match.group(1)) < 51 else "02"
    return "01"


def infer_region_group(item: dict, source_group: str) -> str:
    source = item.get("source") or source_group
    item_id = str(item.get("id") or "")
    name = str(item.get("name") or "")

    if source in {
        "BUSAN_ITS",
        "DAEGU",
        "GWANGJU",
        "INCHEON_ITS",
        "JEJU",
        "NOWJEJU",
        "SEJONG",
        "TOPIS",
        "ULSAN",
    }:
        return "JEJU" if source == "NOWJEJU" else source
    if source == "GANGWON" or name.startswith("[강릉]") or "강원" in name:
        return "GANGWON"
    if source == "DAEJEON_ITS" or item_id.startswith("E07") or name.startswith("대전시(") or "대전 " in name:
        return "DAEJEON"
    if source == "NTIC":
        return "NTIC"
    if "독도" in name or "울릉" in name:
        return "DOKDO"
    return source_group


def classify_item(item: dict) -> tuple[str, str, str]:
    url = item.get("directUrl") or item.get("url") or ""
    source = item.get("source") or "UNKNOWN"
    kind = get_url_param(url, "kind")

    if source == "UTIC" and kind == "E" and (str(item.get("id", "")).startswith("E07") or daejeon_stream_id(item)):
        return "daejeon_timestamp_mp4", "DAEJEON", "DAEJEON"
    if ".m3u8" in url:
        return "hls_manifest", source, infer_region_group(item, source)
    if "kind=Z3" in url or source == "NTIC":
        return "utic_z3_resolver", source, infer_region_group(item, source)
    if "openDataCctvStream.jsp" in url:
        return "utic_legacy_resolver", source, infer_region_group(item, source)
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube_embed", source, infer_region_group(item, source)
    if "cctv-world.kr" in url or "gangneung_player" in url or "cctvPopup.do" in url:
        return "frame_only", source, infer_region_group(item, source)
    if ".mp4" in url:
        return "mp4_file", source, infer_region_group(item, source)
    return "other", source, infer_region_group(item, source)


def resolve_probe_url(item: dict, pattern: str) -> str | None:
    url = item.get("directUrl") or item.get("url") or ""
    if url and not url.startswith(("http://", "https://")):
        return None
    if pattern == "daejeon_timestamp_mp4":
        stream_id = daejeon_stream_id(item)
        if not stream_id:
            return None
        media_path = daejeon_media_path(item, stream_id)
        # The newest file is often absent. Try the same practical window used by the app.
        now = time.time() + (9 * 60 * 60)
        for offset in (1, 2, 3, 4, 5, 6, 8, 10):
            ts = time.strftime("%Y%m%d.%H%M00", time.gmtime(now - (offset * 60)))
            candidate = f"https://tportal.daejeon.go.kr:37084/{media_path}/media/{stream_id}/{stream_id}_{ts}.000.mp4"
            try:
                status_code, _ = http_get_headers(candidate, {**HEADERS, "Range": "bytes=0-1"})
                if status_code in (200, 206):
                    return candidate
            except (URLError, TimeoutError, socket.timeout):
                continue
        return f"https://tportal.daejeon.go.kr:37084/{media_path}/media/{stream_id}/latest-missing"
    if pattern == "utic_legacy_resolver":
        query = urlparse(url).query
        return f"{ORACLE_BASE}/utic?{query}"
    if pattern == "utic_z3_resolver" and "openDataCctvStream.jsp" in url:
        query = urlparse(url).query
        return f"{ORACLE_BASE}/utic?{query}"
    if pattern == "hls_manifest" and url.startswith(f"{ORACLE_BASE}/proxy?url="):
        return url
    if pattern in ("youtube_embed", "frame_only"):
        return url
    return url


def probe(item: dict) -> dict:
    pattern, source_group, region_group = classify_item(item)
    probe_url = resolve_probe_url(item, pattern)
    started = time.perf_counter()
    result = {
        "id": item.get("id"),
        "name": item.get("name"),
        "source": item.get("source"),
        "source_group": source_group,
        "region_group": region_group,
        "pattern": pattern,
        "ok": False,
        "status_code": None,
        "content_type": None,
        "elapsed_ms": None,
        "reason": "not_checked",
    }
    if not probe_url:
        result["reason"] = "missing_probe_url"
        return result

    try:
        headers = dict(HEADERS)
        if probe_url.endswith(".mp4") or "latest-missing" in probe_url:
            headers["Range"] = "bytes=0-1"
        status_code, content_type = http_get_headers(probe_url, headers)
        result["status_code"] = status_code
        result["content_type"] = content_type
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        content_type = result["content_type"].lower()
        if status_code in (200, 206) and "text/html" not in content_type:
            result["ok"] = True
            result["reason"] = "ok"
        elif "text/html" in content_type:
            result["reason"] = "html_player"
        elif status_code == 404:
            result["reason"] = "not_found_or_segment_missing"
        else:
            result["reason"] = "http_error"
    except (TimeoutError, socket.timeout):
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        result["reason"] = "timeout"
    except URLError as exc:
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000)
        result["reason"] = type(exc.reason).__name__ if hasattr(exc, "reason") else type(exc).__name__
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-per-group", type=int, default=12)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260518)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    random.seed(args.seed)
    items = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for item in items:
        pattern, source_group, region_group = classify_item(item)
        groups[(region_group, source_group, pattern)].append(item)

    sample = []
    for key, values in sorted(groups.items()):
        if len(values) <= args.sample_per_group:
            chosen = values
        else:
            chosen = random.sample(values, args.sample_per_group)
        sample.extend(chosen)

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(probe, item) for item in sample]
        for future in as_completed(futures):
            results.append(future.result())

    summary = {}
    for result in results:
        key = f"{result['region_group']}::{result['source_group']}::{result['pattern']}"
        bucket = summary.setdefault(key, {"total": 0, "ok": 0, "reasons": Counter(), "examples": []})
        bucket["total"] += 1
        bucket["ok"] += int(result["ok"])
        bucket["reasons"][result["reason"]] += 1
        if not result["ok"] and len(bucket["examples"]) < 4:
            bucket["examples"].append(result)

    normalized_summary = {
        key: {
            "total": value["total"],
            "ok": value["ok"],
            "ok_rate": round(value["ok"] / value["total"], 3) if value["total"] else 0,
            "reasons": dict(value["reasons"].most_common()),
            "examples": value["examples"],
        }
        for key, value in sorted(summary.items())
    }

    if args.json:
        print(json.dumps({"summary": normalized_summary, "results": results}, ensure_ascii=False, indent=2))
        return 0

    print("region::source_group::pattern\tok/total\tok_rate\treasons")
    for key, value in normalized_summary.items():
        print(f"{key}\t{value['ok']}/{value['total']}\t{value['ok_rate']:.0%}\t{value['reasons']}")
        for example in value["examples"]:
            print(f"  - {example['id']} {example['name']} :: {example['reason']} {example['status_code']} {example['elapsed_ms']}ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
