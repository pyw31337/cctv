#!/usr/bin/env python3
"""Run deterministic daily checks and write one compact operations report."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cctv_runtime import atomic_write_json

ROOT = Path(__file__).resolve().parents[1]


def run_check(name: str, command: list[str], timeout: int) -> dict:
    try:
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        return {"name": name, "status": "pass" if completed.returncode == 0 else "fail", "exit_code": completed.returncode, "output": output[-4000:]}
    except subprocess.TimeoutExpired as exc:
        return {"name": name, "status": "timeout", "exit_code": None, "output": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "daily_quality_report.json")
    args = parser.parse_args()
    python = sys.executable
    checks = [
        run_check("workflow_syntax", [python, "scripts/validate_workflows.py"], 120),
        run_check("regression_tests", [python, "-m", "unittest", "discover", "-p", "test_*.py"], 900),
        run_check("static_data", [python, "scripts/validate_static_data.py"], 180),
        run_check("python_compile", [python, "-m", "compileall", "-q", "scripts", "server"], 180),
    ]
    failed = [item["name"] for item in checks if item["status"] != "pass"]
    recovery = {}
    recovery_path = ROOT / "data" / "recovery_status.json"
    try:
        recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        recovery = {"mode": "UNKNOWN"}
    report = {
        "schema": "cctv-daily-quality-report-v1",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "attention" if failed else "healthy",
        "failed_checks": failed,
        "checks": checks,
        "recovery_mode": recovery.get("mode", "UNKNOWN"),
        "next_action": "수동 원인 확인과 수정 후 재검증" if failed else "현재 주기의 자동 점검을 계속 수행",
    }
    atomic_write_json(args.output, report, sort_keys=True)
    print(json.dumps({"status": report["status"], "failed_checks": failed}, ensure_ascii=False))
    # The scheduled maintenance job records findings even when an external or
    # flaky check fails. The merge Quality Gate remains strict for changes.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
