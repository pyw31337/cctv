#!/usr/bin/env python3
"""Validate persisted camera JSON and reject embedded UTIC credentials."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from cctv_runtime import validate_namyangju_golden_mappings, validate_stream_identity


DEFAULT_FILES = (
    'cctv_data.json',
    'cctv_data_new.json',
    'data/cctv_core.json',
    'data/cctv_extended.json',
    'cctv_overrides.json',
    'cctv_data_pre_audit_v2.json',
    'cctv_data_test.json',
    'data/status.json',
)


def count_embedded_utic_keys(value) -> int:
    if isinstance(value, dict):
        return sum(count_embedded_utic_keys(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_embedded_utic_keys(item) for item in value)
    if isinstance(value, str) and value.startswith(('http://', 'https://')):
        parsed = urlparse(value)
        if parsed.hostname == 'www.utic.go.kr':
            return sum(name.lower() == 'key' for name, _ in parse_qsl(parsed.query))
    return 0


def validate_file(path: Path) -> int:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        print(f'{path}: missing', file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f'{path}: invalid JSON ({exc})', file=sys.stderr)
        return 1

    embedded = count_embedded_utic_keys(payload)
    if embedded:
        print(f'{path}: embedded UTIC keys={embedded}', file=sys.stderr)
        return 1
    if path.name in {'cctv_data.json', 'cctv_core.json'} and isinstance(payload, list):
        errors = validate_namyangju_golden_mappings(payload, require_all=True)
        if errors:
            for error in errors:
                print(f'{path}: {error}', file=sys.stderr)
            return 1
        identity_errors = validate_stream_identity(payload)
        if identity_errors:
            for error in identity_errors:
                print(f'{path}: {error}', file=sys.stderr)
            return 1
    print(f'{path}: OK')
    return 0


def main() -> int:
    paths = [Path(value) for value in sys.argv[1:]] or [Path(value) for value in DEFAULT_FILES]
    return 1 if any(validate_file(path) for path in paths) else 0


if __name__ == '__main__':
    raise SystemExit(main())
