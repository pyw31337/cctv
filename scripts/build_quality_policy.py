#!/usr/bin/env python3
"""Build a conservative telemetry-backed CCTV ranking and repair policy."""
from __future__ import annotations
import argparse
import json
from collections import defaultdict
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


def issue_group(metrics: dict[str, Any], tier: str, quality: int) -> tuple[str, str, str]:
    """Return a stable operational group, issue label, and operator action."""
    source = str(metrics.get("source") or "UNKNOWN").strip() or "UNKNOWN"
    region = str(metrics.get("region") or "UNKNOWN").strip() or "UNKNOWN"
    samples = max(0, int(number(metrics.get("samples") or metrics.get("total"))))
    failure = clamp(number(metrics.get("failure_rate"), 0), 0, 1)
    success = clamp(number(metrics.get("success_rate"), 1 if samples else 0), 0, 1)
    slow = clamp(number(metrics.get("slow_rate"), 0), 0, 1)
    fallback = clamp(number(metrics.get("fallback_rate"), 0), 0, 1)
    first_frame = max(0, number(metrics.get("avg_first_frame_ms")))
    pixels = max(0, number(metrics.get("avg_width"))) * max(0, number(metrics.get("avg_height")))

    # Do not call a camera broken from one or two observations. Keep it in a
    # fast evidence-collection group until the direct probe has enough samples.
    if samples < 5:
        issue, action = "insufficient_evidence", "collect_more_evidence"
    elif tier == "repair" or failure >= .45 or success < .45:
        issue, action = "connection_failure", "reprobe_and_inspect_provider"
    elif fallback >= .35:
        issue, action = "fallback_heavy", "repair_primary_stream_and_mapping"
    elif slow >= .4 or first_frame > 10000:
        issue, action = "slow_startup", "check_token_proxy_and_origin_latency"
    elif pixels and pixels < 640 * 360:
        issue, action = "low_resolution", "prefer_higher_quality_variant"
    elif tier == "watch":
        issue, action = "stale_or_degraded", "increase_check_frequency"
    else:
        issue, action = "healthy", "maintain_cadence"

    return f"{source}:{region}:{issue}", issue, action


def build_group_rollups(cameras: dict[str, Any], now: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "camera_ids": [], "scores": [], "confidences": [], "samples": 0,
        "success": 0.0, "failure": 0.0, "slow": 0.0, "fallback": 0.0,
        "source": "UNKNOWN", "region": "UNKNOWN", "issue": "unknown",
        "recommended_action": "maintain_cadence",
    })
    for camera_id, metrics in cameras.items():
        if not isinstance(metrics, dict):
            continue
        quality, confidence, tier, _ = score(metrics, now)
        group_key, issue, action = issue_group(metrics, tier, quality)
        group = groups[group_key]
        group["camera_ids"].append(str(camera_id))
        group["scores"].append(quality)
        group["confidences"].append(confidence)
        group["samples"] += max(0, int(number(metrics.get("samples") or metrics.get("total"))))
        group["success"] += number(metrics.get("success_rate"), 0)
        group["failure"] += number(metrics.get("failure_rate"), 0)
        group["slow"] += number(metrics.get("slow_rate"), 0)
        group["fallback"] += number(metrics.get("fallback_rate"), 0)
        group["source"] = str(metrics.get("source") or "UNKNOWN")
        group["region"] = str(metrics.get("region") or "UNKNOWN")
        group["issue"] = issue
        group["recommended_action"] = action

    output: dict[str, Any] = {}
    queue: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        count = max(1, len(group["camera_ids"]))
        average_score = round(sum(group["scores"]) / count)
        average_confidence = round(sum(group["confidences"]) / count)
        issue = group["issue"]
        tier = "repair" if issue in {"connection_failure", "fallback_heavy"} else "watch" if issue != "healthy" else "preferred"
        interval = 6 if tier == "repair" else 24 if tier == "watch" else 72
        item = {
            "source": group["source"],
            "region": group["region"],
            "issue": issue,
            "camera_count": count,
            "camera_ids": group["camera_ids"][:200],
            "score": average_score,
            "confidence": average_confidence,
            "tier": tier,
            "review_interval_hours": interval,
            "recommended_action": group["recommended_action"],
            "avg_failure_rate": round(group["failure"] / count, 4),
            "avg_slow_rate": round(group["slow"] / count, 4),
            "avg_fallback_rate": round(group["fallback"] / count, 4),
            "samples": group["samples"],
        }
        output[key] = item
        if tier == "repair":
            queue.append({"id": f"group:{key}", "name": key, "source": group["source"], "score": average_score, "action": group["recommended_action"], "review_interval_hours": interval, "camera_count": count})
    return output, queue

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
        group_key, issue, action = issue_group(metrics, tier, quality)
        camera_policy[str(camera_id)] = {"score": quality, "confidence": confidence, "tier": tier, "issue": issue, "group": group_key, "review_interval_hours": interval}
        if action: queue.append({"id": str(camera_id), "name": str(metrics.get("camera_name") or camera_id), "source": str(metrics.get("source") or "UNKNOWN"), "score": quality, "action": action, "review_interval_hours": interval, "updated_at": metrics.get("updated_at")})
    for source, metrics in sources.items():
        if not isinstance(metrics, dict): continue
        quality, confidence, tier, action = score(metrics, now)
        interval = review_interval_hours(tier, quality, confidence)
        source_policy[str(source)] = {"score": quality, "confidence": confidence, "tier": tier, "review_interval_hours": interval}
        if action and tier == "repair": queue.append({"id": f"source:{source}", "name": str(source), "source": str(source), "score": quality, "action": action, "review_interval_hours": interval, "updated_at": metrics.get("updated_at")})
    groups, group_queue = build_group_rollups(cameras, now)
    queue.extend(group_queue)
    queue.sort(key=lambda item: (item["score"], item["source"], item["id"]))
    # A large camera queue must not hide the group-level repair signal. Keep
    # every repair group visible, then fill the remaining budget with the
    # lowest-scoring camera/source entries.
    group_ids = {item["id"] for item in group_queue}
    ordered_groups = sorted(group_queue, key=lambda item: (item["score"], item["source"], item["id"]))
    ordered_individuals = [item for item in queue if item["id"] not in group_ids]
    queue_for_output = (ordered_groups + ordered_individuals)[:1000]
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    policy = {"schema": "cctv-quality-policy-v2", "generated_at": stamp, "policy": "Telemetry adjusts ranking only. Locked mappings require independent verification before promotion.", "cameras": camera_policy, "sources": source_policy, "groups": groups}
    atomic_write_json(Path(args.output), policy, sort_keys=True)
    atomic_write_json(Path(args.queue), {"schema": "cctv-quality-repair-queue-v2", "generated_at": stamp, "items": queue_for_output}, sort_keys=True)

    history_path = ROOT / "data" / "quality_group_history.json"
    history = load(history_path, [])
    if not isinstance(history, list): history = []
    history.append({"generated_at": stamp, "groups": {key: {k: value for k, value in item.items() if k not in {"camera_ids"}} for key, item in groups.items()}, "repair_group_count": len(group_queue)})
    atomic_write_json(history_path, history[-180:], sort_keys=True)
    print(json.dumps({"cameras": len(camera_policy), "sources": len(source_policy), "groups": len(groups), "repair_items": len(queue_for_output), "repair_groups": len(group_queue)}, ensure_ascii=False))
    return 0

if __name__ == "__main__": raise SystemExit(main())
