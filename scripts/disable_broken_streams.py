
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
    print("Disabling broken streams...")
    
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
        
    print(f"Found {len(target_ids)} streams with 404 errors to disable.")
    
    # Apply to cctv_data
    disabled_count = 0
    for item in cctv_data:
        if item.get("id") in target_ids:
            if item.get("status") != "inactive":
                item["status"] = "inactive"
                item["status_note"] = "Auto-disabled: Returned 404 during health check"
                disabled_count += 1
                print(f"Disabling {item['name']} ({item['id']})")
                
    if disabled_count > 0:
        save_json(CCTV_DATA_FILE, cctv_data)
        print(f"Successfully disabled {disabled_count} streams.")
    else:
        print("No active streams matched the failure list.")

if __name__ == "__main__":
    main()
