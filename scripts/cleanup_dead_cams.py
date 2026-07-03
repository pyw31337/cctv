#!/usr/bin/env python3
import json
import ssl
import urllib.request
import urllib.parse
from pathlib import Path
import concurrent.futures

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data' / 'world_tour_cams.json'

UNVERIFIED_CONTEXT = ssl._create_unverified_context()

def check_hls_url(url, timeout=5):
    """
    Checks if the stream URL responds with 200 OK and valid HLS headers/content.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=timeout, context=UNVERIFIED_CONTEXT) as response:
            status_code = response.getcode()
            if status_code != 200:
                return False, f"HTTP {status_code}"
            content = response.read(1024).decode('utf-8', errors='ignore')
            if "#EXTM3U" in content or "tracks-v1a1" in content or "mono.ts" in content:
                return True, "Valid HLS content"
            return False, "Not a valid HLS playlist"
    except Exception as e:
        return False, str(e)

def check_youtube_video(video_id, timeout=5):
    """
    Checks if a YouTube video is still active.
    """
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.getcode() == 200:
                return True, "Active"
            return False, f"oEmbed HTTP {response.getcode()}"
    except Exception as e:
        return False, str(e)

def main():
    if not DATA_PATH.exists():
        print(f"Data file not found at {DATA_PATH}")
        return

    print("Loading database...")
    payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    items = payload.get('items', [])

    # Filter targets that are active and play via HLS/YouTube
    targets = []
    for item in items:
        if not item.get('sourceOnly'):
            targets.append(item)

    print(f"Total active promoted items to check: {len(targets)}")

    cleaned_count = 0
    results = {}

    def test_item(item):
        play_url = item.get('playUrl')
        video_id = item.get('videoId')
        
        if play_url:
            success, reason = check_hls_url(play_url)
            return item['id'], success, reason
        elif video_id:
            success, reason = check_youtube_video(video_id)
            return item['id'], success, reason
        return item['id'], True, "Direct preview bypass"

    # Test concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        futures = {executor.submit(test_item, item): item for item in targets}
        for future in concurrent.futures.as_completed(futures):
            item_id, success, reason = future.result()
            results[item_id] = (success, reason)

    # Apply cleanup
    for item in items:
        item_id = item.get('id')
        if item_id in results:
            success, reason = results[item_id]
            if not success:
                print(f"[CLEANUP] Demoting {item_id} -> {reason}")
                item['sourceOnly'] = True
                item['playbackStatus'] = 'unstable'
                item['directProbeStatus'] = f"AutoCleanup: {reason}"
                cleaned_count += 1

    if cleaned_count > 0:
        print(f"\nSaving {cleaned_count} updated/demoted items back to {DATA_PATH}...")
        DATA_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
        print("Cleanup completed successfully.")
    else:
        print("\nNo unstable streams detected. Everything is clean!")

if __name__ == '__main__':
    main()
