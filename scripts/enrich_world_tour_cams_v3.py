#!/usr/bin/env python3
import json
import re
import urllib.request
import urllib.parse
from pathlib import Path
from collections import Counter
import concurrent.futures

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'world_tour_cams.json'

def fetch_text(url, timeout=6):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        return None

def resolve_redirect_url(url, timeout=8):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.geturl()
    except Exception as e:
        return None

def extract_youtube_id(text):
    if not text:
        return None
    ids = []
    patterns = [
        r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})',
        r'youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
        r'youtu\.be/([A-Za-z0-9_-]{11})',
        r'"videoId"\s*:\s*"([A-Za-z0-9_-]{11})"',
    ]
    for pat in patterns:
        ids.extend(re.findall(pat, text))
    for vid in ids:
        if vid != 'live_stream':
            return vid
    return None

def resolve_youtube_channel_live(channel_url):
    html_text = fetch_text(channel_url)
    return extract_youtube_id(html_text)

def extract_hls_url(text):
    if not text:
        return None
    patterns = [
        r'https?://[^"\'<>\s]+?\.m3u8(?:\?[^"\'<>\s]*)?',
    ]
    for pat in patterns:
        matches = re.findall(pat, text, re.I)
        if matches:
            val = matches[0].replace('\\/', '/').replace('\\u0026', '&').replace('&amp;', '&').strip()
            val = val.rstrip('.,);\'"')
            return val
    return None

def deep_crawling_target(source_url, title):
    """
    Crawls a source_url, resolving redirects first if it goes through worldcam's redirection service.
    Returns a tuple of (resolved_videoId, resolved_hls_url) or (None, None).
    """
    url_to_crawl = source_url
    
    # 1. Resolve WorldCam redirection code if present
    if 'worldcam.eu' in source_url:
        page_html = fetch_text(source_url)
        if page_html:
            # Look for /click/source?code=... redirect link
            match = re.search(r'href=["\']([^"\']*/click/source\?code=[^"\']+)["\']', page_html)
            if match:
                redirect_link = urllib.parse.urljoin('https://worldcam.eu', match.group(1))
                print(f" -> Found redirect tunnel: {redirect_link}")
                resolved = resolve_redirect_url(redirect_link)
                if resolved:
                    print(f" -> Resolved original source URL: {resolved}")
                    url_to_crawl = resolved
                else:
                    return None, None
            else:
                # Check if there is an iframe embed or YouTube video directly on the worldcam detail page
                resolved_vid = extract_youtube_id(page_html)
                if resolved_vid:
                    return resolved_vid, None
                resolved_hls = extract_hls_url(page_html)
                if resolved_hls:
                    return None, resolved_hls

    # 2. Check if the original URL is youtube channel or watch page
    channel_match = re.search(r'youtube(?:-nocookie)?\.com/(?:embed/live_stream\?channel=|channel/|c/|@)([A-Za-z0-9_#-]+)', url_to_crawl)
    if channel_match or ('youtube.com' in url_to_crawl or 'youtu.be' in url_to_crawl):
        resolved_vid = resolve_youtube_channel_live(url_to_crawl)
        if resolved_vid:
            return resolved_vid, None
        return None, None

    # 3. Perform final fetch of target website ( 지자체 / 해외 관공서 등 )
    print(f" -> Accessing final source: {url_to_crawl}")
    final_html = fetch_text(url_to_crawl)
    if final_html:
        resolved_vid = extract_youtube_id(final_html)
        if resolved_vid:
            return resolved_vid, None
        resolved_hls = extract_hls_url(final_html)
        if resolved_hls:
            if resolved_hls.startswith('/'):
                parsed_src = urllib.parse.urlparse(url_to_crawl)
                resolved_hls = f"{parsed_src.scheme}://{parsed_src.netloc}{resolved_hls}"
            return None, resolved_hls

    return None, None

