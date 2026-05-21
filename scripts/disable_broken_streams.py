
import json
import os

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")
FAILED_STREAMS_FILE = os.path.join(BASE_DIR, "failed_streams.json")

def load_json(filepath):
    if not os.path.exists(filepath):
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("Flagging broken streams for manual_check (preserve list/markers)...")
    
    failed_data = load_json(FAILED_STREAMS_FILE)
    cctv_data = load_json(CCTV_DATA_FILE)
    
    if not failed_data or not cctv_data:
        print("Error: Could not load data files.")
        return

    failures = failed_data.get("failures", {})
    
    target_ids = set()
    
    # Collect IDs from http_404
    for item in failures.get("http_404", []):
        target_ids.add(item["id"])
        
    print(f"Found {len(target_ids)} streams with 404 errors to flag for review.")
    
    # Apply to cctv_data
    flagged_count = 0
    for item in cctv_data:
        if item.get("id") in target_ids:
            if item.get("status") != "manual_check" or item.get("health_reason") != "health_check_http_404":
                item["status"] = "manual_check"
                item["health_reason"] = "health_check_http_404"
                item["status_note"] = "Review needed: Returned 404 during health check"
                flagged_count += 1
                print(f"Flagging {item['name']} ({item['id']})")
                
    if flagged_count > 0:
        save_json(CCTV_DATA_FILE, cctv_data)
        print(f"Successfully flagged {flagged_count} streams for review.")
    else:
        print("No active streams matched the failure list.")

if __name__ == "__main__":
    main()
