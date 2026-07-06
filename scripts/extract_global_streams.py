#!/usr/bin/env python3
"""
Global Webcam Stream URL Extractor
출처별 2-3뎁스 스트림 URL 자동 추출기

Usage: python3 scripts/extract_global_streams.py
"""

import re
import ssl
import json
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

CTX = ssl._create_unverified_context()
UA  = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

# ─────────────────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────────────────

def fetch(url: str, referer: str = None, timeout: int = 10) -> str:
    headers = {'User-Agent': UA, 'Accept': '*/*'}
    if referer:
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read().decode('utf-8', errors='ignore')


def probe_url(url: str, referer: str = None) -> int:
    """Return HTTP status code, 0 on error."""
    try:
        headers = {'User-Agent': UA, 'Range': 'bytes=0-1'}
        if referer:
            headers['Referer'] = referer
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6, context=CTX) as r:
            return r.status
    except Exception:
        return 0


def first_m3u8(text: str) -> str | None:
    m = re.search(r'https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*', text, re.IGNORECASE)
    return m.group(0).replace('\\/', '/') if m else None


# ─────────────────────────────────────────────────────────────────────────
# Per-provider extractors
# ─────────────────────────────────────────────────────────────────────────

class FeratelExtractor:
    """
    Depth-1: feratel.com page  → iframe src webtvfc.feratel.com/webtv/?cam=ID
    Depth-2: webtvfc.feratel.com page → stsfc001.feratel.com/streams/latest/1/{ID}.mp4
    """
    IFRAME_RE = re.compile(
        r'(?:webtvfc|webtv)\.feratel\.com/webtv/[^"\']*[?&]cam=(\d+)',
        re.IGNORECASE
    )
    MP4_URL = "https://stsfc001.feratel.com/streams/latest/1/{cam_id}.mp4?dcsdesign=WTP_feratel.com"

    def extract(self, cam: dict) -> dict | None:
        source_url = cam.get('sourceUrl', '')
        # Depth-1: fetch source page, extract iframe cam IDs
        try:
            html = fetch(source_url, referer='https://www.feratel.com/')
            cam_ids = self.IFRAME_RE.findall(html)
        except Exception as e:
            log.warning(f"Feratel depth-1 failed for {source_url}: {e}")
            return None

        if not cam_ids:
            # Try embedded webtv iframe directly
            iframe_m = re.search(r'((?:webtvfc|webtv)\.feratel\.com/webtv/[^"\'<\s]+)', html)
            if iframe_m:
                iframe_url = 'https://' + iframe_m.group(1).lstrip('/')
                try:
                    iframe_html = fetch(iframe_url, referer=source_url)
                    cam_ids = self.IFRAME_RE.findall(iframe_html)
                except Exception:
                    pass

        if not cam_ids:
            return None

        # Take first cam_id and build MP4 URL
        cam_id = cam_ids[0]
        mp4_url = self.MP4_URL.format(cam_id=cam_id)
        
        # Depth-3: probe MP4 URL
        status = probe_url(mp4_url, referer='https://webtvfc.feratel.com/')
        if status in (200, 206):
            return {'playUrl': mp4_url, 'playType': 'mp4', 'directPlaybackStatus': 'direct_mp4', 'feratelCamId': cam_id}
        
        log.warning(f"Feratel MP4 probe failed (status={status}) for {mp4_url}")
        return None


class WhatUpCamExtractor:
    """
    Depth-1: whatsupcams.com page → iframe services.whatsupcams.com/wgt/{slug}
    Depth-2: widget page → stream slug
    Depth-3: services.whatsupcams.com/streams/{slug}?jsonp=true → HLS URL
    """
    WIDGET_RE = re.compile(r'services\.whatsupcams\.com/wgt/([a-zA-Z0-9_-]+)', re.IGNORECASE)
    STREAM_API = "https://services.whatsupcams.com/streams/{slug}?jsonp=true"
    HLS_RE = re.compile(r'"url"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"')

    def extract(self, cam: dict) -> dict | None:
        source_url = cam.get('sourceUrl', '')
        try:
            html = fetch(source_url, referer='https://www.whatsupcams.com/')
        except Exception as e:
            log.warning(f"WhatUpCam depth-1 failed for {source_url}: {e}")
            return None

        slugs = self.WIDGET_RE.findall(html)
        if not slugs:
            return None

        slug = slugs[0]
        api_url = self.STREAM_API.format(slug=slug)

        try:
            raw = fetch(api_url, referer='https://services.whatsupcams.com/')
        except Exception as e:
            log.warning(f"WhatUpCam stream API failed for {slug}: {e}")
            return None

        m = self.HLS_RE.search(raw)
        if m:
            hls_url = m.group(1)
            return {'playUrl': hls_url, 'playType': 'm3u8', 'directPlaybackStatus': 'direct_hls', 'wucSlug': slug}

        return None


