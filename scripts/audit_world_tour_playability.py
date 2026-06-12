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


def normalize_world_tour_playback_item(item: dict) -> dict:
    normalized = dict(item or {})
    if normalized.get('embedUrl') and not world.is_valid_embed_url(normalized.get('embedUrl')):
        blocked_embed = normalized.pop('embedUrl', None)
        normalized['blockedEmbedUrl'] = blocked_embed
        normalized['directPlaybackStatus'] = 'source_site_only'
        normalized['sourceOnly'] = True
        normalized['sourceOnlyReason'] = 'invalid_or_unstable_embed_url'
        normalized['playbackStatus'] = 'source-only'
    return normalized


def probe_direct_stream(url: str) -> tuple[bool, str]:
    value = str(url or '').strip()
    if not value:
        return False, 'missing_url'
    if value.lower().split('?', 1)[0].endswith('.m3u8'):
        try:
            text = world.fetch_text(value, timeout=12, cache=False)
        except Exception as error:
            return False, f'{type(error).__name__}: {error}'
        if '#EXTM3U' in text:
            return True, 'hls_manifest_ok'
        return False, 'not_hls_manifest'
    return True, 'direct_url_present'


def audit_item(item: dict) -> dict | None:
    item = normalize_world_tour_playback_item(item)
    if world.is_snapshot_only_item(item):
        return None

    if item.get('sourceUrl'):
        item = world.refresh_source_video_id(item)

    if item.get('videoId'):
        item = world.validate_youtube_item(item)
    else:
        item['lastCheckedAt'] = dt.date.today().isoformat()
        if item.get('playUrl'):
            ok, reason = probe_direct_stream(item.get('playUrl'))
            item['directProbeStatus'] = reason
            item['playbackStatus'] = 'verified' if ok else 'source-only'
            item['sourceOnly'] = not ok
            if ok:
                item['directPlaybackStatus'] = 'direct_hls' if '.m3u8' in str(item.get('playUrl')).lower() else 'direct_video'
                item.pop('sourceOnlyReason', None)
            else:
                item['directPlaybackStatus'] = 'source_site_only'
                item['sourceOnlyReason'] = 'direct_stream_probe_failed'
        elif world.is_valid_embed_url(item.get('embedUrl')):
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
        'Snapshot-only feeds are excluded; unavailable/embed-disabled/source-only feeds are retained but not treated as in-app playable.'
    )
    meta['playbackStatusCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in audited))
    meta['sourceOnlyCount'] = sum(1 for item in audited if item.get('sourceOnly'))
    meta['sourceTypeHealth'] = {
        source: {
            'total': total,
            'verified': verified,
            'sourceOnly': source_only,
            'unchecked': unchecked,
            'unavailable': unavailable,
            'embedDisabled': embed_disabled,
        }
        for source, total, verified, source_only, unchecked, unavailable, embed_disabled in (
            (
                source,
                len(source_items),
                sum(1 for item in source_items if item.get('playbackStatus') == 'verified' and not item.get('sourceOnly')),
                sum(1 for item in source_items if item.get('sourceOnly')),
                sum(1 for item in source_items if item.get('playbackStatus') == 'unchecked'),
                sum(1 for item in source_items if item.get('playbackStatus') == 'unavailable'),
                sum(1 for item in source_items if item.get('playbackStatus') == 'embed_disabled'),
            )
            for source, source_items in sorted(
                {
                    key: [item for item in audited if (item.get('sourceType') or 'unknown') == key]
                    for key in sorted({item.get('sourceType') or 'unknown' for item in audited})
                }.items()
            )
        )
    }
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
