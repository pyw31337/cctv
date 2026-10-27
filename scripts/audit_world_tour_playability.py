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
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'data' / 'world_tour_cams.json'
DEFAULT_HISTORY_PATH = ROOT / 'data' / 'world_tour_playability_history.json'
DEFAULT_RETIRED_PATH = ROOT / 'data' / 'world_tour_retired_streams.json'
FAILURE_WINDOW_HOURS = 96
FAILURE_THRESHOLD = 5
PERMANENT_REVIEW_DAYS = 90
TRANSIENT_REVIEW_DAYS = 1
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


def load_history(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {"cameras": {}}
    except (OSError, json.JSONDecodeError):
        return {"cameras": {}}


def in_app_playable(item: dict) -> bool:
    return bool(
        item.get('playbackStatus') == 'verified'
        and not item.get('sourceOnly')
        and (item.get('videoId') or item.get('embedUrl') or item.get('playUrl'))
    )


def recent_attempts(history: dict, camera_id: str, now: dt.datetime) -> list[dict]:
    entry = (history.get('cameras') or {}).get(camera_id, {}) if isinstance(history, dict) else {}
    attempts = entry.get('attempts', []) if isinstance(entry, dict) else []
    cutoff = now - dt.timedelta(hours=FAILURE_WINDOW_HOURS)
    return [item for item in attempts if isinstance(item, dict) and parse_date(item.get('at')) >= cutoff]


def should_prune(history: dict, item: dict, now: dt.datetime) -> bool:
    attempts = recent_attempts(history, str(item.get('id') or ''), now)
    return len(attempts) >= FAILURE_THRESHOLD and not any(bool(attempt.get('in_app')) for attempt in attempts)


def failure_policy(item: dict, history: dict, now: dt.datetime) -> dict:
    """Classify a five-failure result without mistaking a source policy for an outage."""
    attempts = recent_attempts(history, str(item.get('id') or ''), now)
    reasons = [str(attempt.get('reason') or '') for attempt in attempts]
    reason = next((value for value in reversed(reasons) if value), 'unclassified')
    permanent_markers = (
        'forbidden', 'owner_disabled', 'detail_page_does_not_expose',
        'verified_original_source_page_only', 'no_public_youtube',
        'invalid_or_unstable_embed', 'not_embeddable',
    )
    transient_markers = ('timeout', 'http_error', 'httpstatus', 'http_status', 'certificate', 'direct_stream_probe_failed', 'embed_url_probe_failed', '404', '503', '429')
    normalized = reason.lower().replace('-', '_')
    if any(marker in normalized for marker in permanent_markers):
        classification, days, action = 'provider_policy', PERMANENT_REVIEW_DAYS, 'recheck_provider_policy'
    elif any(marker in normalized for marker in transient_markers):
        classification, days, action = 'transient_delivery', TRANSIENT_REVIEW_DAYS, 'retry_and_refresh_source'
    else:
        classification, days, action = 'needs_investigation', 7, 'inspect_source_mapping'
    return {
        'classification': classification,
        'root_cause': reason,
        'recommended_action': action,
        'review_interval_days': days,
        'next_review_at': (now + dt.timedelta(days=days)).isoformat(),
        'consecutive_failures': len(attempts),
    }


def load_retired(path: Path) -> dict:
    payload = load_history(path)
    payload.setdefault('items', {})
    return payload


def retire_item(retired: dict, item: dict, history: dict, now: dt.datetime) -> None:
    camera_id = str(item.get('id') or '')
    if not camera_id:
        return
    retired.setdefault('items', {})[camera_id] = {
        'id': camera_id,
        'title': item.get('title') or camera_id,
        'source_type': item.get('sourceType') or 'unknown',
        'removed_at': now.isoformat(),
        'item': item,
        **failure_policy(item, history, now),
    }


def backfill_retired(retired: dict, history: dict, active_ids: set[str], now: dt.datetime) -> int:
    """Preserve policy review for streams removed before the registry existed."""
    records = retired.setdefault('items', {})
    added = 0
    for camera_id, entry in (history.get('cameras') or {}).items():
        if camera_id in active_ids or camera_id in records:
            continue
        attempts = recent_attempts(history, str(camera_id), now)
        if len(attempts) < FAILURE_THRESHOLD or any(attempt.get('in_app') for attempt in attempts):
            continue
        item = {
            'id': camera_id,
            'title': entry.get('last_title') or camera_id,
            'playbackStatus': attempts[-1].get('status') or 'source-only',
            'sourceOnly': True,
            'sourceOnlyReason': attempts[-1].get('reason') or 'unclassified',
        }
        retire_item(retired, item, history, now)
        records[camera_id].pop('item', None)
        added += 1
    return added


def review_retired(retired: dict, history: dict, now: dt.datetime, max_workers: int) -> tuple[list[dict], dict[str, int]]:
    """Re-admit only a quarantined stream that has passed an independent recheck."""
    records = retired.get('items') if isinstance(retired, dict) else {}
    due = [record for record in records.values() if isinstance(record, dict) and parse_date(record.get('next_review_at')) <= now]
    due = due[:max(1, min(40, max_workers * 4))]
    candidates = [dict(record.get('item') or {}) for record in due if record.get('item')]
    reviewed = []
    if candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            reviewed = [item for item in executor.map(audit_item, candidates) if item]
    recovered = []
    counts = Counter()
    for item in reviewed:
        camera_id = str(item.get('id') or '')
        record_attempt(history, item, now)
        record = records.get(camera_id)
        if not record:
            continue
        if in_app_playable(item):
            recovered.append(item)
            records.pop(camera_id, None)
            counts['recovered'] += 1
            continue
        policy = failure_policy(item, history, now)
        # A repeatedly transient provider is not hammered forever; keep its
        # reason visible and back off to weekly review after the first retry.
        if policy['classification'] == 'transient_delivery' and record.get('transient_rechecks', 0) >= 1:
            policy['review_interval_days'] = 7
            policy['next_review_at'] = (now + dt.timedelta(days=7)).isoformat()
        record.update({'item': item, **policy})
        if policy['classification'] == 'transient_delivery':
            record['transient_rechecks'] = int(record.get('transient_rechecks', 0)) + 1
        counts[policy['classification']] += 1
    return recovered, dict(counts)


def record_attempt(history: dict, item: dict, now: dt.datetime) -> None:
    camera_id = str(item.get('id') or '')
    if not camera_id:
        return
    cameras = history.setdefault('cameras', {})
    entry = cameras.setdefault(camera_id, {"attempts": []})
    attempts = recent_attempts(history, camera_id, now)
    attempts.append({
        'at': now.isoformat(),
        'in_app': in_app_playable(item),
        'status': item.get('playbackStatus') or 'unknown',
        'reason': item.get('sourceOnlyReason') or item.get('directProbeStatus') or item.get('embedProbeStatus') or '',
    })
    entry['attempts'] = attempts[-FAILURE_THRESHOLD:]
    entry['last_title'] = item.get('title') or camera_id


def audit_priority(item: dict, history: dict | None = None) -> tuple:
    """Recheck incomplete failures before rotating to lower-risk entries."""
    status = str(item.get('playbackStatus') or 'unchecked').lower()
    source_only = bool(item.get('sourceOnly'))
    source_type = str(item.get('sourceType') or '')
    risky_source = source_type in {'livebeaches', 'hdontap', 'worldcam', 'youtube-search', 'webcamera24', 'spacecam'}
    status_rank = {
        'unchecked': 0,
        'unavailable': 1,
        'embed_disabled': 1,
        'source-only': 2,
        'verified': 3,
    }.get(status, 1)
    attempts = recent_attempts(history or {}, str(item.get('id') or ''), dt.datetime.now(dt.timezone.utc))
    # Recheck an observed failure until it reaches a defensible five-attempt
    # decision. This avoids keeping source-only entries forever just because
    # a rotating audit visits each one too rarely.
    incomplete_failure = bool(attempts) and len(attempts) < FAILURE_THRESHOLD and not any(a.get('in_app') for a in attempts)
    return (
        0 if incomplete_failure else 1,
        -len(attempts) if incomplete_failure else 0,
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
        normalized['sourceOnlyReason'] = (
            'viewsurf_embed_forbidden_or_not_embeddable'
            if world.is_forbidden_embed_url(blocked_embed)
            else 'invalid_or_unstable_embed_url'
        )
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

    # A URL being present is not evidence that a stream is playable. Providers
    # commonly leave expired MP4 URLs in their feeds and return 404/410 or an
    # HTML error page. Probe a small byte range so the catalog only promotes a
    # URL that actually responds as video.
    try:
        request = urllib.request.Request(
            value,
            headers={
                **world.HEADERS,
                'Accept': 'video/*,application/octet-stream,*/*',
                'Range': 'bytes=0-4095',
            },
        )
        try:
            try:
                response = urllib.request.urlopen(request, timeout=12)
            except urllib.error.URLError as error:
                if 'CERTIFICATE_VERIFY_FAILED' not in str(error):
                    raise
                response = urllib.request.urlopen(
                    request,
                    timeout=12,
                    context=world.UNVERIFIED_SSL_CONTEXT,
                )
            with response:
                status = int(response.getcode() or 0)
                content_type = (response.headers.get('Content-Type') or '').lower()
                body = response.read(4096)
        except urllib.error.HTTPError as error:
            return False, f'http_status_{error.code}'

        if not 200 <= status < 300:
            return False, f'http_status_{status}'
        if not body:
            return False, 'empty_video_response'

        path = value.lower().split('?', 1)[0]
        video_type = content_type.startswith('video/') or content_type in {
            'application/octet-stream',
            'binary/octet-stream',
        }
        mp4_signature = body[:16].find(b'ftyp') >= 0
        if path.endswith('.mp4') and not video_type and not mp4_signature:
            return False, f'invalid_video_content_type:{content_type or "missing"}'
        return True, f'video_probe_ok_{status}'
    except urllib.error.URLError as error:
        return False, f'url_error:{error.reason}'
    except Exception as error:
        return False, f'{type(error).__name__}: {error}'


def probe_embed_url(url: str) -> tuple[bool, str]:
    value = str(url or '').strip()
    if not value:
        return False, 'missing_url'
    try:
        req = urllib.request.Request(value, headers=world.HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.getcode()
        except urllib.error.URLError as error:
            if 'CERTIFICATE_VERIFY_FAILED' not in str(error):
                raise
            with urllib.request.urlopen(req, timeout=10, context=world.UNVERIFIED_SSL_CONTEXT) as response:
                status = response.getcode()
        
        if 200 <= status < 400:
            return True, f'http_{status}_ok'
        return False, f'http_status_{status}'
    except urllib.error.HTTPError as error:
        return False, f'HTTPError_{error.code}'
    except Exception as error:
        return False, f'{type(error).__name__}: {error}'


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
            ok, reason = probe_embed_url(item.get('embedUrl'))
            item['embedProbeStatus'] = reason
            item['playbackStatus'] = 'verified' if ok else 'source-only'
            item['sourceOnly'] = not ok
            if ok:
                item['directPlaybackStatus'] = item.get('directPlaybackStatus') or 'trusted_provider_embed'
                item.pop('sourceOnlyReason', None)
            else:
                item['directPlaybackStatus'] = 'source_site_only'
                item['sourceOnlyReason'] = 'embed_url_probe_failed'
        elif item.get('sourceUrl'):
            item['playbackStatus'] = 'source-only'
            item['sourceOnly'] = True
        else:
            item['playbackStatus'] = 'unchecked'
            item['sourceOnly'] = True
    return world.enrich_item_quality(item)


def select_audit_items(items: list[dict], history: dict, max_items: int | None = None) -> tuple[list[dict], set[str]]:
    if not max_items or max_items <= 0 or max_items >= len(items):
        selected = list(items)
    else:
        selected = sorted(items, key=lambda item: audit_priority(item, history))[:max_items]
    selected_ids = {str(item.get('id') or '') for item in selected}
    return selected, selected_ids


def run(path: Path, history_path: Path = DEFAULT_HISTORY_PATH, retired_path: Path = DEFAULT_RETIRED_PATH, max_workers: int = 10, max_items: int | None = None) -> dict:
    payload = json.loads(path.read_text(encoding='utf-8'))
    items = payload.get('items', [])
    history = load_history(history_path)
    retired = load_retired(retired_path)
    now = dt.datetime.now(dt.timezone.utc)
    backfilled_retired = backfill_retired(retired, history, {str(item.get('id') or '') for item in items}, now)
    retired_ids = set((retired.get('items') or {}).keys())
    for item in items:
        record = (retired.get('items') or {}).get(str(item.get('id') or ''))
        if record and not record.get('item'):
            # A source collector rediscovered a historical record. Keep its
            # candidate for the scheduled policy review, but do not show it.
            record['item'] = item
    # A daily source refresh can rediscover a quarantined listing. It stays
    # hidden until this audit independently proves direct in-app playback.
    items = [item for item in items if str(item.get('id') or '') not in retired_ids]
    recovered_items, retirement_review = review_retired(retired, history, now, max_workers)
    items.extend(recovered_items)
    selected_items, selected_ids = select_audit_items(items, history, max_items)
    preserved_items = [item for item in items if str(item.get('id') or '') not in selected_ids]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        audited_selected = [item for item in executor.map(audit_item, selected_items) if item]
    for item in audited_selected:
        record_attempt(history, item, now)
    prune_ids = {str(item.get('id') or '') for item in audited_selected if should_prune(history, item, now)}
    for item in audited_selected:
        if str(item.get('id') or '') in prune_ids:
            retire_item(retired, item, history, now)
    audited = [item for item in audited_selected + preserved_items if not world.is_refused_original_only_item(item) and str(item.get('id') or '') not in prune_ids]
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
    meta['sourceCounts'] = dict(Counter(item.get('sourceType') or 'unknown' for item in audited))
    meta['regionCounts'] = dict(Counter(item.get('region') or 'Other' for item in audited))
    meta['playbackCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in audited))
    meta['qualityTiers'] = dict(Counter(item.get('qualityTier') or 'unknown' for item in audited))
    meta['directPlaybackStatusCounts'] = dict(Counter(
        item.get('directPlaybackStatus') or ('in_app_playable' if world.is_in_app_video_item(item) else 'source_site_only')
        for item in audited
    ))
    meta['sourceOnlyReasons'] = dict(Counter(
        item.get('sourceOnlyReason') for item in audited if item.get('sourceOnlyReason')
    ))
    meta['lastPlayabilityAuditAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    meta['playabilityAuditPolicy'] = (
        'Snapshot-only feeds are excluded; unavailable/embed-disabled/source-only feeds are retained but not treated as in-app playable. '
        'Known refused original-only providers are removed from the user-facing list. '
        'When max-items is used, stale and high-risk source items are rotated first so every retained item eventually receives a fresh check.'
    )
    meta['playabilityAuditMode'] = 'full' if len(audited_selected) >= len(items) else 'rotating'
    meta['playabilityAuditedThisRun'] = len(audited_selected)
    meta['playabilityRetainedWithoutAuditThisRun'] = len(preserved_items)
    meta['oldestCheckedAt'] = min((str(item.get('lastCheckedAt') or '') for item in audited if item.get('lastCheckedAt')), default=None)
    meta['uncheckedCount'] = sum(1 for item in audited if item.get('playbackStatus') == 'unchecked')
    meta['playbackStatusCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in audited))
    meta['sourceOnlyCount'] = sum(1 for item in audited if item.get('sourceOnly'))
    meta['fiveAttemptRemovalPolicy'] = f'Remove only after {FAILURE_THRESHOLD} in-app playback failures within {FAILURE_WINDOW_HOURS} hours; one success resets eligibility.'
    meta['removedAfterFiveFailedChecksThisRun'] = len(prune_ids)
    retired_items = list((retired.get('items') or {}).values())
    meta['retiredStreamPolicy'] = f'provider_policy items recheck every {PERMANENT_REVIEW_DAYS} days; transient delivery failures retry quickly then back off to weekly review.'
    meta['retiredStreamCounts'] = dict(Counter(str(item.get('classification') or 'unknown') for item in retired_items))
    meta['retiredReviewedThisRun'] = retirement_review
    meta['retiredRecoveredThisRun'] = len(recovered_items)
    meta['retiredBackfilledThisRun'] = backfilled_retired
    meta['sourceTypeHealth'] = {
        source: {
            'total': total,
            'verified': verified,
            'sourceOnly': source_only,
            'unchecked': unchecked,
            'unavailable': unavailable,
            'embedDisabled': embed_disabled,
            'directHls': direct_hls,
            'trustedEmbed': trusted_embed,
            'externalOnly': source_only + unavailable + embed_disabled,
            'verifiedRate': round(verified / total, 4) if total else 0,
        }
        for source, total, verified, source_only, unchecked, unavailable, embed_disabled, direct_hls, trusted_embed in (
            (
                source,
                len(source_items),
                sum(1 for item in source_items if item.get('playbackStatus') == 'verified' and not item.get('sourceOnly')),
                sum(1 for item in source_items if item.get('sourceOnly')),
                sum(1 for item in source_items if item.get('playbackStatus') == 'unchecked'),
                sum(1 for item in source_items if item.get('playbackStatus') == 'unavailable'),
                sum(1 for item in source_items if item.get('playbackStatus') == 'embed_disabled'),
                sum(1 for item in source_items if item.get('playUrl') or item.get('directPlaybackStatus') in {'direct_hls', 'proxied_hls'}),
                sum(1 for item in source_items if item.get('embedUrl') or item.get('directPlaybackStatus') in {'trusted_provider_embed', 'in_app_playable'}),
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
    history['schema'] = 'world-tour-playability-history-v1'
    history['updated_at'] = now.isoformat()
    history['window_hours'] = FAILURE_WINDOW_HOURS
    history['failure_threshold'] = FAILURE_THRESHOLD
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    retired['schema'] = 'world-tour-retired-streams-v1'
    retired['updated_at'] = now.isoformat()
    retired['failure_threshold'] = FAILURE_THRESHOLD
    retired['permanent_review_days'] = PERMANENT_REVIEW_DAYS
    retired_path.write_text(json.dumps(retired, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'items': len(audited),
        'auditedThisRun': len(audited_selected),
        'status': meta['playbackStatusCounts'],
        'sourceOnly': meta['sourceOnlyCount'],
        'removedAfterFiveFailedChecks': len(prune_ids),
        'retiredRecovered': len(recovered_items),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--history', type=Path, default=DEFAULT_HISTORY_PATH)
    parser.add_argument('--retired', type=Path, default=DEFAULT_RETIRED_PATH)
    parser.add_argument('--workers', type=int, default=10)
    parser.add_argument('--max-items', type=int, default=0, help='Audit only the stalest N retained items. 0 means full audit.')
    args = parser.parse_args(argv)
    result = run(args.input, args.history, args.retired, args.workers, args.max_items)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
