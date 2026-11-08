#!/usr/bin/env python3
"""Classify recent GitHub Actions failures and apply bounded remediation.

This controller deliberately does not rewrite production code or camera data.
It can safely retry a failed job once when the failure is likely transient,
records the evidence, and opens one deduplicated operator issue after repeated
failures. A workflow/configuration failure is never blindly retried forever.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "automation_remediation.json"
WINDOW_HOURS = 36
MAX_RUNS = 80
MAX_RETRIES_PER_EXECUTION = 6
RETRYABLE = {"provider_external", "browser_external", "runner_dependency"}
NON_RETRYABLE = {"workflow_configuration", "unknown"}


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_time(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


class GitHub:
    def __init__(self, token: str, repo: str, dry_run: bool = False):
        self.token = token
        self.repo = repo
        self.dry_run = dry_run

    def request(self, method: str, path: str, body: dict | None = None):
        url = f"https://api.github.com/repos/{self.repo}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "cctv-actions-remediator",
                **({"Content-Type": "application/json"} if data else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
                return json.loads(raw.decode()) if raw else {}
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            raise RuntimeError(f"GitHub API {method} {path}: HTTP {error.code}: {detail}") from error

    def list_runs(self):
        payload = self.request("GET", f"/actions/runs?per_page={MAX_RUNS}")
        return payload.get("workflow_runs", []) if isinstance(payload, dict) else []

    def jobs(self, run_id: int):
        payload = self.request("GET", f"/actions/runs/{run_id}/jobs?per_page=100")
        return payload.get("jobs", []) if isinstance(payload, dict) else []

    def rerun_failed(self, run_id: int):
        if self.dry_run:
            return "dry_run"
        self.request("POST", f"/actions/runs/{run_id}/rerun-failed-jobs")
        return "rerun_failed_jobs"

    def open_issue(self, title: str, body: str):
        if self.dry_run:
            return "dry_run"
        issues = self.request("GET", "/issues?state=open&per_page=100")
        if any(isinstance(issue, dict) and issue.get("title") == title for issue in issues or []):
            return "issue_exists"
        created = self.request(
            "POST",
            "/issues",
            {"title": title, "body": body, "labels": ["automated-remediation"]},
        )
        return created.get("html_url") or "issue_created"


def classify_run(run: dict, jobs: list[dict]) -> tuple[str, list[str]]:
    workflow = str(run.get("name") or run.get("workflow_name") or "").lower()
    failed_steps = []
    for job in jobs:
        for step in job.get("steps") or []:
            if step.get("conclusion") == "failure":
                failed_steps.append(str(step.get("name") or "unknown"))
    haystack = " ".join([workflow, *failed_steps]).lower()
    if any(token in haystack for token in ("yaml", "workflow syntax", "invalid workflow", "set up job")):
        return "workflow_configuration", failed_steps
    if any(token in haystack for token in ("install", "checkout", "setup python", "setup node", "playwright install")):
        return "runner_dependency", failed_steps
    if any(token in haystack for token in ("browser", "canary", "playback")):
        return "browser_external", failed_steps
    if any(token in haystack for token in ("renew", "ingest", "audit", "refresh", "quality", "z3", "cctv")):
        return "provider_external", failed_steps
    return "unknown", failed_steps


def recent_failures(runs: list[dict], now: dt.datetime) -> list[dict]:
    cutoff = now - dt.timedelta(hours=WINDOW_HOURS)
    return [
        run for run in runs
        if run.get("conclusion") == "failure"
        and parse_time(run.get("created_at")) >= cutoff
        and run.get("name") != "Actions Failure Auto-Remediation"
    ]


def run_controller(gh: GitHub, output: Path, execute: bool = True) -> dict:
    now = now_utc()
    runs = recent_failures(gh.list_runs(), now)
    records = []
    by_workflow = defaultdict(list)
    retry_budget = MAX_RETRIES_PER_EXECUTION
    for run in runs:
        run_id = int(run["id"])
        jobs = gh.jobs(run_id)
        category, failed_steps = classify_run(run, jobs)
        entry = {
            "run_id": run_id,
            "workflow": run.get("name") or "unknown",
            "created_at": run.get("created_at"),
            "attempt": run.get("run_attempt", 1),
            "category": category,
            "failed_steps": failed_steps,
            "action": "observe_only",
        }
        by_workflow[entry["workflow"]].append(entry)
        # GitHub's run_attempt protects against repeatedly retrying the same run.
        if execute and retry_budget > 0 and category in RETRYABLE and int(run.get("run_attempt") or 1) < 2:
            entry["action"] = gh.rerun_failed(run_id)
            retry_budget -= 1
        records.append(entry)

    repeated = []
    for workflow, entries in by_workflow.items():
        if len(entries) >= 3:
            categories = Counter(entry["category"] for entry in entries)
            repeated.append({"workflow": workflow, "failures": len(entries), "categories": dict(categories)})

    issue_actions = []
    for item in repeated:
        title = f"[auto-remediation] Repeated workflow failures: {item['workflow']}"
        body = (
            "자동 장애관리기가 최근 36시간 동안 같은 워크플로우의 반복 실패를 감지했습니다.\n\n"
            f"- 워크플로우: `{item['workflow']}`\n"
            f"- 실패 횟수: `{item['failures']}`\n"
            f"- 분류: `{json.dumps(item['categories'], ensure_ascii=False)}`\n\n"
            "일시적 공급처/브라우저 장애는 제한적으로 재실행했으며, 반복되는 설정·데이터·공급처 문제는 무한 재시도하지 않고 이 이슈로 승격했습니다."
        )
        issue_actions.append({"workflow": item["workflow"], "action": gh.open_issue(title, body) if execute else "dry_run"})

    report = {
        "generated_at": now.isoformat(),
        "window_hours": WINDOW_HOURS,
        "failure_count": len(records),
        "retry_budget_used": MAX_RETRIES_PER_EXECUTION - retry_budget,
        "records": records,
        "repeated_workflows": repeated,
        "issue_actions": issue_actions,
        "policy": {
            "retryable": sorted(RETRYABLE),
            "non_retryable": sorted(NON_RETRYABLE),
            "max_retries_per_run": 1,
            "max_retries_per_execution": MAX_RETRIES_PER_EXECUTION,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    token = os.getenv("GITHUB_TOKEN", "").strip()
    repo = os.getenv("GITHUB_REPOSITORY", "pyw31337/cctv").strip()
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2
    try:
        report = run_controller(GitHub(token, repo, dry_run=args.dry_run), Path(args.output), execute=not args.dry_run)
    except Exception as error:
        print(f"auto-remediation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "failures": report["failure_count"],
        "retries": report["retry_budget_used"],
        "repeated_workflows": report["repeated_workflows"],
        "issues": report["issue_actions"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