class CamscapeExtractor:
    """
    Depth-1: camscape.com page → iframe weather-webcam.eu/cams/...
    Depth-2: weather-webcam.eu page → rtsp.me HLS m3u8
    Note: rtsp.me HLS URLs may rotate. If they 404, regeneration requires JS.
    """
    IFRAME_RE = re.compile(r'https?://weather-webcam\.eu/cams/[^\s"\'<>]+', re.IGNORECASE)
    
    def extract(self, cam: dict) -> dict | None:
        source_url = cam.get('sourceUrl', '')
        try:
            html = fetch(source_url, referer='https://www.camscape.com/')
        except Exception as e:
            log.warning(f"Camscape depth-1 failed for {source_url}: {e}")
            return None

        iframes = self.IFRAME_RE.findall(html)
        if not iframes:
            return None

        iframe_url = iframes[0]
        try:
            iframe_html = fetch(iframe_url, referer=source_url)
        except Exception as e:
            log.warning(f"Camscape depth-2 failed for {iframe_url}: {e}")
            return None

        m3u8_url = first_m3u8(iframe_html)
        if m3u8_url:
            # Probe it
            status = probe_url(m3u8_url)
            if status in (200, 206):
                return {'playUrl': m3u8_url, 'playType': 'm3u8', 'directPlaybackStatus': 'direct_hls'}
        
        return None


class SkylineWebcamsExtractor:
    """
    Depth-1: skylinewebcams.com page → token in page HTML
    Token is embedded directly as: hd-auth.skylinewebcams.com/live.m3u8?a=TOKEN
    Token appears to be session-scoped (changes on page reload).
    We do NOT cache the token; we extract fresh each time via server proxy.
    """
    TOKEN_RE = re.compile(
        r'hd-auth\.skylinewebcams\.com/live\.m3u8\?a=([a-zA-Z0-9]+)',
        re.IGNORECASE
    )
    
    def extract(self, cam: dict) -> dict | None:
        source_url = cam.get('sourceUrl', '')
        try:
            html = fetch(source_url, referer='https://www.skylinewebcams.com/')
        except Exception as e:
            log.warning(f"SkylineWebcams depth-1 failed for {source_url}: {e}")
            return None

        tokens = self.TOKEN_RE.findall(html)
        if not tokens:
            return None

        token = tokens[0]
        hls_url = f"https://hd-auth.skylinewebcams.com/live.m3u8?a={token}"
        return {
            'playUrl': hls_url,
            'playType': 'm3u8',
            'directPlaybackStatus': 'direct_hls',
            'skylineToken': token,
            'skylineTokenNote': 'session-scoped; must refresh via server proxy'
        }


class WorldCamExtractor:
    """
    WorldCam pages load stream URLs via JavaScript (dynamic rendering).
    Static HTML has no direct m3u8. Strategy:
    - Some cams expose Akamai CDN URLs in the JS bundle config
    - Look for rbmn-live.akamaized.net or similar patterns in page JS includes
    """
    AKAMAI_RE = re.compile(
        r'(https?://[a-zA-Z0-9.-]+\.akamaized\.net/[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
        re.IGNORECASE
    )
    
    def extract(self, cam: dict) -> dict | None:
        source_url = cam.get('sourceUrl', '')
        # If playUrl is already set (from prior scrape), validate it
        existing = cam.get('playUrl')
        if existing and 'akamaized.net' in existing:
            status = probe_url(existing)
            if status in (200, 206):
                return {'playUrl': existing, 'directPlaybackStatus': 'direct_hls'}
        
        try:
            html = fetch(source_url, referer='https://worldcam.eu/')
        except Exception as e:
            log.warning(f"WorldCam depth-1 failed for {source_url}: {e}")
            return None

        m = self.AKAMAI_RE.search(html)
        if m:
            return {'playUrl': m.group(1), 'playType': 'm3u8', 'directPlaybackStatus': 'direct_hls'}
        
        return None


