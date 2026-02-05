#!/usr/bin/env python3
"""
Playwright-based scraper for ActiveX-dependent CCTV streams.
This uses a headless browser to render JavaScript and intercept network requests
to capture the actual stream URLs that ActiveX players would use.
"""
import asyncio
import json
import re
import time
from urllib.parse import urlparse, parse_qs

# Check if playwright is installed
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run: pip install playwright && playwright install chromium")
    exit(1)

DATA_FILE = "cctv_data.json"
BATCH_LIMIT = 50  # Start small for testing
DELAY_SECONDS = 2.0  # Safe mode delay

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def find_activex_targets(data):
    """Find streams that are likely ActiveX-dependent (Kind: C, y, J, H, etc.)"""
    targets = []
    for i, item in enumerate(data):
        url = item.get('url', '')
        # Skip already secured streams
        if 'm3u8' in url or 'mp4' in url:
            continue
        # Target popup-based streams
        if 'openDataCctvStream.jsp' in url:
            # Parse the kind parameter
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            kind = params.get('kind', [''])[0]
            # Target known ActiveX kinds
            if kind in ['C', 'y', 'J', 'H', 'F', 'Y', 'II', 'HH']:
                targets.append((i, item, kind))
    return targets

async def scrape_with_playwright(page, url, name):
    """
    Use Playwright to load the popup and intercept network requests.
    ActiveX streams often make requests to RTSP-to-HLS converters or direct video endpoints.
    """
    found_url = None
    
    # Set up request interception to catch stream URLs
    async def handle_request(route, request):
        nonlocal found_url
        req_url = request.url
        # Look for stream URLs in network requests
        if '.m3u8' in req_url or '.mp4' in req_url or 'stream' in req_url or ':1935/' in req_url:
            found_url = req_url
        await route.continue_()
    
    async def handle_response(response):
        nonlocal found_url
        resp_url = response.url
        # Check response URLs
        if '.m3u8' in resp_url or '.mp4' in resp_url:
            found_url = resp_url
    
    try:
        # Intercept all requests
        await page.route("**/*", handle_request)
        page.on("response", handle_response)
        
        # Navigate to the popup URL
        await page.goto(url, wait_until='networkidle', timeout=15000)
        
        # Wait a bit for any lazy-loaded video
        await asyncio.sleep(2)
        
        # If no network interception, try to find video source in DOM
        if not found_url:
            # Look for video elements
            found_url = await page.evaluate("""
                () => {
                    // Check video src
                    const video = document.querySelector('video');
                    if (video && video.src) return video.src;
                    
                    // Check source tags
                    const source = document.querySelector('source');
                    if (source && source.src) return source.src;
                    
                    // Check for hurl/lurl variables
                    if (typeof hurl !== 'undefined') return hurl;
                    if (typeof lurl !== 'undefined') return lurl;
                    
                    // Check for data attributes
                    const player = document.querySelector('[data-src]');
                    if (player) return player.getAttribute('data-src');
                    
                    return null;
                }
            """)
        
        return found_url
        
    except Exception as e:
        print(f"    Error: {e}")
        return None

async def main():
    data = load_data()
    targets = find_activex_targets(data)
    
    print(f"Found {len(targets)} ActiveX-dependent streams to process.")
    print(f"Limiting to first {BATCH_LIMIT} items for testing.")
    
    targets = targets[:BATCH_LIMIT]
    total = len(targets)
    secured = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        for idx, (data_idx, item, kind) in enumerate(targets):
            name = item.get('name', 'Unknown')
            url = item.get('url', '')
            
            # Progress bar
            progress = int((idx + 1) / total * 30)
            bar = '=' * progress + ' ' * (30 - progress)
            print(f"\r[{bar}] {((idx+1)/total*100):.1f}% ({idx+1}/{total}) {name[:20]}...", end='', flush=True)
            
            stream_url = await scrape_with_playwright(page, url, name)
            
            if stream_url and ('.m3u8' in stream_url or '.mp4' in stream_url):
                print(f" SUCCESS -> {stream_url[:50]}...")
                data[data_idx]['url'] = stream_url
                secured += 1
            else:
                print(f" NO MATCH (Kind: {kind})")
            
            # Safe mode delay
            await asyncio.sleep(DELAY_SECONDS)
        
        await browser.close()
    
    # Save results
    save_data(data)
    print(f"\n\nBatch Complete. Scanned: {total}, Secured: {secured}")

if __name__ == "__main__":
    asyncio.run(main())
