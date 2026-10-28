#!/usr/bin/env python3
"""Build a non-destructive recovery plan from the latest service evidence."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from cctv_runtime import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def build_plan(ops: dict, canary: dict, now: datetime) -> dict:
    service_status = str(ops.get("service_status") or "UNKNOWN")
    canary_status = str(canary.get("overall_status") or "UNKNOWN")
    z3 = ((ops.get("cache") or {}).get("z3") or {})
    z3_severity = str(z3.get("severity") or "unknown")
    impacted = service_status == "SERVICE_IMPACT" or canary_status == "SERVICE_IMPACT" or z3_severity == "danger"
    degraded = service_status == "DEGRADED" or canary_status == "DEGRADED" or z3_severity == "warn"
    mode = "RECOVERY_REQUIRED" if impacted else "SAFE_MODE" if degraded else "NORMAL"
    actions = [
        "preserve_last_known_good_catalog",
        "use_static_health_and_quality_fallback",
        "keep_verified_mappings_locked",
    ]
    if impacted or degraded:
        actions.extend(["refresh_z3_cache", "run_core_canary_recovery", "renew_due_provider_urls"])
    return {
        "schema": "cctv-recovery-plan-v1",
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "automatic_actions": actions,
        "service_status": service_status,
        "canary_status": canary_status,
        "z3": {"status": z3.get("status"), "severity": z3_severity, "age_hours": z3.get("age_hours")},
        "safety": {
            "catalog_mutation": "blocked_until_data_preservation_guard_passes",
            "mapping_promotion": "blocked_until_independent_verification",
            "fallback": "static_last_known_good_snapshot",
        },
        "operator_message": "외부 스트림 장애는 매핑을 바꾸지 않고 캐시·토큰·카나리 순서로 복구합니다." if mode != "NORMAL" else "정상 운영 상태입니다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ops", default=str(ROOT / "data" / "ops_status.json"))
    parser.add_argument("--canary", default=str(ROOT / "data" / "canary_status.json"))
    parser.add_argument("--output", default=str(ROOT / "data" / "recovery_status.json"))
    args = parser.parse_args()
    plan = build_plan(load(Path(args.ops), {}), load(Path(args.canary), {}), datetime.now(timezone.utc))
    atomic_write_json(Path(args.output), plan, sort_keys=True)
    print(json.dumps({"mode": plan["mode"], "actions": len(plan["automatic_actions"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
