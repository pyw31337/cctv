#!/usr/bin/env python3
"""Remove embedded UTIC API keys from static JSON camera data."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from cctv_runtime import atomic_write_text


URL_RE = re.compile(r'(?P<quote>["\'])(?P<url>https?://www\.utic\.go\.kr/[^"\']+)(?P=quote)')


def scrub_text(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        raw_url = match.group('url')
        parsed = urlparse(raw_url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        scrubbed = [(name, value) for name, value in query if name.lower() != 'key']
        if len(scrubbed) == len(query):
            return match.group(0)
        count += 1
        clean_url = urlunparse(parsed._replace(query=urlencode(scrubbed, doseq=True)))
        return f"{match.group('quote')}{clean_url}{match.group('quote')}"

    return URL_RE.sub(replace, text), count


def scrub_file(path: Path) -> int:
    original = path.read_text(encoding='utf-8')
    scrubbed, count = scrub_text(original)
    if count:
        json.loads(scrubbed)
        atomic_write_text(path, scrubbed)
    return count


def main() -> int:
    paths = [Path(value) for value in sys.argv[1:]]
    if not paths:
        print('usage: scrub_utic_data_keys.py <json-file> [...]', file=sys.stderr)
        return 2
    total = 0
    for path in paths:
        count = scrub_file(path)
        total += count
        print(f'{path}: scrubbed {count} URL(s)')
    print(f'total: scrubbed {total} URL(s)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
