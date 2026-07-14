import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")
CORE_OUTPUT_FILE = os.path.join(BASE_DIR, "data", "cctv_core.json")
EXTENDED_OUTPUT_FILE = os.path.join(BASE_DIR, "data", "cctv_extended.json")

def main():
    if not os.path.exists(CCTV_DATA_FILE):
        print(f"[Error] {CCTV_DATA_FILE} not found")
        return

    print("Loading cctv_data.json...")
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded {len(data)} items. Splitting...")

    core_data = []
    extended_data = {}

    core_keys = {"id", "name", "lat", "lng", "source", "url", "directUrl", "original_id"}

    for item in data:
        cid = item.get("id")
        if not cid:
            continue

        # Build core item
        core_item = {}
        for k in core_keys:
            if k in item:
                core_item[k] = item[k]
        core_data.append(core_item)

        # Build extended item if there are non-core keys
        ext_item = {}
        for k, v in item.items():
            if k not in core_keys:
                ext_item[k] = v
        
        if ext_item:
            extended_data[cid] = ext_item

    # Ensure output directory exists
    os.makedirs(os.path.dirname(CORE_OUTPUT_FILE), exist_ok=True)

    print("Writing cctv_core.json...")
    with open(CORE_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(core_data, f, ensure_ascii=False)

    print("Writing cctv_extended.json...")
    with open(EXTENDED_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(extended_data, f, ensure_ascii=False)

    print(f"Splitting completed successfully. Core items: {len(core_data)}, Extended items: {len(extended_data)}")

if __name__ == "__main__":
    main()
