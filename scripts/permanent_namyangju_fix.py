import json
from pathlib import Path

def main():
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / "cctv_data.json"
    overrides_path = base_dir / "cctv_overrides.json"
    
    # Correct Mappings (Checked against backup data and user report)
    # Name -> Correct Stream ID
    CORRECT_MAPPINGS = {
        "마석윗3": "L180009",
        "창현A앞4 (1)": "L180007",
        "창현A앞4 (2)": "L180065",
        "마석사거리(웹)": "L180111",
        "퇴계원사거리": "L180013",
        "퇴계원사거리(웹)": "L180013", # Assuming same stream for web variant
        "양정4 (1)": "L180076",
        "양정4 (2)": "L180076"
    }
    
    # 1. Update cctv_data.json
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    fixed_count = 0
    for item in data:
        name = item.get("name")
        if name in CORRECT_MAPPINGS:
            stream_id = CORRECT_MAPPINGS[name]
            new_url = f"https://211.57.45.101/media/{stream_id}/chunklist.m3u8"
            if item.get("url") != new_url:
                print(f"Fixing {name}: {item.get('url')} -> {new_url}")
                item["url"] = new_url
                item["directUrl"] = new_url
                item["tags"] = list(set(item.get("tags", []) + ["direct_source", "locked_mapping"]))
                fixed_count += 1
                
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    # 2. Update cctv_overrides.json to lock these changes
    with open(overrides_path, "r", encoding="utf-8") as f:
        overrides = json.load(f)
        
    # Remove existing overrides for these names to avoid duplicates (if stored by ID though)
    # We should add/update them by ID
    
    # Get IDs of fixed items for override lookup
    fixed_ids = {item["id"]: item for item in data if item.get("name") in CORRECT_MAPPINGS}
    
    updated_overrides = []
    overridden_ids = set()
    
    # Keep existing overrides that are NOT in our fixed list
    for ovr in overrides:
        if ovr["id"] not in fixed_ids:
            updated_overrides.append(ovr)
        
    # Add our fixed ones
    for cid, cctv in fixed_ids.items():
        updated_overrides.append({
            "id": cid,
            "name": cctv["name"],
            "url": cctv["url"],
            "tags": ["direct_source", "locked_mapping"],
            "_comment": "Permanently locked Namyangju mapping"
        })
        
    with open(overrides_path, "w", encoding="utf-8") as f:
        json.dump(updated_overrides, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccessfully fixed and locked {len(fixed_ids)} Namyangju CCTV mappings.")

if __name__ == "__main__":
    main()
