#!/usr/bin/env python3
"""
Restore Namyangju CCTVs from UTIC iframe back to direct HLS format.
Use the correct stream IDs that we identified.
"""

import json
import re
from pathlib import Path

def main():
    base = Path(__file__).parent.parent
    data_path = base / "cctv_data.json"
    
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    fixed = 0
    fixed_list = []
    
    for cctv in data:
        cctv_id = cctv.get("id", "")
        url = cctv.get("url", "")
        name = cctv.get("name", "")
        
        # Only process L180 entries with UTIC iframe URLs
        if cctv_id.startswith("L180") and "openDataCctvStream.jsp" in url:
            # Extract stream ID from URL's id= parameter
            match = re.search(r'[&?]id=(L\d+)', url)
            if match:
                stream_id = match.group(1)
                # Convert back to direct HLS
                new_url = f"https://211.57.45.101/media/{stream_id}/chunklist.m3u8"
                cctv["url"] = new_url
                # Add direct_source tag if not present
                if "tags" not in cctv:
                    cctv["tags"] = []
                if "direct_source" not in cctv["tags"]:
                    cctv["tags"].append("direct_source")
                fixed += 1
                fixed_list.append({
                    "id": cctv_id,
                    "name": name,
                    "stream_id": stream_id
                })
    
    # Save updated data
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Restored {fixed} Namyangju CCTVs to direct HLS format")
    print("=" * 60)
    
    # Show specific targets
    targets = ["마석사거리", "마석윗3", "창현A앞4"]
    for item in fixed_list:
        if any(t in item["name"] for t in targets):
            print(f"  {item['id']}: {item['name']} → {item['stream_id']}")
    
    print(f"\nSaved to: {data_path}")

if __name__ == "__main__":
    main()
