#!/usr/bin/env python3
"""Refresh playability metadata for the existing global CCTV directory.

This is intentionally lighter than a full collection run: it keeps every known
source record, removes snapshot-only records from the user-facing list, rejects
bogus embeds such as analytics iframes, and refreshes YouTube live playability
so ended/unavailable live streams stop appearing as green in-app videos.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'data' / 'world_tour_cams.json'
sys.path.insert(0, str(ROOT / 'scripts'))
import build_world_tour_cams as world  # noqa: E402


def audit_item(item: dict) -> dict | None:
    item = world.normalize_world_tour_playback_item(item)
    if world.is_snapshot_only_item(item):
        return None
    if item.get('videoId'):
        item = world.validate_youtube_item(item)
    else:
        item['lastCheckedAt'] = dt.date.today().isoformat()
        if world.is_valid_embed_url(item.get('embedUrl')) or world.is_valid_embed_url(item.get('playUrl')):
            item['playbackStatus'] = 'verified'
            item['sourceOnly'] = False
        elif item.get('sourceUrl'):
            item['playbackStatus'] = 'source-only'
            item['sourceOnly'] = True
        else:
            item['playbackStatus'] = 'unchecked'
            item['sourceOnly'] = True
    return world.enrich_item_quality(item)


def run(path: Path, max_workers: int = 10) -> dict:
    payload = json.loads(path.read_text(encoding='utf-8'))
    items = payload.get('items', [])
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        audited = [item for item in executor.map(audit_item, items) if item]
    audited = [item for item in audited if item.get('playbackStatus') != 'unavailable']
    audited.sort(
        key=lambda item: (
            0 if world.is_in_app_video_item(item) and not item.get('sourceOnly') else 1,
            -int(item.get('qualityScore') or item.get('stabilityScore') or item.get('priority') or 0),
            str(item.get('title') or ''),
        )
    )
    payload['items'] = audited
    meta = payload.setdefault('collectionMeta', {})
    meta['itemCount'] = len(audited)
    meta['lastPlayabilityAuditAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    meta['playabilityAuditPolicy'] = (
        'Snapshot-only feeds and unavailable YouTube lives are excluded; source-only feeds are retained but not treated as in-app playable.'
    )
    meta['playbackStatusCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in audited))
    meta['sourceOnlyCount'] = sum(1 for item in audited if item.get('sourceOnly'))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'items': len(audited),
        'status': meta['playbackStatusCounts'],
        'sourceOnly': meta['sourceOnlyCount'],
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--workers', type=int, default=10)
    args = parser.parse_args(argv)
    result = run(args.input, args.workers)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
