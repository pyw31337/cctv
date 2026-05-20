#!/usr/bin/env python3
"""Refresh and audit the UTIC/NTIC Z3 appUrl cache.

The Z3 cache is not just an optimization: many national-road cameras need a
fresh its.go.kr appUrl token before the browser can resolve a frame-free HLS
stream. This script is intentionally reusable from GitHub Actions, Oracle cron,
and manual incident response.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_FILE = ROOT / "data" / "z3_cache.json"
DEFAULT_DATA_FILE = ROOT / "cctv_data.json"
DEFAULT_STATUS_FILE = ROOT / "data" / "cache_status.json"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp(dt: datetime | None = None) -> str:
    value = dt or utc_now()
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_stamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


def load_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fallback
    except Exception as error:
        print(f"[WARN] failed to load {path}: {error}", file=sys.stderr)
        return fallback


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def get_cache_age_minutes(cache_file: Path) -> float | None:
    cache = load_json(cache_file, {})
    fetched = parse_utc_stamp(cache.get("fetched") if isinstance(cache, dict) else None)
    if not fetched:
        return None
    return (utc_now() - fetched).total_seconds() / 60


def should_skip_refresh(cache_file: Path, max_age_minutes: int, force: bool) -> bool:
    if force:
        return False
    age_minutes = get_cache_age_minutes(cache_file)
    if age_minutes is None:
        return False
    if age_minutes <= max_age_minutes:
        print(f"[OK] existing Z3 cache is fresh enough: {age_minutes:.1f} min <= {max_age_minutes} min")
        return True
    print(f"[WARN] existing Z3 cache is stale: {age_minutes:.1f} min > {max_age_minutes} min")
    return False


def fetch_z3_map(max_attempts: int = 3) -> dict[str, str]:
    last_error = None
    for attempt in range(max_attempts):
        ua = USER_AGENTS[attempt % len(USER_AGENTS)]
        session = requests.Session()
        session.verify = False
        try:
            print(f"[INFO] Z3 refresh attempt {attempt + 1}/{max_attempts}: opening its.go.kr")
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "max-age=0",
            }
            session.get("https://its.go.kr/", timeout=20, headers=headers)
            xsrf = session.cookies.get("XSRF-TOKEN", "")
            if not xsrf:
                raise RuntimeError("missing XSRF-TOKEN")

            api_headers = {
                "User-Agent": ua,
                "Referer": "https://its.go.kr/",
                "Content-Type": "application/json",
                "X-XSRF-TOKEN": xsrf,
                "Accept": "application/json",
                "Origin": "https://its.go.kr",
            }
            response = session.post(
                "https://its.go.kr/map/getMarkers",
                data=json.dumps({"body": {"data": {"type": "CCTV"}}}),
                headers=api_headers,
                timeout=120,
            )
            if response.status_code != 200:
                raise RuntimeError(f"getMarkers HTTP {response.status_code}: {response.text[:160]}")

            features = response.json().get("features", [])
            cctvip_map: dict[str, str] = {}
            for feature in features:
                props = feature.get("properties", {})
                info_str = props.get("INFO", "{}")
                try:
                    info = json.loads(info_str) if isinstance(info_str, str) else info_str
                except Exception:
                    continue
                app_url = info.get("appUrl", "") if isinstance(info, dict) else ""
                if app_url and "cctvsec.ktict.co.kr" in app_url:
                    parts = app_url.split("/")
                    if len(parts) >= 4:
                        cctvip_map[parts[3]] = app_url

            if not cctvip_map:
                raise RuntimeError("no cctvsec appUrl entries extracted")

            print(f"[OK] fetched {len(cctvip_map)} Z3 appUrl entries from its.go.kr")
            return cctvip_map
        except Exception as error:
            last_error = error
            print(f"[WARN] attempt {attempt + 1} failed: {error}", file=sys.stderr)
            if attempt < max_attempts - 1:
                time.sleep(8 * (attempt + 1))

    raise RuntimeError(f"all Z3 refresh attempts failed: {last_error}")


def z3_expected_cctvips(data_file: Path) -> set[str]:
    return set(z3_expected_cameras(data_file).keys())


def z3_expected_cameras(data_file: Path) -> dict[str, dict]:
    items = load_json(data_file, [])
    expected: dict[str, dict] = {}
    if not isinstance(items, list):
        return expected
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("directUrl") or item.get("url") or ""
        try:
            params = parse_qs(urlparse(url).query)
        except Exception:
            params = {}
        kind = (params.get("kind") or [""])[0]
        cctvip = (params.get("cctvip") or [""])[0]
        if cctvip and (item.get("source") == "NTIC" or kind == "Z3"):
            expected[str(cctvip)] = {
                "id": item.get("id"),
                "name": item.get("name"),
                "source": item.get("source"),
                "kind": kind,
                "cctvip": str(cctvip),
            }
    return expected


def build_status(cache_file: Path, data_file: Path, cache_payload: dict | None = None) -> dict:
    cache = cache_payload or load_json(cache_file, {})
    data = cache.get("data", {}) if isinstance(cache, dict) else {}
    fetched = cache.get("fetched") if isinstance(cache, dict) else None
    fetched_dt = parse_utc_stamp(fetched)
    age_minutes = round((utc_now() - fetched_dt).total_seconds() / 60, 1) if fetched_dt else None
    expected_cameras = z3_expected_cameras(data_file)
    expected = set(expected_cameras.keys())
    present = set(data.keys()) if isinstance(data, dict) else set()
    missing = sorted(expected - present)
    missing_ratio = (len(missing) / len(expected)) if expected else 0
    missing_sources: dict[str, int] = {}
    missing_prefixes: dict[str, int] = {}
    for cctvip in missing:
        item = expected_cameras.get(cctvip, {})
        source = str(item.get("source") or "UNKNOWN")
        prefix = str(item.get("id") or "")[:3] or "UNKNOWN"
        missing_sources[source] = missing_sources.get(source, 0) + 1
        missing_prefixes[prefix] = missing_prefixes.get(prefix, 0) + 1
    status = "OK"
    if age_minutes is None or age_minutes > 90:
        status = "STALE"
    if missing_ratio >= 0.08:
        status = "COVERAGE_RISK"
    return {
        "generated_at": utc_stamp(),
        "z3": {
            "status": status,
            "fetched": fetched,
            "age_minutes": age_minutes,
            "entries": len(present),
            "expected_cctvips": len(expected),
            "missing_cctvips": len(missing),
            "missing_ratio": round(missing_ratio, 4),
            "missing_samples": missing[:40],
            "missing_by_source": dict(sorted(missing_sources.items(), key=lambda pair: (-pair[1], pair[0]))),
            "missing_by_id_prefix": dict(sorted(missing_prefixes.items(), key=lambda pair: (-pair[1], pair[0]))[:20]),
            "missing_camera_samples": [expected_cameras[cctvip] for cctvip in missing[:40]],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-file", type=Path, default=DEFAULT_CACHE_FILE)
    parser.add_argument("--data-file", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--max-age-minutes", type=int, default=45)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--no-status", action="store_true")
    args = parser.parse_args()

    cache_payload = None
    refreshed = False
    if not args.audit_only and not should_skip_refresh(args.cache_file, args.max_age_minutes, args.force):
        cctvip_map = fetch_z3_map()
        cache_payload = {
            "fetched": utc_stamp(),
            "entries": len(cctvip_map),
            "data": cctvip_map,
        }
        atomic_write_json(args.cache_file, cache_payload)
        refreshed = True
        print(f"[OK] wrote {args.cache_file} with {len(cctvip_map)} entries")

    status = build_status(args.cache_file, args.data_file, cache_payload)
    z3 = status["z3"]
    print(
        "[INFO] Z3 audit: "
        f"status={z3['status']} fetched={z3['fetched']} age={z3['age_minutes']}min "
        f"entries={z3['entries']} expected={z3['expected_cctvips']} missing={z3['missing_cctvips']}"
    )
    if not args.no_status:
        atomic_write_json(args.status_file, status)
        print(f"[OK] wrote {args.status_file}")

    if z3["status"] == "STALE":
        print("[ERROR] Z3 cache is still stale after refresh attempt", file=sys.stderr)
        return 2
    if refreshed:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
