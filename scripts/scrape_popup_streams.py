import json
import time
import re
import subprocess
import random
import os

DATA_FILE = "cctv_data.json"
UserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    # Atomic save to prevent corruption
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, DATA_FILE)

def fetch_url_content(url):
    # Use curl for stability and TLS handling
    try:
        cmd = [
            "curl", "-s", "-k", "-L",
            "--max-time", "10",
            "-H", f"User-Agent: {UserAgent}",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    data = load_data()
    
    # 1. Identify Targets: UTIC, Popup URL, Not Secured
    targets = []
    for i, item in enumerate(data):
        if item.get('source') != 'UTIC': continue
        url = item.get('url', '')
        name = item.get('name', '')
        
        # Skip already secured
        if '.m3u8' in url or '.mp4' in url: continue
        
        # Target only standard popups
        if 'openDataCctvStream.jsp' in url or 'cctvPopup.do' in url:
            # PRIORITY: Regional (Non-Seoul, Non-Jeju)
            is_seoul = 'Seoul' in url or '서울' in name
            # Block known bad/timeout targets primarily to save time
            is_jeju = 'Jeju' in url or '제주' in name or '1100고지' in name
            
            if not is_seoul and not is_jeju:
                targets.append(i)

    print(f"Found {len(targets)} potential Regional popup streams to scrape.")
    print("Starting SAFE MODE: 1.5s delay between requests.")
    
    # User requested progress bar.
    BATCH_LIMIT = 1000 # "Veteran Hunter" Mode: Large batch, steady pace
    total_targets = len(targets)
    if total_targets > BATCH_LIMIT:
        print(f"Limiting to first {BATCH_LIMIT} items for DETAILED HUNT (Total available: {total_targets})")
        targets = targets[:BATCH_LIMIT]
        total_targets = BATCH_LIMIT
    
    print(f"Processing {total_targets} items...")
    
    # Ensure debug dir exists
    if not os.path.exists("debug_html"):
        os.makedirs("debug_html")

    modified_count = 0
    scanned_count = 0

    try:
        for idx in range(total_targets):
            target_idx = targets[idx]
            item = data[target_idx]
            name = item.get('name')
            url = item.get('url')
            
            scanned_count += 1
            
            # Progress Bar: [====      ] 25% (25/100)
            percent = (idx + 1) / total_targets * 100
            bar_length = 30
            filled_length = int(bar_length * (idx + 1) // total_targets)
            bar = '=' * filled_length + ' ' * (bar_length - filled_length)
            
            print(f"\r[{bar}] {percent:.1f}% ({idx+1}/{total_targets}) Checking: {name}...", end="", flush=True)
            
            html = fetch_url_content(url)
            
            # Extraction Logic
            found_url = None
            
            # Pattern 1: var hurl = "..." or var lurl = "..."
            match = re.search(r'var\s+[hl]url\s*=\s*"([^"]+\.(m3u8|mp4)[^"]*)"', html)
            if match: found_url = match.group(1)
            
            # Pattern 2: src="..." (video tag or source tag)
            if not found_url:
                match = re.search(r'src=["\']([^"\']+\.(m3u8|mp4)[^"\']*)["\']', html)
                if match: found_url = match.group(1)
            
            # Pattern 3: file: "..." (jwplayer/flowplayer)
            if not found_url:
                match = re.search(r'file\s*:\s*["\']([^"\']+\.(m3u8|mp4)[^"\']*)["\']', html)
                if match: found_url = match.group(1)

            # Pattern 4: value="..." (hidden input)
            if not found_url:
                match = re.search(r'value=["\']([^"\']+\.(m3u8|mp4)[^"\']*)["\']', html)
                if match: found_url = match.group(1)

            if found_url:
                if found_url.startswith("http"):
                    data[target_idx]['url'] = found_url
                    modified_count += 1
                    print(f"SUCCESS -> {found_url}")
                else:
                     print(f"FOUND RELATIVE (SKIPPING) -> {found_url}")
            else:
                print("NO MATCH")
                # Save HTML for Pattern Research
                safe_name = re.sub(r'[^a-zA-Z0-9가-힣]', '_', name)
                with open(f"debug_html/{safe_name}.html", "w", encoding='utf-8') as f:
                    f.write(html)
                
            # Checkpoint save every 10 successes
            if modified_count > 0 and modified_count % 10 == 0:
                save_data(data)
                
            # Safety Delay
            time.sleep(1.5 + random.random())

    except KeyboardInterrupt:
        print("\nStopping by user request...")
    finally:
        save_data(data)
        print(f"\nBatch Complete. Scanned: {scanned_count}, Secured: {modified_count}")

if __name__ == "__main__":
    main()
