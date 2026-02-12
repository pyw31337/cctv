
import json
import os
import sys

# Add parent directory to path to import collectors
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collectors.daejeon import DaejeonCollector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("Restoring Daejeon data...")
    
    # 1. Fetch new data
    collector = DaejeonCollector()
    new_items = collector.fetch_data()
    
    if not new_items:
        print("Failed to fetch Daejeon data.")
        return
        
    print(f"Fetched {len(new_items)} items from Daejeon API.")
    
    # 2. Load existing data
    data = load_json(CCTV_DATA_FILE)
    original_count = len(data)
    
    # 3. Append new items (filtering duplicates if any exist, though unlikely given missing source)
    existing_ids = set(item["id"] for item in data)
    
    added_count = 0
    for item in new_items:
        if item["id"] not in existing_ids:
            data.append(item)
            added_count += 1
            
    # 4. Save
    if added_count > 0:
        save_json(CCTV_DATA_FILE, data)
        print(f"Successfully added {added_count} Daejeon streams.")
        print(f"Total streams: {original_count} -> {len(data)}")
    else:
        print("No new items added (all duplicates?).")

if __name__ == "__main__":
    main()
