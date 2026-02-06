#!/usr/bin/env python3
"""
Restore Namyangju CCTV URLs from pre-audit backup.
The previous fix broke the correct URL mappings.

Original data (cctv_data_pre_audit_v2.json) had the correct URL mappings.
Restore those URLs for all L180xxx CCTVs.
"""

import json
from pathlib import Path

def main():
    base = Path(__file__).parent.parent
    
    # Load backup data with correct URLs
    backup_path = base / "cctv_data_pre_audit_v2.json"
    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    # Create lookup by ID from backup
    backup_lookup = {}
    for item in backup_data:
        cctv_id = item.get("id", "")
        if cctv_id.startswith("L180"):
            backup_lookup[cctv_id] = item.get("url", "")
    
    print(f"Loaded {len(backup_lookup)} L180 entries from backup")
    
    # Load current data
    current_path = base / "cctv_data.json"
    with open(current_path, "r", encoding="utf-8") as f:
        current_data = json.load(f)
    
    # Restore URLs from backup
    restored = 0
    for item in current_data:
        cctv_id = item.get("id", "")
        if cctv_id in backup_lookup:
            backup_url = backup_lookup[cctv_id]
            current_url = item.get("url", "")
            if backup_url and current_url != backup_url:
                item["url"] = backup_url
                restored += 1
                if restored <= 10:
                    print(f"  Restored {cctv_id}: {item.get('name', '')}")
                    print(f"    From: {current_url}")
                    print(f"    To:   {backup_url}")
    
    # Save updated data
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f, ensure_ascii=False, indent=2)
    
    print(f"\nRestored {restored} URLs from backup")
    print(f"Saved to: {current_path}")

if __name__ == "__main__":
    main()
