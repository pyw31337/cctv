import json
import requests
import concurrent.futures
import re
from collections import defaultdict
import time
import urllib3
import sys

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = "cctv_data.json"
MAX_WORKERS = 50  # Adjust based on network capability
TIMEOUT = 5

def load_data(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def get_region(name):
    # Extract region from format like "[Highway Name] Location" or "[City] Location"
    match = re.search(r'\[(.*?)\]', name)
    if match:
        return match.group(1)
    return "Unknown"

def check_stream(cctv):
    url = cctv.get('url')
    cctv_id = cctv.get('id')
    name = cctv.get('name', 'Unknown')
    region = get_region(name)
    
    if not url:
        return {'id': cctv_id, 'region': region, 'status': 'no_url'}

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # Try HEAD first
        response = requests.head(url, headers=headers, timeout=TIMEOUT, verify=False, allow_redirects=True)
        if response.status_code < 400:
            return {'id': cctv_id, 'region': region, 'status': 'ok'}
        
        # Fallback to GET with stream=True (don't download body)
        response = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False, stream=True, allow_redirects=True)
        if response.status_code < 400:
            return {'id': cctv_id, 'region': region, 'status': 'ok'}
        else:
            return {'id': cctv_id, 'region': region, 'status': 'error', 'code': response.status_code}
            
    except requests.exceptions.RequestException:
        return {'id': cctv_id, 'region': region, 'status': 'error', 'code': 'conn_err'}
    except Exception as e:
        return {'id': cctv_id, 'region': region, 'status': 'error', 'code': str(e)}

def main():
    print(f"Loading {DATA_FILE}...")
    data = load_data(DATA_FILE)
    if not data:
        return

    print(f"Validating {len(data)} streams with {MAX_WORKERS} workers...")
    
    results_by_region = defaultdict(lambda: {'total': 0, 'ok': 0, 'error': 0, 'no_url': 0})
    
    start_time = time.time()
    
    completed = 0
    total = len(data)
    
    jsonl_file = open("validation_results.jsonl", "w", encoding="utf-8")
    
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_cctv = {executor.submit(check_stream, item): item for item in data}
            
            for future in concurrent.futures.as_completed(future_to_cctv):
                result = future.result()
                
                # Write to file immediately
                json.dump(result, jsonl_file, ensure_ascii=False)
                jsonl_file.write('\n')
                jsonl_file.flush() # Ensure it's written
                
                region = result['region']
                status = result['status']
                
                results_by_region[region]['total'] += 1
                results_by_region[region][status] += 1
                
                completed += 1
                if completed % 100 == 0:
                    print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)", end='\r')
                    
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user.")
    finally:
        jsonl_file.close()
        print(f"\nValidation stop/finished in {time.time() - start_time:.2f} seconds.")
        
        print("\n" + "="*50)
        print("REGIONS WITH > 10 FAILURES")
        print("="*50)
        print(f"{'Region':<30} | {'Total':<8} | {'Failures':<8} | {'% Fail':<8}")
        print("-" * 65)
        
        found_issues = False
        sorted_regions = sorted(results_by_region.items(), key=lambda x: (x[1]['error'] + x[1]['no_url']), reverse=True)
        
        for region, stats in sorted_regions:
            failures = stats['error'] + stats['no_url']
            if failures > 10:
                found_issues = True
                fail_rate = (failures / stats['total']) * 100
                print(f"{region:<30} | {stats['total']:<8} | {failures:<8} | {fail_rate:.1f}%")
                
        if not found_issues:
            print("No regions found with more than 10 failures.")

if __name__ == "__main__":
    main()
