#!/usr/bin/env python3
"""Validate GitHub Actions YAML and embedded Bash before it reaches main."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPRESSION = re.compile(r"\$\{\{.*?\}\}")


def walk_steps(node):
    if isinstance(node, dict):
        if isinstance(node.get("run"), str):
            yield node
        for value in node.values():
            yield from walk_steps(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_steps(value)


def validate_workflow(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return [f"{path}: invalid YAML: {exc}"]
    for index, step in enumerate(walk_steps(payload), 1):
        shell = str(step.get("shell") or "bash").lower()
        if shell not in {"bash", "sh", "shell"}:
            continue
        source = EXPRESSION.sub("0", step["run"])
        result = subprocess.run(["bash", "-n"], input=source, text=True, capture_output=True)
        if result.returncode:
            label = step.get("name") or f"run block {index}"
            detail = (result.stderr or "syntax check failed").strip().replace("\n", " ")
            errors.append(f"{path}: {label}: {detail}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=sorted((ROOT / ".github" / "workflows").glob("*.yml")))
    args = parser.parse_args()
    errors = [error for path in args.paths for error in validate_workflow(path)]
    if errors:
        print("Workflow validation failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Workflow validation passed: {len(args.paths)} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
