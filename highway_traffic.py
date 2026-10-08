"""Shared helpers for Korean highway traffic (data.ex.co.kr) and ITS cctvInfo.

Parsing and key-error classification are ported from the MIT-licensed
NomaDamas/k-skill ``highway-traffic-status/scripts/highway_traffic.py``
(https://github.com/NomaDamas/k-skill, MIT License, Copyright (c) 2026).
Adapted for this repository:

* ITS cctvInfo answers success bodies as XML even with ``getType=json``; we
  parse XML first and fall back to the JSON envelope (older responses).
* Key problems are raised as :class:`KeyProblemError` so collectors can record
  them in ``data/workflow_status.json`` instead of failing silently.
* data.ex.co.kr ``trafficAmountByRealtime`` rows are normalized for the
  ``/highway-traffic`` proxy endpoint. The upstream ``updownTypeCode`` is
  passed through untouched: its S/N/E/W -> 상행/하행 mapping is unverified,
  so the UI never labels a direction from it.

Stdlib only so it can be imported by the collectors, the Flask proxy, and the
Docker image without extra dependencies.
"""

from __future__ import annotations

import json
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

EXDATA_TRAFFIC_URL = "https://data.ex.co.kr/openapi/odtraffic/trafficAmountByRealtime"
ITS_CCTV_URL = "https://openapi.its.go.kr:9443/cctvInfo"

# Published demo keys (work without registration as of 2026-07-21 per k-skill).
# They may be revoked or rate limited at any time; production should set its
# own keys through the environment.
EXDATA_DEMO_KEY = "test"
ITS_DEMO_KEY = "test"

# 대한민국 근해 좌표 범위 (경도/위도)
KOREA_LON_RANGE = (124.0, 132.0)
KOREA_LAT_RANGE = (33.0, 39.5)

GRADE_LABELS = {1: "원활", 2: "서행", 3: "정체"}
KST = timezone(timedelta(hours=9))


class UpstreamError(RuntimeError):
    """Upstream answered with something we could not use."""


class KeyProblemError(UpstreamError):
    """The upstream rejected the API key (invalid, revoked, or over quota)."""


def resolve_api_key(*env_names: str, demo_key: str, label: str, log=None) -> tuple[str, bool]:
    """Return ``(key, is_demo)``; fall back to the public demo key with a warning."""

    for name in env_names:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value, False
    message = (
        f"[WARNING] {label}: {' / '.join(env_names)} is not set; "
        f"falling back to the public demo key '{demo_key}'. "
        "Register a personal key for production use."
    )
    (log or logger.warning)(message)
    return demo_key, True


def in_korea_bounds(lat: Any, lng: Any) -> bool:
    try:
        lat_f = float(lat)
        lng_f = float(lng)
    except (TypeError, ValueError):
        return False
    return (
        KOREA_LAT_RANGE[0] <= lat_f <= KOREA_LAT_RANGE[1]
        and KOREA_LON_RANGE[0] <= lng_f <= KOREA_LON_RANGE[1]
    )


# ---------------------------------------------------------------------------
# ITS cctvInfo
# ---------------------------------------------------------------------------

def _its_json_error(payload: Any, status_code: int | None) -> UpstreamError | None:
    if not isinstance(payload, dict):
        return None
    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    result_code = str(header.get("resultCode") or "").strip()
    message = str(header.get("resultMsg") or payload.get("message") or "").strip()
    if status_code == 401 or result_code == "4005" or "인증키" in message:
        return KeyProblemError(
            f"ITS cctvInfo key problem (HTTP {status_code}, resultCode {result_code or '-'}): {message or 'unauthorized'}"
        )
    if result_code and result_code not in {"0", "00", "200"}:
        return UpstreamError(f"ITS cctvInfo error (resultCode {result_code}): {message or 'unknown'}")
    return None


