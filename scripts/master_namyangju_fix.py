import json
from pathlib import Path

def main():
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / "cctv_data.json"
    overrides_path = base_dir / "cctv_overrides.json"
    
    # MASTER GOLDEN MAPPING (Verified from cctv_data_pre_audit_v2.json)
    # Using multiple keys (ID + Name) to be absolutely sure.
    GOLDEN_MAPPING = [
        {"name": "마석사거리(웹)", "stream_id": "L180111"},
        {"name": "마석윗3", "stream_id": "L180009"},
        {"name": "창현A앞4 (1)", "stream_id": "L180007"},
        {"name": "창현A앞4 (2)", "stream_id": "L180065"},
        {"name": "퇴계원사거리", "stream_id": "L180013"},
        {"name": "퇴계원사거리(웹)", "stream_id": "L180077"},
        {"name": "양정4 (1)", "stream_id": "L180076"},
        {"name": "양정4 (2)", "stream_id": "L180045"},
        {"name": "샛터3 (1)", "stream_id": "L180021"},
        {"name": "샛터3 (2)", "stream_id": "L180075"} # This STREAM L180075 is 샛터3!
    ]
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    fixed_items = []
    
    for entry in GOLDEN_MAPPING:
        target_name = entry["name"]
        target_stream = entry["stream_id"]
        
        # Find matches by name (handling potential suffixes like (1))
        # Strip suffixes for more flexible matching if needed, but here we are specific
        match_found = False
        for item in data:
            if target_name in item.get("name", ""):
                new_url = f"https://211.57.45.101/media/{target_stream}/chunklist.m3u8"
                if item.get("url") != new_url:
                    print(f"Restoring {item['name']} ({item['id']}): {item.get('url')} -> {new_url}")
                    item["url"] = new_url
                    item["directUrl"] = new_url
                    item["tags"] = list(set(item.get("tags", []) + ["direct_source", "locked_mapping", "fixed_namyangju"]))
                
                fixed_items.append(item)
                match_found = True
        
        if not match_found:
            print(f"Warning: No item found for {target_name}")

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    # Update Overrides
    with open(overrides_path, "r", encoding="utf-8") as f:
        overrides = json.load(f)
        
    # Map by ID for overrides
    fixed_ids = {item["id"]: item for item in fixed_items}
    
    new_overrides = []
    for ovr in overrides:
        if ovr["id"] not in fixed_ids:
            new_overrides.append(ovr)
            
    for cid, item in fixed_ids.items():
        new_overrides.append({
            "id": cid,
            "name": item["name"],
            "url": item["url"],
            "tags": ["direct_source", "locked_mapping", "fixed_namyangju"],
            "_comment": f"Golden Record mapping for {item['name']}"
        })
        
    with open(overrides_path, "w", encoding="utf-8") as f:
        json.dump(new_overrides, f, ensure_ascii=False, indent=2)
        
    print(f"\nSuccessfully restored and locked {len(fixed_ids)} Namyangju streams.")

if __name__ == "__main__":
    main()
