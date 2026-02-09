#!/usr/bin/env python3
"""
Restore Suwon CCTV URLs (L19xxxx) from pre-audit backup.
These streams use the cctv-proxy-hoon-001.fly.dev proxy.
"""

import json
from pathlib import Path

def main():
    base = Path(__file__).parent.parent
    
    # Load backup data with correct URLs
    backup_path = base / "cctv_data_pre_audit_v2.json"
    if not backup_path.exists():
        print(f"Backup file not found: {backup_path}")
        return

    with open(backup_path, "r", encoding="utf-8") as f:
        backup_data = json.load(f)
    
    # Create lookup by ID from backup
    # Only target Suwon IDs (L19xxxx) and ensure they are proxy URLs
    backup_lookup = {}
    for item in backup_data:
        cctv_id = item.get("id", "")
        url = item.get("url", "")
        # Suwon IDs start with L19
        if cctv_id.startswith("L19") and "fly.dev" in url:
            backup_lookup[cctv_id] = url
            # Also restore the source field to indicate it's a proxy
            # But here we just restore URL for simplicity, or should we restore whole object?
            # Let's just restore URL for now to minimize side effects.
    
    print(f"Loaded {len(backup_lookup)} Suwon proxy entries from backup")
    
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
            
            # If current URL is different (e.g. reverted to UTIC JSP), restore it
            if current_url != backup_url:
                item["url"] = backup_url
                item["source"] = "UTIC_RTSP_Proxy" # Mark as proxy source
                restored += 1
                if restored <= 5:
                    print(f"  Restored {cctv_id}: {item.get('name', '')}")
                    print(f"    To: {backup_url}")
    
    if restored > 0:
        # Save updated data
        with open(current_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nRestored {restored} Suwon URLs from backup")
        print(f"Saved to: {current_path}")
    else:
        print("\nNo Suwon URLs needed restoration (already match or not found).")

if __name__ == "__main__":
    main()
