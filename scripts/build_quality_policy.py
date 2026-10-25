#!/usr/bin/env python3
"""Build a conservative telemetry-backed CCTV ranking and repair policy."""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from cctv_runtime import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]

def load(path: Path, fallback: Any) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return fallback

def number(value: Any, default: float = 0) -> float:
    try: return float(value)
    except (TypeError, ValueError): return default

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def age_hours(value: Any, now: datetime) -> float | None:
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return max(0, (now - (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)).total_seconds() / 3600)
    except (TypeError, ValueError): return None

def score(metrics: dict[str, Any], now: datetime) -> tuple[int, int, str, str | None]:
    samples = max(0, int(number(metrics.get("samples") or metrics.get("total"))))
    success = clamp(number(metrics.get("success_rate"), 1 if samples else 0), 0, 1)
    failure = clamp(number(metrics.get("failure_rate"), 1 - success), 0, 1)
    slow, fallback = clamp(number(metrics.get("slow_rate")), 0, 1), clamp(number(metrics.get("fallback_rate")), 0, 1)
    first_frame = max(0, number(metrics.get("avg_first_frame_ms")))
    pixels = max(0, number(metrics.get("avg_width"))) * max(0, number(metrics.get("avg_height")))
    freshness = age_hours(metrics.get("updated_at") or metrics.get("last_seen_at"), now)
    value = 36 + success * 42 - failure * 38 - slow * 10 - fallback * 6
    value += -10 if first_frame > 12000 else -6 if first_frame > 8000 else 4 if first_frame and first_frame < 3500 else 0
    value += 5 if pixels >= 1280 * 720 else -4 if pixels and pixels < 640 * 360 else 0
    if freshness is not None and freshness > 48: value -= min(12, 3 + (freshness - 48) / 12)
    confidence = round(clamp(samples / 20, 0, 1) * 100)
    if samples < 3: value = (value * .35) + 55 * .65
    value = round(clamp(value, 0, 100))
    if samples >= 5 and (failure >= .45 or success < .45): return value, confidence, "repair", "probe_stream"
    if samples >= 5 and (slow >= .4 or first_frame > 10000): return value, confidence, "watch", "measure_startup"
    if freshness is not None and freshness > 72: return value, confidence, "watch", "refresh_evidence"
    return value, confidence, "preferred" if value >= 75 else "watch", None

def review_interval_hours(tier: str, score_value: int, confidence: int) -> int:
    """Shorten verification only where evidence says users are at risk."""
    if tier == "repair": return 6
    if confidence < 20: return 24
    if tier == "watch" or score_value < 75: return 24
    return 72

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", default=str(ROOT / "data" / "quality_summary.json"))
    parser.add_argument("--output", default=str(ROOT / "data" / "quality_policy.json"))
    parser.add_argument("--queue", default=str(ROOT / "data" / "quality_repair_queue.json"))
    args = parser.parse_args()
    summary, now = load(Path(args.summary), {}), datetime.now(timezone.utc)
    cameras = summary.get("cameras", {}) if isinstance(summary, dict) else {}
    sources = summary.get("sources", {}) if isinstance(summary, dict) else {}
    camera_policy, source_policy, queue = {}, {}, []
    for camera_id, metrics in cameras.items():
        if not isinstance(metrics, dict): continue
        quality, confidence, tier, action = score(metrics, now)
        interval = review_interval_hours(tier, quality, confidence)
        camera_policy[str(camera_id)] = {"score": quality, "confidence": confidence, "tier": tier, "review_interval_hours": interval}
        if action: queue.append({"id": str(camera_id), "name": str(metrics.get("camera_name") or camera_id), "source": str(metrics.get("source") or "UNKNOWN"), "score": quality, "action": action, "review_interval_hours": interval, "updated_at": metrics.get("updated_at")})
    for source, metrics in sources.items():
        if not isinstance(metrics, dict): continue
        quality, confidence, tier, action = score(metrics, now)
        interval = review_interval_hours(tier, quality, confidence)
        source_policy[str(source)] = {"score": quality, "confidence": confidence, "tier": tier, "review_interval_hours": interval}
        if action and tier == "repair": queue.append({"id": f"source:{source}", "name": str(source), "source": str(source), "score": quality, "action": action, "review_interval_hours": interval, "updated_at": metrics.get("updated_at")})
    queue.sort(key=lambda item: (item["score"], item["source"], item["id"]))
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    atomic_write_json(Path(args.output), {"schema": "cctv-quality-policy-v1", "generated_at": stamp, "policy": "Telemetry adjusts ranking only. Locked mappings require independent verification before promotion.", "cameras": camera_policy, "sources": source_policy}, sort_keys=True)
    atomic_write_json(Path(args.queue), {"schema": "cctv-quality-repair-queue-v1", "generated_at": stamp, "items": queue[:1000]}, sort_keys=True)
    print(json.dumps({"cameras": len(camera_policy), "sources": len(source_policy), "repair_items": len(queue[:1000])}, ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
