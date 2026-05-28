#!/usr/bin/env python3
"""Probe critical CCTV canary regions and write an operations status snapshot.

The canary policy is intentionally conservative:
- keep all cameras in the catalog;
- classify service impact separately from workflow/process failures;
- prefer real stream/resolver evidence over aggregate region health;
- never fail the GitHub workflow only because an upstream camera is down.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import ssl
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import requests
except Exception:  # pragma: no cover - GitHub runner fallback path
    requests = None

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    urllib3 = None

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "cctv_data.json"
Z3_CACHE_FILE = ROOT / "data" / "z3_cache.json"
CACHE_STATUS_FILE = ROOT / "data" / "cache_status.json"
STATUS_FILE = ROOT / "data" / "status.json"
QUALITY_SUMMARY_FILE = ROOT / "data" / "quality_summary.json"
UTIC_AUDIT_HISTORY_FILE = ROOT / "data" / "utic_audit_history.json"
CANARY_STATUS_FILE = ROOT / "data" / "canary_status.json"
OPS_STATUS_FILE = ROOT / "data" / "ops_status.json"
CANARY_HISTORY_FILE = ROOT / "data" / "canary_history.json"
ORACLE_BASE = "https://158.179.194.163.sslip.io"
Z3_MAX_TRUSTED_AGE_HOURS = 8
DEFAULT_TIMEOUT = (2.5, 6.0)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (cctv-canary/1.0; +https://pyw31337.github.io/cctv/) Chrome/124",
    "Accept": "*/*",
}
SSL_CONTEXT = ssl._create_unverified_context()

CANARY_REGIONS = [
    {
        "key": "jindo",
        "label": "진도",
        "lat": 34.456845,
        "lng": 126.242558,
        "radius_km": 35,
        "keywords": ["진도"],
        "min_ok": 1,
        "max_candidates": 10,
    },
    {
        "key": "jeju",
        "label": "제주",
        "lat": 33.3617,
        "lng": 126.5292,
        "radius_km": 55,
        "keywords": ["제주", "서귀포", "NOWJEJU"],
        "min_ok": 2,
        "max_candidates": 12,
    },
    {
        "key": "daejeon",
        "label": "대전",
        "lat": 36.3504,
        "lng": 127.3845,
        "radius_km": 35,
        "keywords": ["대전", "갑천", "엑스포", "대화JC"],
        "min_ok": 2,
        "max_candidates": 12,
    },
    {
        "key": "guri",
        "label": "구리",
        "lat": 37.5943,
        "lng": 127.1296,
        "radius_km": 12,
        "keywords": ["구리", "수택", "세무서", "돌다리", "왕숙", "교문"],
        "min_ok": 2,
        "max_candidates": 10,
    },
    {
        "key": "namyangju",
        "label": "남양주",
        "lat": 37.6574,
        "lng": 127.2650,
        "radius_km": 28,
        "keywords": ["남양주", "마석", "화도", "평내", "호평", "왕숙"],
        "min_ok": 2,
        "max_candidates": 10,
    },
    {
        "key": "dokdo",
        "label": "독도",
        "lat": 37.23936,
        "lng": 131.8686,
        "radius_km": 120,
        "keywords": ["독도", "울릉"],
        "min_ok": 1,
        "max_candidates": 8,
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except Exception as error:
        print(f"[WARN] failed to load {path}: {error}", file=sys.stderr)
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def url_param(url: str, key: str) -> str | None:
    try:
        values = parse_qs(urlparse(url or "").query).get(key)
        return values[0] if values else None
    except Exception:
        return None


def z3_cctvip(url: str) -> str | None:
    value = url_param(url, "cctvip")
    if value:
        return value
    try:
        parsed = urlparse(url or "")
        if "cctvsec.ktict.co.kr" in parsed.netloc:
            first = parsed.path.strip("/").split("/", 1)[0]
            return first if first.isdigit() else None
    except Exception:
        return None
    return None


def source_of(cam: dict) -> str:
    return str(cam.get("source") or "UNKNOWN")


def camera_url(cam: dict) -> str:
    return str(cam.get("directUrl") or cam.get("url") or "")


def redact_probe_url(url: str) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        safe_path = ""
        if parsed.netloc == "cctvsec.ktict.co.kr" and parts and parts[0].isdigit():
            safe_path = f"/{parts[0]}/…"
        elif parts:
            safe_path = f"/{parts[0]}/…"
        return f"{parsed.scheme}://{parsed.netloc}{safe_path}"
    except Exception:
        return url[:120]


def is_z3_camera(cam: dict) -> bool:
    url = camera_url(cam)
    return url_param(url, "kind") == "Z3" or source_of(cam) == "NTIC" or "kind=Z3" in url


def z3_cache_age_hours(cache: dict) -> float | None:
    fetched = parse_utc(cache.get("fetched") if isinstance(cache, dict) else None)
    if not fetched:
        return None
    return (utc_now() - fetched).total_seconds() / 3600


def resolve_probe_url(cam: dict, z3_cache: dict) -> tuple[str, str, dict]:
    url = camera_url(cam)
    source = source_of(cam)
    meta: dict[str, Any] = {"source": source, "resolver": "direct"}

    if is_z3_camera(cam):
        cctvip = z3_cctvip(url)
        cache_data = z3_cache.get("data", {}) if isinstance(z3_cache, dict) else {}
        age_hours = z3_cache_age_hours(z3_cache)
        meta.update({"resolver": "z3_cache", "cctvip": cctvip, "z3_cache_age_hours": age_hours})
        if cctvip and isinstance(cache_data, dict) and cache_data.get(cctvip) and age_hours is not None and age_hours <= Z3_MAX_TRUSTED_AGE_HOURS:
            return cache_data[cctvip], "z3_cache", meta
        cctvid = url_param(url, "cctvid") or cam.get("id") or ""
        meta["resolver"] = "oracle_z3"
        return f"{ORACLE_BASE}/utic?kind=Z3&cctvid={quote(str(cctvid))}&cctvip={quote(str(cctvip or ''))}", "oracle_z3", meta

    if source == "KBS":
        cctvip = cam.get("original_id") or z3_cctvip(url) or str(cam.get("id", "")).split("_")[-1]
        meta.update({"resolver": "kbs", "cctvip": cctvip})
        # Prefer the existing signed URL when present; fallback to the resolver.
        if "kbscctv-cache" in url or "playlist.m3u8" in url:
            return url, "direct_kbs", meta
        return f"{ORACLE_BASE}/kb?cctvip={quote(str(cctvip))}", "oracle_kbs", meta

    if source in {"NOWJEJU", "TRENDWORLD"} and url and not url.startswith(ORACLE_BASE):
        meta["resolver"] = "oracle_proxy"
        return f"{ORACLE_BASE}/proxy?url={quote(url, safe='')}", "oracle_proxy", meta

    if source == "GITS":
        cctvid = url_param(url, "cctvid") or cam.get("original_id") or cam.get("id")
        meta.update({"resolver": "oracle_gits", "cctvid": cctvid})
        if cctvid:
            return f"{ORACLE_BASE}/gits?id={quote(str(cctvid))}", "oracle_gits", meta

    if source == "UTIC" and "openDataCctvStream.jsp" in url:
        meta["resolver"] = "oracle_utic"
        return f"{ORACLE_BASE}/utic?{urlparse(url).query}", "oracle_utic", meta

    return url, "direct", meta


def classify_response(resp: requests.Response, body_prefix: bytes, elapsed_ms: int) -> tuple[bool, str, str]:
    content_type = (resp.headers.get("Content-Type") or "").lower()
    text = body_prefix.decode("utf-8", errors="ignore")
    if resp.status_code >= 400 and not (resp.status_code == 404 and "mpegurl" in content_type):
        if resp.status_code in (401, 403):
            return False, "auth_or_token", "HTTP auth/token error"
        if resp.status_code == 404:
            return False, "not_found", "HTTP 404"
        return False, "http_error", f"HTTP {resp.status_code}"
    if "text/html" in content_type and "youtube" not in resp.url.lower():
        return False, "html_or_frame", "HTML/frame content, not a direct stream"
    if "mpegurl" in content_type or "#EXTM3U" in text or ".m3u8" in resp.url:
        return True, "ok_hls", "HLS manifest reachable"
    if "video" in content_type or ".mp4" in resp.url.lower():
        return True, "ok_video", "video content reachable"
    if text.startswith("http") or "cctvsec.ktict.co.kr" in text:
        return True, "ok_resolver", "resolver returned stream URL"
    if resp.status_code < 400 and content_type.startswith(("image/", "application/octet-stream")):
        return True, "ok_media", f"media reachable: {content_type}"
    if resp.status_code < 400:
        return True, "ok_http", f"HTTP {resp.status_code} {content_type or 'unknown content'}"
    return False, "unknown", "unknown response"


class SimpleResponse:
    def __init__(self, status_code: int, headers: Any, url: str):
        self.status_code = status_code
        self.headers = headers
        self.url = url


def read_probe_prefix(probe_url: str) -> tuple[SimpleResponse, bytes]:
    if requests is not None:
        resp = requests.get(
            probe_url,
            headers=HEADERS,
            timeout=DEFAULT_TIMEOUT,
            verify=False,
            allow_redirects=True,
            stream=True,
        )
        body = resp.raw.read(512, decode_content=True) if resp.raw else b""
        return resp, body

    request = Request(probe_url, headers=HEADERS)
    try:
        with urlopen(request, timeout=DEFAULT_TIMEOUT[1], context=SSL_CONTEXT) as resp:
            body = resp.read(512)
            return SimpleResponse(resp.status, resp.headers, resp.geturl()), body
    except HTTPError as error:
        body = error.read(512)
        return SimpleResponse(error.code, error.headers, error.geturl()), body


def probe_camera(cam: dict, z3_cache: dict) -> dict:
    started = time.monotonic()
    probe_url, resolver, meta = resolve_probe_url(cam, z3_cache)
    result = {
        "id": cam.get("id"),
        "name": cam.get("name"),
        "source": source_of(cam),
        "status": cam.get("status"),
        "resolver": resolver,
        "ok": False,
        "reason": "not_checked",
        "category": "not_checked",
        "elapsed_ms": None,
        "http_status": None,
        "content_type": None,
        "probe_url": redact_probe_url(probe_url),
        "meta": meta,
    }
    if not probe_url:
        result.update({"reason": "missing_url", "category": "data_error", "elapsed_ms": 0})
        return result

    try:
        resp, body = read_probe_prefix(probe_url)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        ok, category, reason = classify_response(resp, body, elapsed_ms)
        result.update({
            "ok": ok,
            "reason": reason,
            "category": category,
            "elapsed_ms": elapsed_ms,
            "http_status": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
        })
    except (TimeoutError, socket.timeout) as error:
        result.update({
            "reason": "timeout",
            "category": "timeout",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "detail": str(error)[:180],
        })
    except URLError as error:
        category = "timeout" if isinstance(getattr(error, "reason", None), TimeoutError) else "network_error"
        result.update({
            "reason": "request_error",
            "category": category,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "detail": str(error)[:180],
        })
    except Exception as error:
        result.update({
            "reason": "request_error",
            "category": "network_error",
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "detail": str(error)[:180],
        })
    return result


def select_candidates(cameras: list[dict], region: dict) -> list[dict]:
    terms = [term.lower() for term in region.get("keywords", [])]
    out = []
    for cam in cameras:
        try:
            lat = float(cam.get("lat"))
            lng = float(cam.get("lng"))
        except Exception:
            continue
        dist = haversine_km(region["lat"], region["lng"], lat, lng)
        text = f"{cam.get('name','')} {cam.get('address','')} {cam.get('source','')}".lower()
        keyword_match = any(term in text for term in terms)
        if dist > region.get("radius_km", 30) and not keyword_match:
            continue
        status_penalty = 2.5 if str(cam.get("status") or "").lower() == "manual_check" else 0
        source_bonus = -1.2 if source_of(cam) in {"KBS", "SPATIC", "NOWJEJU"} else 0
        z3_penalty = 0.8 if is_z3_camera(cam) else 0
        keyword_bonus = -2.0 if keyword_match else 0
        score = dist + status_penalty + source_bonus + z3_penalty + keyword_bonus
        out.append((score, dist, cam))
    out.sort(key=lambda item: (item[0], item[1], str(item[2].get("id"))))
    seen = set()
    selected = []
    for _, dist, cam in out:
        cid = cam.get("id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        clone = dict(cam)
        clone["_canary_distance_km"] = round(dist, 3)
        selected.append(clone)
        if len(selected) >= region.get("max_candidates", 6):
            break
    return selected


def summarize_region(region: dict, candidates: list[dict], results: list[dict]) -> dict:
    checked = len(results)
    passed = sum(1 for item in results if item.get("ok"))
    min_ok = int(region.get("min_ok", 1))
    failures = checked - passed
    categories = Counter(str(item.get("category") or "unknown") for item in results if not item.get("ok"))
    avg_ok_ms_values = [int(item.get("elapsed_ms") or 0) for item in results if item.get("ok") and item.get("elapsed_ms")]
    avg_ok_ms = round(sum(avg_ok_ms_values) / len(avg_ok_ms_values)) if avg_ok_ms_values else None

    if checked == 0:
        status = "NO_CANDIDATES"
        severity = "danger"
    elif passed >= min_ok:
        status = "OK" if failures == 0 else "DEGRADED"
        severity = "ok" if failures == 0 else "warn"
    else:
        status = "IMPACT"
        severity = "danger"

    if categories:
        dominant = categories.most_common(1)[0][0]
    else:
        dominant = None

    action = region_recovery_action(region, status, categories, results)
    recovery = region_recovery_plan(region, status, categories, results)
    if status == "OK":
        action = action or "정상 후보가 확보되었습니다."
    elif status == "DEGRADED":
        action = action or "일부 후보가 실패했습니다. 정상 후보를 우선 노출하고 실패 후보는 후순위 유지하세요."
    elif status == "IMPACT":
        action = action or "정상 후보 수가 기준 미달입니다. 토큰/캐시/공급처 상태를 우선 확인하고 대체 소스를 추천해야 합니다."
    elif status == "NO_CANDIDATES":
        action = action or "지역 후보 자체가 부족합니다. 데이터 수집 누락을 점검하세요."

    return {
        "key": region["key"],
        "label": region["label"],
        "status": status,
        "severity": severity,
        "checked": checked,
        "passed": passed,
        "failed": failures,
        "min_ok": min_ok,
        "success_rate": round(passed / checked, 3) if checked else 0,
        "avg_ok_ms": avg_ok_ms,
        "candidate_ids": [cam.get("id") for cam in candidates],
        "passed_ids": [item.get("id") for item in results if item.get("ok")],
        "failed_ids": [item.get("id") for item in results if not item.get("ok")],
        "failure_categories": dict(categories.most_common()),
        "dominant_failure": dominant,
        "recommended_action": action,
        "recovery_plan": recovery,
        "results": results,
    }


def region_recovery_action(region: dict, status: str, categories: Counter, results: list[dict]) -> str | None:
    if status == "NO_CANDIDATES":
        return "후보 데이터가 부족합니다. 수집처 누락을 보강하되 기존 목록은 삭제하지 마세요."
    if status == "OK":
        return None

    key = str(region.get("key") or "")
    dominant = categories.most_common(1)[0][0] if categories else None
    sources = Counter(str(item.get("source") or "UNKNOWN") for item in results if not item.get("ok"))

    if key == "daejeon":
        if dominant in {"timeout", "not_found"}:
            return "대전 UTIC 공급 응답 지연/404가 우세합니다. Oracle /utic 재해석과 Z3 최신 캐시를 재확인하고, 성공 이력이 있는 KBS/하천/인접 교통 후보를 우선 추천하세요."
        if dominant == "auth_or_token":
            return "대전 KBS/토큰형 URL 만료 신호입니다. KBS resolver 토큰 갱신을 우선 실행하고 실패 카메라는 삭제하지 말고 후순위 유지하세요."
        return "대전은 소스 혼합 장애 가능성이 큽니다. UTIC, KBS, GITS를 분리 점검하고 정상 후보를 우선 노출하세요."

    if key == "dokdo":
        return "독도/울릉은 KBS 토큰 의존도가 높습니다. KBS signed URL을 즉시 갱신하고 울릉/독도 인접 후보를 백업으로 유지하세요."

    if key == "jeju":
        return "제주는 로딩 지연과 대체 NOWJEJU 전환이 잦습니다. 기존 교통 CCTV는 긴 로딩 허용 후 실패 시에만 NOWJEJU로 넘기고, 성공 이력 후보를 우선하세요."

    if key in {"guri", "namyangju"}:
        return "수도권 시내 후보가 외곽도로에 밀리지 않도록 실사용 성공 이력과 시내 가중치를 함께 적용하세요."

    if dominant == "auth_or_token":
        return "토큰/서명 URL 갱신을 우선 실행하고, 실패 후보는 삭제하지 않고 후순위 처리하세요."
    if dominant == "timeout":
        return "공급처 지연 가능성이 큽니다. 재시도 간격을 늘리고 정상 후보를 먼저 추천하세요."
    return None


def region_recovery_plan(region: dict, status: str, categories: Counter, results: list[dict]) -> dict:
    failed = [item for item in results if not item.get("ok")]
    source_counts = Counter(str(item.get("source") or "UNKNOWN") for item in failed)
    resolver_counts = Counter(str(item.get("resolver") or "UNKNOWN") for item in failed)
    key = str(region.get("key") or "")
    actions = [
        "catalog_preserve",
        "downrank_failed_candidates",
        "prefer_recent_success_candidates",
    ]
    if categories.get("auth_or_token"):
        actions.append("refresh_signed_token_urls")
    if categories.get("timeout"):
        actions.append("probe_with_longer_timeout_before_fallback")
    if categories.get("not_found"):
        actions.append("rerun_source_resolver_and_cache_refresh")
    if status != "OK" and key in {"daejeon", "dokdo", "jindo", "jeju"}:
        actions.append(f"run_{key}_canary_recovery")
    return {
        "status": status,
        "primary_failure": categories.most_common(1)[0][0] if categories else None,
        "failed_sources": dict(source_counts.most_common()),
        "failed_resolvers": dict(resolver_counts.most_common()),
        "actions": actions,
        "delete_policy": "never_delete_for_transient_failure",
    }


def summarize_cache(cache_status: dict) -> dict:
    z3 = (cache_status or {}).get("z3", {}) if isinstance(cache_status, dict) else {}
    z3_cache = load_json(Z3_CACHE_FILE, {})
    actual_age_hours = z3_cache_age_hours(z3_cache)
    status_age = z3.get("age_minutes")
    status_age_hours = round(float(status_age) / 60, 2) if isinstance(status_age, (int, float)) else None
    age_hours = round(actual_age_hours, 2) if isinstance(actual_age_hours, (int, float)) else status_age_hours
    status = z3.get("status") or "UNKNOWN"
    if isinstance(age_hours, (int, float)) and age_hours > Z3_MAX_TRUSTED_AGE_HOURS:
        status = "STALE_ACTUAL_CACHE"
    severity = "ok"
    if age_hours is None or age_hours > Z3_MAX_TRUSTED_AGE_HOURS or status in {"STALE", "COVERAGE_RISK"}:
        severity = "danger"
    elif age_hours > 4:
        severity = "warn"
    return {
        "status": status,
        "severity": severity,
        "age_hours": age_hours,
        "fetched": z3_cache.get("fetched") or z3.get("fetched"),
        "entries": z3_cache.get("entries") or z3.get("entries"),
        "missing_cctvips": z3.get("missing_cctvips"),
        "missing_ratio": z3.get("missing_ratio"),
        "status_file_age_hours": status_age_hours,
        "actual_cache_age_hours": round(actual_age_hours, 2) if isinstance(actual_age_hours, (int, float)) else None,
    }


def build_ops_status(canary: dict) -> dict:
    cache_status = load_json(CACHE_STATUS_FILE, {})
    health_status = load_json(STATUS_FILE, {})
    quality_summary = load_json(QUALITY_SUMMARY_FILE, {})
    audit_history = load_json(UTIC_AUDIT_HISTORY_FILE, [])
    cache = summarize_cache(cache_status)
    regions = canary.get("regions", {})
    impact = [item for item in regions.values() if item.get("status") in {"IMPACT", "NO_CANDIDATES"}]
    degraded = [item for item in regions.values() if item.get("status") == "DEGRADED"]
    service_status = "OK"
    severity = "ok"
    if cache.get("severity") == "danger" or impact:
        service_status = "SERVICE_IMPACT"
        severity = "danger"
    elif degraded or cache.get("severity") == "warn":
        service_status = "DEGRADED"
        severity = "warn"

    audit_runs = audit_history if isinstance(audit_history, list) else audit_history.get("runs", []) if isinstance(audit_history, dict) else []
    recent_recoveries = sum(int(run.get("recovered") or run.get("restored") or 0) for run in audit_runs[-12:] if isinstance(run, dict))

    return {
        "generated_at": canary.get("generated_at") or utc_stamp(),
        "service_status": service_status,
        "severity": severity,
        "policy": {
            "catalog_preservation": "카메라는 삭제하지 않고 품질/카나리/실사용 데이터로 후순위 처리합니다.",
            "workflow_failure_definition": "GitHub Actions 실패는 스크립트/데이터 보존/커밋 실패입니다. 외부 CCTV 장애는 canary_status/ops_status에 서비스 영향으로 기록합니다.",
            "green_confidence": "녹색은 카메라 단위 실사용 성공 또는 카나리/품질 데이터가 충분할 때만 강하게 표시합니다.",
        },
        "cache": {"z3": cache},
        "canary": {
            "status": canary.get("overall_status"),
            "severity": canary.get("severity"),
            "regions_total": len(regions),
            "impact_regions": [item.get("label") for item in impact],
            "degraded_regions": [item.get("label") for item in degraded],
            "regions": regions,
        },
        "regional_health": {
            "last_updated": health_status.get("last_updated"),
            "regions_total": len(health_status.get("regions", {}) or {}),
            "camera_failures": len(health_status.get("camera_failures", {}) or {}),
        },
        "quality_summary": {
            "generated_at": quality_summary.get("generated_at"),
            "camera_count": len(quality_summary.get("cameras", {}) or {}),
            "source_count": len(quality_summary.get("sources", {}) or {}),
            "region_count": len(quality_summary.get("regions", {}) or {}),
        },
        "auto_recovery": {
            "recent_runs": len(audit_runs[-12:]),
            "recent_recovered": recent_recoveries,
            "last_audited_at": audit_runs[-1].get("audited_at") if audit_runs and isinstance(audit_runs[-1], dict) else None,
        },
    }


def compact_history_point(canary: dict, ops: dict) -> dict:
    regions = {}
    for key, item in (canary.get("regions") or {}).items():
        regions[key] = {
            "status": item.get("status"),
            "severity": item.get("severity"),
            "success_rate": item.get("success_rate"),
            "passed": item.get("passed"),
            "checked": item.get("checked"),
            "avg_ok_ms": item.get("avg_ok_ms"),
            "dominant_failure": item.get("dominant_failure"),
        }
    return {
        "generated_at": canary.get("generated_at") or utc_stamp(),
        "overall_status": canary.get("overall_status"),
        "severity": canary.get("severity"),
        "z3_age_hours": (ops.get("cache") or {}).get("z3", {}).get("age_hours"),
        "z3_status": (ops.get("cache") or {}).get("z3", {}).get("status"),
        "regions": regions,
    }


def append_history(canary: dict, ops: dict, path: Path = CANARY_HISTORY_FILE, limit: int = 288) -> list[dict]:
    history = load_json(path, [])
    if not isinstance(history, list):
        history = []
    point = compact_history_point(canary, ops)
    history = [item for item in history if isinstance(item, dict) and item.get("generated_at") != point["generated_at"]]
    history.append(point)
    history.sort(key=lambda item: str(item.get("generated_at") or ""))
    history = history[-limit:]
    write_json(path, history)
    return history


def run() -> tuple[dict, dict]:
    cameras = load_json(DATA_FILE, [])
    if not isinstance(cameras, list):
        raise SystemExit("cctv_data.json must be a list")
    z3_cache = load_json(Z3_CACHE_FILE, {})
    regions: dict[str, Any] = {}
    camera_index: dict[str, Any] = {}
    for region in CANARY_REGIONS:
        candidates = select_candidates(cameras, region)
        print(f"[canary] {region['label']} candidates={len(candidates)}")
        results = []
        for cam in candidates:
            result = probe_camera(cam, z3_cache)
            result["distance_km"] = cam.get("_canary_distance_km")
            result["region_key"] = region["key"]
            result["region_label"] = region["label"]
            print(f"[canary] {region['label']} {result['id']} {result['ok']} {result['category']} {result.get('elapsed_ms')}ms")
            results.append(result)
            if result.get("id"):
                camera_index[str(result["id"])] = {
                    "id": result.get("id"),
                    "name": result.get("name"),
                    "source": result.get("source"),
                    "region_key": region["key"],
                    "region_label": region["label"],
                    "ok": result.get("ok"),
                    "category": result.get("category"),
                    "reason": result.get("reason"),
                    "elapsed_ms": result.get("elapsed_ms"),
                    "checked_at": utc_stamp(),
                    "resolver": result.get("resolver"),
                }
        regions[region["key"]] = summarize_region(region, candidates, results)

    impact = [item for item in regions.values() if item.get("status") in {"IMPACT", "NO_CANDIDATES"}]
    degraded = [item for item in regions.values() if item.get("status") == "DEGRADED"]
    overall = "OK"
    severity = "ok"
    if impact:
        overall = "SERVICE_IMPACT"
        severity = "danger"
    elif degraded:
        overall = "DEGRADED"
        severity = "warn"

    canary = {
        "generated_at": utc_stamp(),
        "overall_status": overall,
        "severity": severity,
        "policy": {
            "core_regions": [region["label"] for region in CANARY_REGIONS],
            "cadence": "Oracle/local cron every 15-30 minutes is primary; GitHub Actions refreshes the static fallback every 3 hours.",
            "candidate_policy": "핵심 지역은 넓은 후보군을 점검해 일부 장애가 있어도 재생 가능한 인접 후보를 찾습니다.",
            "catalog_preservation": "카메라 목록은 삭제하지 않고, 실패 카메라는 추천/노출 순위만 낮춥니다.",
            "service_impact_is_data_not_job_failure": "카나리에서 외부 CCTV 장애가 발견되어도 워크플로우는 성공 처리하고 상태 JSON에 기록합니다.",
            "z3_cache_incident_threshold_hours": Z3_MAX_TRUSTED_AGE_HOURS,
        },
        "cameras": camera_index,
        "regions": regions,
    }
    ops = build_ops_status(canary)
    return canary, ops


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canary-output", type=Path, default=CANARY_STATUS_FILE)
    parser.add_argument("--ops-output", type=Path, default=OPS_STATUS_FILE)
    parser.add_argument("--history-output", type=Path, default=CANARY_HISTORY_FILE)
    parser.add_argument("--strict-service-impact", action="store_true", help="exit non-zero when canary detects service impact")
    args = parser.parse_args()

    canary, ops = run()
    write_json(args.canary_output, canary)
    write_json(args.ops_output, ops)
    append_history(canary, ops, args.history_output)
    print(f"[canary] wrote {args.canary_output}")
    print(f"[canary] wrote {args.ops_output}")
    print(f"[canary] wrote {args.history_output}")
    print(f"[canary] overall={canary['overall_status']}")

    if args.strict_service_impact and canary.get("overall_status") == "SERVICE_IMPACT":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