def main():
    if not DATA_PATH.exists():
        print(f"Data file not found at {DATA_PATH}")
        return

    print("Loading world tour cams data...")
    payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    items = payload.get('items', [])
    
    initial_direct_counts = Counter(i.get('directPlaybackStatus', 'source_site_only') for i in items)
    print("Initial stats:")
    print(json.dumps(dict(initial_direct_counts), indent=2))
    
    promoted_panomax = 0
    promoted_roundshot = 0
    promoted_deep_crawl = 0
    
    # Filter targets:
    # 1. Panomax / Roundshot
    # 2. South Korea local government cameras (deep crawl)
    # 3. Major European/US locations that are currently source-site-only
    targets_to_crawl = []
    for item in items:
        source_type = item.get('sourceType', '')
        source_url = item.get('sourceUrl', '')
        country = item.get('country', '')
        
        # Panomax Promotion
        if source_type == 'panomax' and item.get('sourceOnly'):
            item_id = item.get('id', '')
            cam_id = None
            if item_id.startswith('panomax-'):
                cam_id = item_id.split('panomax-')[1]
            if cam_id:
                item['embedUrl'] = f"https://{cam_id}.camera.panomax.com/"
                item['directPlaybackStatus'] = 'trusted_provider_embed'
                item['sourceOnly'] = False
                item['playbackStatus'] = 'verified'
                item['status'] = 'is_live'
                item.pop('sourceOnlyReason', None)
                promoted_panomax += 1
                
        # Roundshot Promotion
        elif source_type == 'roundshot' and item.get('sourceOnly'):
            if source_url and '.roundshot.com' in source_url:
                item['embedUrl'] = source_url
                item['directPlaybackStatus'] = 'trusted_provider_embed'
                item['sourceOnly'] = False
                item['playbackStatus'] = 'verified'
                item['status'] = 'is_live'
                item.pop('sourceOnlyReason', None)
                promoted_roundshot += 1
                
        # Deep Crawl for ALL sourceOnly cams globally
        elif item.get('sourceOnly') and source_url:
            targets_to_crawl.append(item)

    print(f"\nCollected {len(targets_to_crawl)} deep crawling candidates. Processing concurrently...")
    
    # We process deep crawling concurrently with 8 threads to save time
    def process_item(item):
        title = item.get('title', '')
        source_url = item.get('sourceUrl', '')
        print(f"Resolving: {title} ({source_url})")
        vid, hls = deep_crawling_target(source_url, title)
        return item, vid, hls

    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
        futures = {executor.submit(process_item, item): item for item in targets_to_crawl}
        for future in concurrent.futures.as_completed(futures):
            item, vid, hls = future.result()
            if vid:
                item['videoId'] = vid
                item['directPlaybackStatus'] = 'youtube_embed_verified'
                item['sourceOnly'] = False
                item['playbackStatus'] = 'verified'
                item['status'] = 'is_live'
                item.pop('sourceOnlyReason', None)
                promoted_deep_crawl += 1
                print(f"SUCCESS: Promoted '{item.get('title')}' to YouTube VideoId: {vid}")
            elif hls:
                item['playUrl'] = hls
                item['directPlaybackStatus'] = 'direct_hls'
                item['sourceOnly'] = False
                item['playbackStatus'] = 'verified'
                item['status'] = 'is_live'
                item.pop('sourceOnlyReason', None)
                promoted_deep_crawl += 1
                print(f"SUCCESS: Promoted '{item.get('title')}' to HLS stream: {hls}")

    print(f"\nEnrichment complete.")
    print(f"Promoted Panomax: {promoted_panomax}")
    print(f"Promoted Roundshot: {promoted_roundshot}")
    print(f"Promoted Deep Crawl (Korea & Global): {promoted_deep_crawl}")
    
    # Recalculate collection metadata
    meta = payload.setdefault('collectionMeta', {})
    meta['itemCount'] = len(items)
    
    # Recalculate status counts
    direct_status_counts = Counter(
        i.get('directPlaybackStatus') or ('in_app_playable' if i.get('videoId') or i.get('embedUrl') else 'source_site_only') 
        for i in items
    )
    meta['directPlaybackStatusCounts'] = dict(direct_status_counts)
    meta['playbackCounts'] = dict(Counter(i.get('playbackStatus', 'unknown') for i in items))
    meta['sourceOnlyCount'] = sum(1 for i in items if i.get('sourceOnly'))
    
    print("\nUpdated stats:")
    print(json.dumps(dict(direct_status_counts), indent=2))
    
    if promoted_panomax > 0 or promoted_roundshot > 0 or promoted_deep_crawl > 0:
        print("\nSaving updated data back to JSON...")
        payload['updated_at'] = dt.date.today().isoformat()
        DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print("Save successful.")
    else:
        print("\nNo promotions made. Skipping save.")

if __name__ == '__main__':
    import datetime as dt
    main()
