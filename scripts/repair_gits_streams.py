#!/usr/bin/env python3
import json
import requests
import os
import sys
import concurrent.futures
from datetime import datetime
import threading

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collectors.gits import GitsCollector

CCTV_DATA_FILE = "cctv_data.json"
REPAIR_LOG = "gits_repair.log"

# Circuit Breaker Config
MAX_CONSECUTIVE_FAILURES = 20
failure_counter = 0
counter_lock = threading.Lock()

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(REPAIR_LOG, "a") as f:
        f.write(line + "\n")

def check_gits_server_health():
    """Initial check to see if GITS server is responsive at all."""
    try:
        url = "https://gits.gg.go.kr/web/map/webMap.do"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        return resp.status_code == 200
    except Exception as e:
        log(f"Pre-flight check failed: {e}")
        return False

def check_stream_health(item):
    global failure_counter
    
    # Check circuit breaker
    with counter_lock:
        if failure_counter >= MAX_CONSECUTIVE_FAILURES:
            return False

    url = item.get("url", "")
    if not url: return False
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Use HEAD to check if token is still valid. 
        # GITS tokens redirect to a validminutes=120 URL. HEAD usually follows redirect.
        response = requests.head(url, headers=headers, timeout=5, allow_redirects=True, verify=False)
        if response.status_code == 200:
            with counter_lock:
                failure_counter = 0 # Reset on success
            return True
        else:
            with counter_lock:
                failure_counter += 1
            return False
    except:
        with counter_lock:
            failure_counter += 1
        return False

def main():
    if not os.path.exists(CCTV_DATA_FILE):
        log("CCTV data file not found.")
        return

    log("Starting GITS Stream Repair Process...")
    
    # 0. Pre-flight Check
    if not check_gits_server_health():
        log("CRITICAL: GITS Server appears to be down or unreachable. Aborting repair to prevent mass timeouts.")
        return

    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Filter GITS streams
    gits_streams = [item for item in data if item.get("source") == "GITS"]
    log(f"Found {len(gits_streams)} GITS streams to check.")

    # 1. Concurrent Health Check
    failed_items = []
    log("Checking stream health...")
    
    global failure_counter
    failure_counter = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_item = {executor.submit(check_stream_health, item): item for item in gits_streams}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                is_healthy = future.result()
                if not is_healthy:
                    failed_items.append(item)
            except Exception:
                failed_items.append(item)
            
            # Check circuit breaker status
            with counter_lock:
                if failure_counter >= MAX_CONSECUTIVE_FAILURES:
                    log(f"Circuit breaker tripped! {failure_counter} consecutive failures. Aborting health check.")
                    executor.shutdown(wait=False, cancel_futures=True)
                    break

    log(f"Detected {len(failed_items)} failed GITS streams (or aborted early).")
    
    # If we aborted early due to circuit breaker, we should NOT attempt repair on just the failed ones, 
    # as the server is likely down.
    if failure_counter >= MAX_CONSECUTIVE_FAILURES:
        log("Skipping repair phase due to circuit breaker trip.")
        return

    if not failed_items:
        log("All GITS streams are healthy. No repair needed.")
        return

    # 2. Repair Failed Streams
    log(f"Repairing {len(failed_items)} streams...")
    collector = GitsCollector()
    
    repaired_count = 0
    repair_failures = 0
    MAX_REPAIR_FAILURES = 10 # Abort if repair fails 10 times in a row

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
                            repair_failures = 0 # Reset
                            break
                else:
                    repair_failures += 1
            except Exception as e:
                log(f"Error repairing {item['id']}: {e}")
                repair_failures += 1
            
            if repair_failures >= MAX_REPAIR_FAILURES:
                log("Too many consecutive repair failures. Aborting.")
                executor.shutdown(wait=False, cancel_futures=True)
                break

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
