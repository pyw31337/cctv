#!/usr/bin/env python3
"""Track catalog size and in-app playability after every collector mutation.

The report never removes a camera. It records what a strict in-app-only catalog
*would* contain, so transient upstream failures cannot silently shrink either
the domestic or world directory.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cctv_runtime import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]
DIRECT_PATTERN = re.compile(r"(?:\.m3u8|\.mp4|/(?:gits|kb|jeju)\?|workers\.dev|sslip\.io)", re.I)


def load(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def domestic_report(cameras: list[dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
    evidence = quality.get("cameras", {}) if isinstance(quality, dict) else {}
    direct = verified = 0
    sources = Counter()
    for item in cameras:
        source = str(item.get("source") or "UNKNOWN")
        url = str(item.get("directUrl") or item.get("url") or "")
        if DIRECT_PATTERN.search(url): direct += 1
        metrics = evidence.get(str(item.get("id") or ""), {}) if isinstance(evidence, dict) else {}
        failure_rate = metrics.get("failure_rate") if isinstance(metrics, dict) else None
        if isinstance(metrics, dict) and int(metrics.get("samples") or 0) >= 3 and float(metrics.get("success_rate") or 0) >= .8 and float(1 if failure_rate is None else failure_rate) <= .2:
            verified += 1
            sources[source] += 1
    total = len(cameras)
    return {"total": total, "native_or_proxy_candidate": direct, "recently_verified_in_app": verified, "strict_removed_if_verified_only": max(0, total - verified), "verified_retention_rate": round(verified / total, 4) if total else 0, "verified_by_source": dict(sorted(sources.items())), "definition": "Recent in-app evidence requires >=3 samples, >=80% success, and <=20% failure. URL candidates are reported separately and are not proof of playback."}


def world_report(payload: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in (payload.get("items", []) if isinstance(payload, dict) else []) if isinstance(item, dict)]
    verified = [item for item in items if item.get("playbackStatus") == "verified" and not item.get("sourceOnly") and (item.get("videoId") or item.get("embedUrl") or item.get("playUrl"))]
    native = [item for item in verified if item.get("playUrl")]
    total = len(items)
    reasons = Counter(str(item.get("sourceOnlyReason") or item.get("playbackStatus") or "unknown") for item in items if item not in verified)
    return {"total": total, "strict_in_app_playable": len(verified), "native_video_or_hls": len(native), "embed_or_youtube_in_app": len(verified) - len(native), "strict_removed_if_in_app_only": max(0, total - len(verified)), "strict_retention_rate": round(len(verified) / total, 4) if total else 0, "excluded_reason_counts": dict(reasons.most_common()), "definition": "In-app means a currently verified public playUrl, embedUrl, or YouTube videoId. Source-site-only and unchecked entries are excluded in strict mode but remain in the master catalog."}


def delta(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, int]:
    if not isinstance(previous, dict): return {}
    result = {}
    for catalog in ("domestic", "world"):
        before, after = previous.get(catalog, {}), current.get(catalog, {})
        if not isinstance(before, dict) or not isinstance(after, dict): continue
        for key in ("total", "recently_verified_in_app", "strict_in_app_playable", "strict_removed_if_verified_only", "strict_removed_if_in_app_only"):
            if key in before and key in after: result[f"{catalog}.{key}"] = int(after[key]) - int(before[key])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", default="manual")
    parser.add_argument("--domestic", default=str(ROOT / "cctv_data.json")); parser.add_argument("--world", default=str(ROOT / "data" / "world_tour_cams.json")); parser.add_argument("--quality", default=str(ROOT / "data" / "quality_summary.json")); parser.add_argument("--output", default=str(ROOT / "data" / "catalog_playability_report.json")); parser.add_argument("--history", default=str(ROOT / "data" / "catalog_playability_history.json"))
    args = parser.parse_args()
    old = load(Path(args.output), {})
    report = {"schema": "cctv-catalog-playability-v1", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "event": args.event, "domestic": domestic_report(load(Path(args.domestic), []), load(Path(args.quality), {})), "world": world_report(load(Path(args.world), {}))}
    report["delta_since_previous"] = delta(old, report)
    history = load(Path(args.history), [])
    if not isinstance(history, list): history = []
    history.append({"generated_at": report["generated_at"], "event": args.event, "domestic": report["domestic"], "world": report["world"], "delta": report["delta_since_previous"]})
    atomic_write_json(Path(args.output), report, sort_keys=True)
    atomic_write_json(Path(args.history), history[-180:], sort_keys=False)
    print(json.dumps({"domestic": report["domestic"]["total"], "domestic_verified": report["domestic"]["recently_verified_in_app"], "world": report["world"]["total"], "world_strict": report["world"]["strict_in_app_playable"], "delta": report["delta_since_previous"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
