import json
import requests
import datetime
import concurrent.futures
import sys

# Configuration
DATA_FILE = "cctv_data.json"
MAX_WORKERS = 20

def load_data():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

def check_cctv(cctv):
    url = cctv.get('url')
    if not url: return None
    
    try:
        if '.m3u8' in url:
            r = requests.head(url, timeout=5)
        else:
            r = requests.get(url, timeout=5, stream=True)
            
        if r.status_code < 400:
            return None # Good
        else:
            return {'id': cctv['id'], 'name': cctv['name'], 'error': f"Status {r.status_code}"}
    except Exception as e:
         return {'id': cctv['id'], 'name': cctv['name'], 'error': str(e)}

def main():
    print("Starting Weekly Validation...")
    data = load_data()
    if not data: return

    # Strategy: Modulo 5 based on Index
    # This guarantees every CCTV is checked once a week regardless of location metadata quality.
    
    weekday = datetime.datetime.now().weekday()
    if weekday > 4: 
        print("Weekend - Skipping or running debug mode.")
        weekday = 0 
    
    targets = [item for i, item in enumerate(data) if i % 5 == weekday]
    print(f"Total CCTVs: {len(data)}. Targets for today (Modulo 5 == {weekday}): {len(targets)}")
    
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_cctv, cctv): cctv for cctv in targets}
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            if i % 100 == 0: print(f"Progress: {i}/{len(targets)}", end='\r')
            result = future.result()
            if result:
                failures.append(result)
                
    print(f"\nValidation Complete.")
    print(f"Checked: {len(targets)}")
    print(f"Failures: {len(failures)}")
    
    if failures:
        print("Failed CCTVs:")
        for f in failures[:20]:
            print(f" - {f['name']} ({f['id']}): {f['error']}")
        
        with open(f"validation_failure_{weekday}.json", "w", encoding="utf-8") as f:
            json.dump(failures, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
