"""Shared runtime configuration and camera identity helpers.

Keep environment lookups, proxy base URLs, and normalized camera identity
logic in one place so the collectors, proxy server, and utility scripts do not
duplicate the same constants.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

DEFAULT_PUBLIC_PROXY_BASE = "https://158.179.194.163.sslip.io"
DEFAULT_WORKER_PROXY_BASE = "https://cctv-proxy.pyw213.workers.dev"
DEFAULT_QUALITY_TELEMETRY_ENDPOINT = "https://cctv-quality.pyw31337.workers.dev/v1/events"
DEFAULT_QUALITY_SUMMARY_URL = "https://cctv-quality.pyw31337.workers.dev/v1/summary"

# Verified Namyangju UTIC mapping. These IDs are deliberately keyed by the
# stable catalog camera ID, not by a mutable display name.
NAMYANGJU_GOLDEN_STREAMS: dict[str, tuple[str, str]] = {
    "L180074": ("록원교회(웹)", "L180188"),
    "L180075": ("마석사거리(웹)", "L180111"),
    "L180076": ("마석윗3", "L180009"),
    "L180195": ("창현A앞4 (1)", "L180007"),
    "L180196": ("창현A앞4 (2)", "L180065"),
    "L180205": ("퇴계원사거리", "L180013"),
    "L180206": ("퇴계원사거리(웹)", "L180077"),
    "L180140": ("양정4 (1)", "L180076"),
    "L180141": ("양정4 (2)", "L180045"),
    "L180115": ("샛터3 (1)", "L180021"),
    "L180116": ("샛터3 (2)", "L180075"),
}
KNOWN_CAMERA_ID_ALIASES: dict[str, str] = {
    # Historical typo: the verified UTIC record is L933067.
    "L933066": "L933067",
}


def first_env(*names: str, default: Any = None) -> Any:
    for name in names:
        value = os.environ.get(name)
        if value is None:
            continue
        value = value.strip()
        if value:
            return value
    return default


def require_env(*names: str) -> str:
    value = first_env(*names)
    if value is None:
        joined = ", ".join(names)
        raise RuntimeError(f"Missing required environment variable: {joined}")
    return value


def env_int(name: str, default: int) -> int:
    raw = first_env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    raw = first_env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool = False) -> bool:
    raw = first_env(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on", "y"}


def _normalize_base(value: Any) -> str:
    return str(value or "").strip().rstrip("/")


def public_proxy_base() -> str:
    return _normalize_base(
        first_env("CCTV_PUBLIC_PROXY_BASE", "PUBLIC_PROXY_BASE_URL", default=DEFAULT_PUBLIC_PROXY_BASE)
    ) or DEFAULT_PUBLIC_PROXY_BASE


def worker_proxy_base() -> str:
    return _normalize_base(
        first_env("CCTV_WORKER_PROXY_BASE", "WORKER_PROXY_BASE_URL", default=DEFAULT_WORKER_PROXY_BASE)
    ) or DEFAULT_WORKER_PROXY_BASE


def proxy_bases() -> list[str]:
    raw = first_env("CCTV_PROXY_BASES")
    if raw:
        bases = [_normalize_base(part) for part in raw.split(",")]
        bases = [base for base in bases if base]
    else:
        bases = [public_proxy_base(), worker_proxy_base()]

    seen = set()
    unique = []
    for base in bases:
        if base in seen:
            continue
        seen.add(base)
        unique.append(base)
    return unique


def proxy_prefix(base: str | None = None, route: str = "proxy") -> str:
    normalized_base = _normalize_base(base or public_proxy_base())
    return f"{normalized_base}/{route}?url="


def public_proxy_prefix(route: str = "proxy") -> str:
    return proxy_prefix(route=route)


def worker_proxy_prefix(route: str = "proxy") -> str:
    return proxy_prefix(worker_proxy_base(), route=route)


def quality_telemetry_endpoint() -> str:
    return first_env(
        "CCTV_QUALITY_TELEMETRY_ENDPOINT",
        default=DEFAULT_QUALITY_TELEMETRY_ENDPOINT,
    )


def quality_summary_url() -> str:
    return first_env("CCTV_QUALITY_SUMMARY_URL", default=DEFAULT_QUALITY_SUMMARY_URL)


def canary_status_url() -> str:
    return first_env("CCTV_CANARY_STATUS_URL", default=f"{public_proxy_base()}/canary-status")


def slugify(value: Any, fallback: str = "camera") -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or fallback


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def camera_source_id(item: dict[str, Any]) -> str:
    for key in ("original_id", "source_id", "id", "cctvid", "cctvId", "DEVICE_ID", "CCTVID"):
        value = _coerce_text(item.get(key))
        if value:
            return value
    return ""


def camera_identity(item: dict[str, Any]) -> str:
    source = _coerce_text(item.get("source")).upper() or "UNKNOWN"
    source_id = camera_source_id(item)
    if source_id:
        return f"{source}:{source_id}"

    name = slugify(
        item.get("name")
        or item.get("cctvName")
        or item.get("CCTVNAME")
        or item.get("title")
        or item.get("label"),
        fallback="camera",
    )
    lat = item.get("lat")
    lng = item.get("lng")
    if _is_number(lat) and _is_number(lng):
        return f"{source}:{name}:{float(lat):.6f}:{float(lng):.6f}"
    return f"{source}:{name}"


def stream_id_from_url(url: Any) -> str:
    """Extract a provider stream ID from a direct media or UTIC URL."""
    value = str(url or "")
    media_match = re.search(r"/media/(L\d+)(?:/|$)", value, re.IGNORECASE)
    if media_match:
        return media_match.group(1).upper()
    try:
        from urllib.parse import parse_qs, urlparse

        query_id = parse_qs(urlparse(value).query).get("id", [""])[0]
        match = re.fullmatch(r"(L\d+)", query_id.strip(), re.IGNORECASE)
        return match.group(1).upper() if match else ""
    except (TypeError, ValueError):
        return ""


def url_camera_id(url: Any) -> str:
    """Extract a stable camera ID from a UTIC URL when it is present."""
    try:
        from urllib.parse import parse_qs, urlparse

        value = parse_qs(urlparse(str(url or "")).query).get("cctvid", [""])[0].strip()
        return value.upper()
    except (TypeError, ValueError):
        return ""


def apply_camera_id_aliases(items: list[dict[str, Any]]) -> int:
    """Normalize known catalog ID typos before overrides and validation run."""
    changed = 0
    ids = {str(item.get("id") or "").upper() for item in items}
    for item in items:
        current = str(item.get("id") or "").upper()
        canonical = KNOWN_CAMERA_ID_ALIASES.get(current)
        if not canonical or canonical in ids:
            continue
        item["id"] = canonical
        if item.get("canonical_id") == current:
            item["canonical_id"] = canonical
        changed += 1
        ids.add(canonical)
    return changed


def validate_stream_identity(items: list[dict[str, Any]]) -> list[str]:
    """Reject records whose URL points to a different stable camera ID."""
    errors: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        camera_id = str(item.get("id") or "").strip().upper()
        source = str(item.get("source") or "").strip().upper()
        url = item.get("url") or item.get("directUrl")
        embedded_id = url_camera_id(url)
        if source == "UTIC" and embedded_id and embedded_id != camera_id:
            errors.append(f"{camera_id}: URL cctvid={embedded_id}")
    return errors


def apply_namyangju_golden_mappings(items: list[dict[str, Any]]) -> int:
    """Apply verified Namyangju stream IDs without changing other providers."""
    changed = 0
    for item in items:
        camera_id = str(item.get("id") or "").strip().upper()
        mapping = NAMYANGJU_GOLDEN_STREAMS.get(camera_id)
        if not mapping or str(item.get("source") or "").upper() != "UTIC":
            continue

        expected_name, stream_id = mapping
        expected_url = f"https://211.57.45.101/media/{stream_id}/chunklist.m3u8"
        if item.get("name") != expected_name:
            item["name"] = expected_name
            changed += 1
        if item.get("url") != expected_url or item.get("directUrl") != expected_url:
            item["url"] = expected_url
            item["directUrl"] = expected_url
            changed += 1

        tags = list(item.get("tags") or [])
        for tag in ("direct_source", "locked_mapping", "golden_namyangju"):
            if tag not in tags:
                tags.append(tag)
        item["tags"] = tags
        item["golden_stream_id"] = stream_id
    return changed


def validate_namyangju_golden_mappings(
    items: list[dict[str, Any]], *, require_all: bool = False
) -> list[str]:
    """Return data-integrity errors for known Namyangju camera mappings."""
    by_id = {
        str(item.get("id") or "").strip().upper(): item
        for item in items
        if isinstance(item, dict)
    }
    errors: list[str] = []
    for camera_id, (expected_name, expected_stream) in NAMYANGJU_GOLDEN_STREAMS.items():
        item = by_id.get(camera_id)
        if item is None:
            if require_all:
                errors.append(f"{camera_id}: missing golden camera")
            continue
        if str(item.get("source") or "").upper() != "UTIC":
            errors.append(f"{camera_id}: unexpected source={item.get('source')!r}")
        if item.get("name") != expected_name:
            errors.append(f"{camera_id}: name={item.get('name')!r}, expected={expected_name!r}")
        actual_stream = stream_id_from_url(item.get("directUrl") or item.get("url"))
        if actual_stream != expected_stream:
            errors.append(f"{camera_id}: stream={actual_stream or '<missing>'}, expected={expected_stream}")
    return errors


def build_proxy_url(base: str, target_url: str, route: str = "proxy") -> str:
    normalized_base = _normalize_base(base or public_proxy_base())
    return f"{normalized_base}/{route}?url={quote(str(target_url), safe='')}"


def append_query_parameter(url: str, name: str, value: Any) -> str:
    """Return a URL with one query parameter appended when it is absent."""
    parsed = urlparse(str(url))
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if any(existing_name.lower() == name.lower() for existing_name, _ in query):
        return str(url)
    query.append((name, str(value)))
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def remove_query_parameter(url: str, name: str) -> str:
    parsed = urlparse(str(url))
    query = [
        (existing_name, existing_value)
        for existing_name, existing_value in parse_qsl(parsed.query, keep_blank_values=True)
        if existing_name.lower() != name.lower()
    ]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def sanitize_utic_payload(value: Any) -> Any:
    """Remove UTIC credentials recursively before a payload is persisted."""
    if isinstance(value, dict):
        return {key: sanitize_utic_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_utic_payload(item) for item in value]
    if isinstance(value, str) and value.startswith(('http://', 'https://')):
        try:
            if urlparse(value).hostname == 'www.utic.go.kr':
                return remove_query_parameter(value, 'key')
        except ValueError:
            pass
    return value


def atomic_write_text(path: Any, content: str) -> None:
    """Write a complete file before replacing the destination atomically."""
    destination = os.fspath(path)
    parent = os.path.dirname(destination) or "."
    os.makedirs(parent, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{os.path.basename(destination)}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Any, payload: Any, *, sort_keys: bool = True) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=sort_keys) + "\n",
    )
