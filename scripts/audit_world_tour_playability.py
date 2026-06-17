#!/usr/bin/env python3
"""Refresh playability metadata for the existing global CCTV directory.

This is intentionally lighter than a full collection run: it removes
still-image-only and source-site-only records from the user-facing list, rejects
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


def parse_date(value: object) -> dt.datetime:
    text = str(value or '').strip()
    if not text:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    try:
        if len(text) == 10:
            return dt.datetime.fromisoformat(text).replace(tzinfo=dt.timezone.utc)
        parsed = dt.datetime.fromisoformat(text.replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def audit_priority(item: dict) -> tuple:
    """Oldest and highest-risk items are audited first when using --max-items."""
    status = str(item.get('playbackStatus') or 'unchecked').lower()
    source_only = bool(item.get('sourceOnly'))
    source_type = str(item.get('sourceType') or '')
    risky_source = source_type in {'livebeaches', 'hdontap', 'worldcam', 'youtube-search', 'webcamera24'}
    status_rank = {
        'unchecked': 0,
        'unavailable': 1,
        'embed_disabled': 1,
        'source-only': 2,
        'verified': 3,
    }.get(status, 1)
    return (
        parse_date(item.get('lastCheckedAt')),
        status_rank,
        0 if risky_source else 1,
        0 if source_only else 1,
        str(item.get('id') or item.get('title') or ''),
    )


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


def select_audit_items(items: list[dict], max_items: int | None = None) -> tuple[list[dict], set[str]]:
    if not max_items or max_items <= 0 or max_items >= len(items):
        selected = list(items)
    else:
        selected = sorted(items, key=audit_priority)[:max_items]
    selected_ids = {str(item.get('id') or '') for item in selected}
    return selected, selected_ids


def run(path: Path, max_workers: int = 10, max_items: int | None = None) -> dict:
    payload = json.loads(path.read_text(encoding='utf-8'))
    raw_items = payload.get('items', [])
    items = [item for item in raw_items if not world.is_snapshot_only_item(item)]
    still_image_only_removed = len(raw_items) - len(items)
    selected_items, selected_ids = select_audit_items(items, max_items)
    preserved_items = [item for item in items if str(item.get('id') or '') not in selected_ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        audited_selected = [item for item in executor.map(audit_item, selected_items) if item]
    audited_before_playback_filter = audited_selected + preserved_items
    audited = [item for item in audited_before_playback_filter if world.is_user_facing_world_tour_item(item)]
    app_playback_removed = len(audited_before_playback_filter) - len(audited)
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
        'Still-image-only, unavailable, embed-disabled, unchecked, and source-site-only feeds are excluded from the user-facing global list. '
        'Only verified in-app playable video feeds contribute to the source verification table.'
    )
    meta['playabilityAuditMode'] = 'full' if len(audited_selected) >= len(items) else 'rotating'
    meta['playabilityAuditedThisRun'] = len(audited_selected)
    meta['playabilityRetainedWithoutAuditThisRun'] = len(preserved_items)
    meta['stillImageOnlyRemovedThisRun'] = still_image_only_removed
    meta['appPlaybackRemovedThisRun'] = app_playback_removed
    meta['oldestCheckedAt'] = min((str(item.get('lastCheckedAt') or '') for item in audited if item.get('lastCheckedAt')), default=None)
    meta['uncheckedCount'] = sum(1 for item in audited if item.get('playbackStatus') == 'unchecked')
    meta['playbackStatusCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in audited))
    meta['sourceOnlyCount'] = sum(1 for item in audited if item.get('sourceOnly'))
    meta['verifiedRate'] = 1 if audited else 0
    meta['sourceTypeHealth'] = world.world_tour_source_type_health(audited)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'items': len(audited),
        'auditedThisRun': len(audited_selected),
        'status': meta['playbackStatusCounts'],
        'sourceOnly': meta['sourceOnlyCount'],
        'appPlaybackRemoved': app_playback_removed,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--max-items', type=int, default=0, help='Audit only the stalest N retained items. 0 means full audit.')
    args = parser.parse_args(argv)
    result = run(args.input, args.workers, args.max_items)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