class BalticLiveCamExtractor:
    """
    Baltic Live Cam - server-side proxy handles this.
    playUrl should be: https://<proxy>/baltic?id={camId}
    camId is extracted from sourceUrl.
    """
    CAM_ID_RE = re.compile(r'[?&]cam=(\d+)|/cameras?/[^/]+/[^/]+/([^/]+)/?$', re.IGNORECASE)
    
    def extract(self, cam: dict) -> dict | None:
        # Baltic cams are handled by server-side /baltic?id=... endpoint
        # The cam ID comes from the source page's WP post ID
        existing_play = cam.get('playUrl', '')
        if '/baltic?id=' in existing_play or '&ext=.m3u8' in existing_play:
            return None  # already configured
        
        source_url = cam.get('sourceUrl', '')
        try:
            html = fetch(source_url, referer='https://balticlivecam.com/')
            # Look for the WP post/cam ID in the page
            ids = re.findall(r'"cam_id"\s*:\s*"?(\d+)"?', html)
            ids += re.findall(r'cam[_-]?id["\s]*[:=]\s*["\']?(\d+)', html, re.IGNORECASE)
            if ids:
                cam_id = ids[0]
                proxy_url = f"https://158.179.194.163.sslip.io/baltic?id={cam_id}&ext=.m3u8"
                return {'playUrl': proxy_url, 'directPlaybackStatus': 'direct_hls', 'balticCamId': cam_id}
        except Exception as e:
            log.warning(f"Baltic depth-1 failed for {source_url}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────────────────────────────────

EXTRACTORS = {
    'feratel': FeratelExtractor(),
    'feratel – your window to the world': FeratelExtractor(),
    "What's Up Cam": WhatUpCamExtractor(),
    'Camscape': CamscapeExtractor(),
    'SkylineWebcams': SkylineWebcamsExtractor(),
    'WorldCam': WorldCamExtractor(),
    'Baltic Live Cam': BalticLiveCamExtractor(),
    'Panorama.sk': FeratelExtractor(),   # Panorama.sk embeds Feratel iframes
}


def process_cam(cam: dict) -> tuple[str, dict | None]:
    """Return (cam_id, update_dict | None)."""
    cam_id = cam.get('id', 'unknown')
    channel = cam.get('channel', '')
    extractor = EXTRACTORS.get(channel)
    if not extractor:
        return cam_id, None
    try:
        result = extractor.extract(cam)
        return cam_id, result
    except Exception as e:
        log.error(f"Error extracting {cam_id}: {e}")
        return cam_id, None


def main():
    root = Path(__file__).parent.parent
    data_path = root / 'data' / 'world_tour_cams.json'
    
    with open(data_path, encoding='utf-8') as f:
        data = json.load(f)
    
    items = data.get('items', [])
    # Filter: only cams with no playUrl AND an extractor exists
    candidates = [
        cam for cam in items
        if not cam.get('playUrl')
        and not cam.get('sourceOnly')
        and cam.get('channel') in EXTRACTORS
    ]
    
    log.info(f"Total items: {len(items)}, candidates for extraction: {len(candidates)}")
    
    updated = 0
    failed  = 0
    
    # Process with limited concurrency to be respectful
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(process_cam, cam): cam for cam in candidates}
        for future in as_completed(futures):
            cam = futures[future]
            cam_id, result = future.result()
            if result:
                # Update in-place
                for i, item in enumerate(items):
                    if item.get('id') == cam_id:
                        items[i].update(result)
                        updated += 1
                        log.info(f"✅ {cam_id} → {result.get('playUrl','')[:80]}")
                        break
            else:
                failed += 1
                log.warning(f"❌ {cam_id} (channel={cam.get('channel')}): no stream found")
            time.sleep(0.05)  # rate limit
    
    log.info(f"\n=== DONE: updated={updated}, failed={failed} ===")
    
    # Write back
    data['items'] = items
    data['lastExtracted'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    
    log.info(f"Saved {data_path}")
    return updated, failed


if __name__ == '__main__':
    main()