def parse_its_cctv_response(body: str, status_code: int | None = 200) -> list[dict[str, Any]]:
    """Parse an ITS cctvInfo body into raw ITS-style dicts.

    Returns dicts keyed like the upstream (``cctvname``, ``cctvurl``,
    ``coordx``, ``coordy``, ``cctvformat``, ``cctvtype``) so existing callers
    keep working. XML is tried first because that is what the success path
    returns; the JSON branch handles both the error envelope and the legacy
    JSON success shape.
    """

    text = (body or "").strip().lstrip("\ufeff")
    if status_code == 401:
        payload = None
        try:
            payload = json.loads(text) if text.startswith("{") else None
        except json.JSONDecodeError:
            payload = None
        raise _its_json_error(payload or {}, 401) or KeyProblemError("ITS cctvInfo key problem (HTTP 401)")
    if status_code is not None and status_code >= 400:
        raise UpstreamError(f"ITS cctvInfo HTTP {status_code}")
    if not text:
        raise UpstreamError("ITS cctvInfo returned an empty body")

    if text.startswith("<"):
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise UpstreamError("ITS cctvInfo body is not parseable XML (blocked or format change?)") from exc
        items = []
        for node in root.iter("data"):
            record = {child.tag: (child.text or "").strip() for child in list(node)}
            if record:
                items.append(record)
        if not items and root.tag != "response":
            raise UpstreamError(f"ITS cctvInfo unexpected XML root <{root.tag}>")
        return items

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UpstreamError("ITS cctvInfo body is neither XML nor JSON (blocked or maintenance?)") from exc

    error = _its_json_error(payload, status_code)
    if error is not None:
        raise error

    rows: Any = []
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        response = payload.get("response")
        if isinstance(response, dict):
            rows = response.get("data") or []
        if not rows and "data" in payload:
            rows = payload.get("data") or []
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise UpstreamError("ITS cctvInfo JSON has no data list")
    return [row for row in rows if isinstance(row, dict)]


# ---------------------------------------------------------------------------
# data.ex.co.kr trafficAmountByRealtime
# ---------------------------------------------------------------------------

def build_exdata_traffic_url(api_key: str, page_no: int | None = None, num_of_rows: int | None = None) -> str:
    query: dict[str, Any] = {"key": api_key or EXDATA_DEMO_KEY, "type": "json"}
    if page_no is not None:
        query["pageNo"] = page_no
    if num_of_rows is not None:
        query["numOfRows"] = num_of_rows
    return f"{EXDATA_TRAFFIC_URL}?{urlencode(query)}"


def check_exdata_payload(payload: Any) -> list[dict[str, Any]]:
    """Validate an exdata payload and return the raw row list.

    The service answers an invalid key with HTTP 200 and
    ``{"code": "ERROR", "message": "인증키가 유효하지 않습니다."}``.
    """

    if not isinstance(payload, dict):
        raise UpstreamError("data.ex.co.kr payload is not a JSON object")
    code = str(payload.get("code") or "").upper()
    message = str(payload.get("message") or "").strip()
    if code == "ERROR":
        if "인증키" in message or "key" in message.lower():
            raise KeyProblemError(f"data.ex.co.kr key problem: {message or 'invalid key'}")
        raise UpstreamError(f"data.ex.co.kr error: {message or 'unknown'}")
    rows = payload.get("list")
    if not isinstance(rows, list):
        raise UpstreamError("data.ex.co.kr payload has no traffic list")
    return rows


def _to_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None


