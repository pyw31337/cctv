#!/usr/bin/env python3
"""Expand the world-tour directory with verified source-site-only webcams.

This intentionally works in small batches: collectors may discover thousands of
source pages, but only pages whose original URL can be fetched cleanly are
merged into the user-facing JSON, capped by --batch-size.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / 'data' / 'world_tour_cams.json'
sys.path.insert(0, str(ROOT / 'scripts'))
import build_world_tour_cams as world  # noqa: E402


SOURCE_COLLECTORS = {
    'worldcamlive': lambda: world.collect_worldcamlive(160),
    'panoramask': lambda: world.collect_panoramask(180),
    'airportwebcams': lambda: world.collect_airportwebcams(180),
    'webcamhopper': lambda: world.collect_webcamhopper(120),
    'livecamcroatia': lambda: world.collect_livecamcroatia(80),
    'viewsurf': lambda: world.collect_viewsurf(160),
    'worldcam': lambda: world.collect_worldcam(180),
    'baltic': lambda: world.collect_baltic(180),
    'skyline': lambda: world.collect_skyline(120),
}

BLOCKED_SOURCE_PAGE_RE = re.compile(
    r'(403 Forbidden|404 Not Found|Access Denied|Service Unavailable|This page is unavailable|'
    r'blocked due to|connection refused|refused to connect)',
    re.I,
)


def item_key(item: dict) -> str:
    source_url = str(item.get('sourceUrl') or '').strip().lower().rstrip('/')
    if source_url:
        return f'url:{source_url}'
    return 'id:' + str(item.get('id') or '').strip().lower()


def identity_key(item: dict) -> str:
    return '|'.join([
        re.sub(r'[^a-z0-9가-힣]+', '', str(item.get('title') or '').lower()),
        str(item.get('city') or '').lower(),
        str(item.get('country') or '').lower(),
    ])


def existing_keys(items: list[dict]) -> tuple[set[str], set[str]]:
    return {item_key(item) for item in items}, {identity_key(item) for item in items}


def normalize_candidate(item: dict) -> dict | None:
    if not item or not item.get('sourceUrl'):
        return None
    if world.is_snapshot_only_item(item) or world.is_refused_original_only_item(item):
        return None
    normalized = dict(item)
    embed_url = normalized.get('embedUrl')
    if embed_url and not world.is_valid_embed_url(embed_url):
        normalized['blockedEmbedUrl'] = normalized.pop('embedUrl')
        normalized['sourceOnly'] = True
        normalized['directPlaybackStatus'] = 'source_site_only'
        normalized['playbackStatus'] = 'source-only'
        normalized['sourceOnlyReason'] = (
            'viewsurf_embed_forbidden_or_not_embeddable'
            if world.is_forbidden_embed_url(embed_url)
            else 'invalid_or_unstable_embed_url'
        )
    normalized['sourceOnly'] = True
    normalized['playbackStatus'] = 'source-only'
    normalized['directPlaybackStatus'] = 'source_site_only'
    normalized['sourceOnlyReason'] = 'verified_original_source_page_only'
    normalized['sourceExpansionBatch'] = True
    return world.enrich_item_quality(normalized)


def probe_source_page(item: dict, min_html_chars: int = 500) -> tuple[bool, str]:
    source_url = str(item.get('sourceUrl') or '').strip()
    if not source_url.startswith(('http://', 'https://')):
        return False, 'missing_or_invalid_source_url'
    parsed = urlparse(source_url)
    if not parsed.netloc:
        return False, 'missing_source_host'
    try:
        text = world.fetch_text(source_url, timeout=12, cache=True)
    except Exception as error:
        return False, f'{type(error).__name__}'
    compact = re.sub(r'\s+', ' ', text or '').strip()
    if len(compact) < min_html_chars:
        return False, 'source_page_too_short'
    if BLOCKED_SOURCE_PAGE_RE.search(compact[:5000]):
        return False, 'source_page_error_html'
    title = (world.extract_meta_content(text, 'og:title') or world.text_from_tag(text, 'title') or '').strip()
    if title and re.search(r'\b(404|403|forbidden|not found|access denied)\b', title, re.I):
        return False, 'source_page_error_title'
    return True, 'source_page_ok'


def collect_candidates(source_names: list[str], candidate_limit: int, collection_goal: int) -> tuple[list[dict], list[dict]]:
    candidates = []
    collector_health = []
    for source_name in source_names:
        collector = SOURCE_COLLECTORS[source_name]
        started = time.perf_counter()
        status = 'ok'
        error_summary = None
        print(f'collecting {source_name}...', file=sys.stderr, flush=True)
        try:
            collected = collector()
        except Exception as error:
            collected = []
            status = 'error'
            error_summary = f'{type(error).__name__}: {error}'
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        print(f'{source_name} collected {len(collected)} in {elapsed_ms}ms', file=sys.stderr, flush=True)
        collector_health.append({
            'source': source_name,
            'count': len(collected),
            'elapsedMs': elapsed_ms,
            'status': status,
            'error': error_summary,
        })
        for item in collected:
            normalized = normalize_candidate(item)
            if normalized:
                candidates.append(normalized)
        if len(candidates) >= min(candidate_limit, collection_goal):
            break
    return candidates[:candidate_limit], collector_health


def recalculate_meta(payload: dict, expansion_meta: dict) -> None:
    items = payload.get('items', [])
    meta = payload.setdefault('collectionMeta', {})
    meta['itemCount'] = len(items)
    meta['sourceCounts'] = dict(Counter(item.get('sourceType') or 'unknown' for item in items))
    meta['regionCounts'] = dict(Counter(item.get('region') or 'Other' for item in items))
    meta['playbackCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in items))
    meta['qualityTiers'] = dict(Counter(item.get('qualityTier') or 'unknown' for item in items))
    meta['directPlaybackStatusCounts'] = dict(Counter(
        item.get('directPlaybackStatus') or ('in_app_playable' if world.is_in_app_video_item(item) else 'source_site_only')
        for item in items
    ))
    meta['sourceOnlyReasons'] = dict(Counter(item.get('sourceOnlyReason') for item in items if item.get('sourceOnlyReason')))
    meta['uncheckedCount'] = sum(1 for item in items if item.get('playbackStatus') == 'unchecked')
    meta['playbackStatusCounts'] = dict(Counter(item.get('playbackStatus') or 'unknown' for item in items))
    meta['sourceOnlyCount'] = sum(1 for item in items if item.get('sourceOnly'))
    meta['lastSourceOnlyExpansionAt'] = dt.datetime.now(dt.timezone.utc).isoformat()
    meta['sourceOnlyExpansionPolicy'] = (
        'Candidates are collected broadly, then each original source page is fetched before merging. '
        'Only validated candidates are added, capped by batch size so expansion happens in 100/500 item units.'
    )
    meta['lastSourceOnlyExpansion'] = expansion_meta

    source_groups = defaultdict(list)
    for item in items:
        source_groups[item.get('sourceType') or 'unknown'].append(item)
    meta['sourceTypeHealth'] = {}
    for source, source_items in sorted(source_groups.items()):
        total = len(source_items)
        verified = sum(1 for item in source_items if item.get('playbackStatus') == 'verified' and not item.get('sourceOnly'))
        source_only = sum(1 for item in source_items if item.get('sourceOnly'))
        unchecked = sum(1 for item in source_items if item.get('playbackStatus') == 'unchecked')
        unavailable = sum(1 for item in source_items if item.get('playbackStatus') == 'unavailable')
        embed_disabled = sum(1 for item in source_items if item.get('playbackStatus') == 'embed_disabled')
        direct_hls = sum(1 for item in source_items if item.get('playUrl') or item.get('directPlaybackStatus') in {'direct_hls', 'proxied_hls'})
        trusted_embed = sum(1 for item in source_items if item.get('embedUrl') or item.get('directPlaybackStatus') in {'trusted_provider_embed', 'in_app_playable'})
        meta['sourceTypeHealth'][source] = {
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


def run(path: Path, batch_size: int, candidate_limit: int, source_names: list[str], dry_run: bool = False, collection_multiplier: int = 3) -> dict:
    payload = json.loads(path.read_text(encoding='utf-8'))
    existing_items = payload.get('items', [])
    known_urls, known_identities = existing_keys(existing_items)
    collection_goal = max(batch_size, batch_size * max(1, collection_multiplier))
    candidates, collector_health = collect_candidates(source_names, candidate_limit, collection_goal)

    fresh_candidates = []
    seen_urls = set()
    seen_identities = set()
    for candidate in candidates:
        key = item_key(candidate)
        ident = identity_key(candidate)
        if key in known_urls or key in seen_urls:
            continue
        if ident in known_identities or ident in seen_identities:
            continue
        seen_urls.add(key)
        seen_identities.add(ident)
        fresh_candidates.append(candidate)

    accepted = []
    rejected = []
    checked = 0
    today = dt.date.today().isoformat()
    for item in fresh_candidates:
        checked += 1
        if checked == 1 or checked % 25 == 0:
            print(f'probing source page {checked}/{len(fresh_candidates)} accepted={len(accepted)}', file=sys.stderr, flush=True)
        ok, reason = probe_source_page(item)
        item['sourceUrlProbeStatus'] = reason
        item['sourceUrlCheckedAt'] = today
        if ok:
            accepted.append(item)
        else:
            rejected.append({'id': item.get('id'), 'sourceType': item.get('sourceType'), 'reason': reason})
        if len(accepted) >= batch_size:
            break

    accepted.sort(key=lambda item: (
        -(int(item.get('qualityScore') or item.get('stabilityScore') or item.get('priority') or 0)),
        item.get('sourceType') or '',
        item.get('title') or '',
    ))
    expansion_meta = {
        'candidateLimit': candidate_limit,
        'collectionGoal': min(candidate_limit, collection_goal),
        'batchSize': batch_size,
        'collectorHealth': collector_health,
        'candidatesCollected': len(candidates),
        'freshCandidates': len(fresh_candidates),
        'checked': checked,
        'accepted': len(accepted),
        'rejectedDuringProbe': len(rejected),
        'acceptedBySource': dict(Counter(item.get('sourceType') or 'unknown' for item in accepted)),
        'rejectedReasonSample': dict(Counter(item.get('reason') for item in rejected).most_common(10)),
        'dryRun': dry_run,
    }

    if not dry_run and accepted:
        payload['items'] = existing_items + accepted
        payload['items'].sort(key=lambda item: (
            0 if world.is_in_app_video_item(item) and not item.get('sourceOnly') else 1,
            -int(item.get('qualityScore') or item.get('stabilityScore') or item.get('priority') or 0),
            item.get('region') or '',
            item.get('title') or '',
        ))
        payload['updated_at'] = today
        recalculate_meta(payload, expansion_meta)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return expansion_meta


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_PATH)
    parser.add_argument('--batch-size', type=int, default=100)
    parser.add_argument('--candidate-limit', type=int, default=2000)
    parser.add_argument('--collection-multiplier', type=int, default=3)
    parser.add_argument('--sources', default=','.join(SOURCE_COLLECTORS.keys()))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    source_names = [name.strip() for name in args.sources.split(',') if name.strip()]
    unknown = [name for name in source_names if name not in SOURCE_COLLECTORS]
    if unknown:
        raise SystemExit(f'unknown source collectors: {", ".join(unknown)}')
    result = run(args.input, args.batch_size, args.candidate_limit, source_names, args.dry_run, args.collection_multiplier)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
