#!/usr/bin/env python3
"""
Fix Namyangju CCTV URLs by matching on NAME instead of ID.
The IDs are different between current and backup data.
"""

import json
from pathlib import Path

def main():
    base = Path(__file__).parent.parent
    
    # Load backup data with correct URLs
    backup_path = base / "cctv_data_pre_audit_v2.json"
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    # Create lookup by NAME from backup (for L180 entries)
    backup_lookup = {}
    for item in backup_data:
        cctv_id = item.get("id", "")
        name = item.get("name", "")
        url = item.get("url", "")
        if cctv_id.startswith("L180") and name and url:
            # Store by name (use first occurrence)
            if name not in backup_lookup:
                backup_lookup[name] = url
    
    print(f"Loaded {len(backup_lookup)} unique L180 names from backup")
    
    # Load current data
    current_path = base / "cctv_data.json"
    with open(current_path, "r", encoding="utf-8") as f:
        current_data = json.load(f)
    
    # Fix URLs based on name matching
    fixed = 0
    fixed_list = []
    for item in current_data:
        cctv_id = item.get("id", "")
        name = item.get("name", "")
        current_url = item.get("url", "")
        
        # Only fix L180 entries
        if cctv_id.startswith("L180") and name in backup_lookup:
            backup_url = backup_lookup[name]
            if current_url != backup_url:
                item["url"] = backup_url
                fixed += 1
                fixed_list.append({
                    "id": cctv_id,
                    "name": name,
                    "old": current_url,
                    "new": backup_url
                })
    
    # Save updated data
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
    
    print(f"Fixed {fixed} URLs by name matching")
    print("=" * 60)
    
    # Show specific targets
    targets = ["마석사거리(웹)", "마석윗3", "창현A앞4"]
    for item in fixed_list:
        if any(t in item["name"] for t in targets):
            print(f"  {item['id']}: {item['name']}")
            print(f"    OLD: {item['old']}")
            print(f"    NEW: {item['new']}")
    
    print(f"\nSaved to: {current_path}")

if __name__ == "__main__":
    main()