def format_observed_at(std_date: Any, std_hour: Any) -> str | None:
    """``20260721`` + ``1530`` -> ``2026-07-21T15:30:00+09:00`` (KST)."""

    date_text = str(std_date or "").strip()
    hour_text = str(std_hour or "").strip().zfill(4) if str(std_hour or "").strip() else ""
    if len(date_text) != 8 or not date_text.isdigit():
        return None
    try:
        if hour_text and hour_text.isdigit():
            parsed = datetime.strptime(date_text + hour_text[:4], "%Y%m%d%H%M")
        else:
            parsed = datetime.strptime(date_text, "%Y%m%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST).isoformat()


def normalize_exdata_traffic(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    sections = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        grade = _to_int(row.get("grade"))
        if grade not in GRADE_LABELS:
            grade = None
        speed = _to_int(row.get("speed"))
        sections.append({
            "routeName": str(row.get("routeName") or "").strip(),
            "routeNo": str(row.get("routeNo") or "").strip(),
            "conzoneId": str(row.get("conzoneId") or "").strip(),
            "conzoneName": str(row.get("conzoneName") or "").strip(),
            # Raw upstream code only; see module docstring.
            "directionCode": str(row.get("updownTypeCode") or "").strip(),
            "grade": grade,
            "congestion": GRADE_LABELS.get(grade, "정보없음"),
            "speed": speed if speed is not None and speed >= 0 else None,
            "observed_at": format_observed_at(row.get("stdDate"), row.get("stdHour")),
        })
    return sections


def route_grade(grades: list[int]) -> int | None:
    """Representative grade for a route: worst sections dominate early."""

    if not grades:
        return None
    total = len(grades)
    jam = sum(1 for grade in grades if grade == 3)
    slow = sum(1 for grade in grades if grade == 2)
    if jam / total >= 0.15:
        return 3
    if (jam + slow) / total >= 0.25:
        return 2
    return 1


def summarize_routes(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for section in sections:
        name = section.get("routeName")
        if not name:
            continue
        bucket = buckets.setdefault(name, {
            "routeName": name,
            "routeNo": section.get("routeNo") or "",
            "grades": [],
            "speeds": [],
            "observed": [],
        })
        if section.get("grade"):
            bucket["grades"].append(section["grade"])
        if section.get("speed") is not None:
            bucket["speeds"].append(section["speed"])
        if section.get("observed_at"):
            bucket["observed"].append(section["observed_at"])

    routes = []
    for bucket in buckets.values():
        grade = route_grade(bucket["grades"])
        speeds = bucket["speeds"]
        routes.append({
            "routeName": bucket["routeName"],
            "routeNo": bucket["routeNo"],
            "grade": grade,
            "congestion": GRADE_LABELS.get(grade, "정보없음"),
            "avgSpeed": round(sum(speeds) / len(speeds)) if speeds else None,
            "sections": len(bucket["grades"]),
            "congestedSections": sum(1 for g in bucket["grades"] if g == 3),
            "slowSections": sum(1 for g in bucket["grades"] if g == 2),
            "observed_at": max(bucket["observed"]) if bucket["observed"] else None,
        })
    routes.sort(key=lambda item: (-(item["grade"] or 0), -item["congestedSections"], item["routeName"]))
    return routes


def _section_severity(section: dict[str, Any]) -> tuple[int, int]:
    grade = section.get("grade") or 0
    speed = section.get("speed")
    # Higher grade first; for equal grades the slower reading is worse.
    return grade, -(speed if speed is not None else 999)


def collapse_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per conzone and direction.

    The realtime feed has one row per vehicle detector (VDS), so a single
    conzone appears several times (about 8.4k rows for 1.6k conzones). The
    worst reading represents the conzone, which also keeps the payload small.
    """

    collapsed: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    for section in sections:
        key = (
            section.get("routeNo") or section.get("routeName") or "",
            section.get("conzoneId") or section.get("conzoneName") or "",
            section.get("directionCode") or "",
        )
        if not key[1]:
            key = (key[0], f"#{len(order)}", key[2])
        current = collapsed.get(key)
        if current is None:
            collapsed[key] = section
            order.append(key)
            continue
        observed = max(filter(None, [current.get("observed_at"), section.get("observed_at")]), default=None)
        if _section_severity(section) > _section_severity(current):
            current = section
        collapsed[key] = {**current, "observed_at": observed}
    return [collapsed[key] for key in order]


def build_traffic_snapshot(rows: Iterable[dict[str, Any]], *, fetched_at: str, demo_key: bool) -> dict[str, Any]:
    sections = collapse_sections(normalize_exdata_traffic(rows))
    observed = [section["observed_at"] for section in sections if section.get("observed_at")]
    return {
        "ok": True,
        "source": "data.ex.co.kr trafficAmountByRealtime",
        "observed_at": max(observed) if observed else None,
        "fetched_at": fetched_at,
        "demo_key": demo_key,
        "routes": summarize_routes(sections),
        "sections": sections,
    }
