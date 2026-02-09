#!/usr/bin/env python3
import json
import requests
import os
import sys
import concurrent.futures
from datetime import datetime

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.gits import GitsCollector

CCTV_DATA_FILE = "cctv_data.json"
REPAIR_LOG = "gits_repair.log"

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(REPAIR_LOG, "a") as f:
        f.write(line + "\n")

def check_stream_health(item):
    url = item.get("url", "")
    if not url: return False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Use HEAD to check if token is still valid. 
        # GITS tokens redirect to a validminutes=120 URL. HEAD usually follows redirect.
        response = requests.head(url, headers=headers, timeout=5, allow_redirects=True, verify=False)
        return response.status_code == 200
    except:
        return False

def main():
    if not os.path.exists(CCTV_DATA_FILE):
        log("CCTV data file not found.")
        return

    log("Starting GITS Stream Repair Process...")
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter GITS streams
    gits_streams = [item for item in data if item.get("source") == "GITS"]
    log(f"Found {len(gits_streams)} GITS streams to check.")

    # 1. Concurrent Health Check
    failed_items = []
    log("Checking stream health...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_item = {executor.submit(check_stream_health, item): item for item in gits_streams}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            if not future.result():
                failed_items.append(item)

    log(f"Detected {len(failed_items)} failed GITS streams.")
    if not failed_items:
        log("All GITS streams are healthy. No repair needed.")
        return

    # 2. Repair Failed Streams
    log(f"Repairing {len(failed_items)} streams...")
    collector = GitsCollector()
    
    repaired_count = 0
    # Use max_workers=5 for repair to be extremely safe/gentle
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_item = {executor.submit(collector.fetch_stream_url, item): item for item in failed_items}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                new_url = future.result()
                if new_url:
                    # Update in the main data list
                    for target in data:
                        if target['id'] == item['id']:
                            target['url'] = new_url
                            target['lastRepaired'] = datetime.now().isoformat()
                            repaired_count += 1
                            break
            except Exception as e:
                log(f"Error repairing {item['id']}: {e}")

    log(f"Successfully repaired {repaired_count}/{len(failed_items)} streams.")

    # 3. Save if changes made
    if repaired_count > 0:
        with open(CCTV_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log("Updated cctv_data.json saved.")
    else:
        log("No streams were successfully repaired.")

if __name__ == "__main__":
    main()
