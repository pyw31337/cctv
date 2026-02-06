#!/usr/bin/env python3
"""
Convert Namyangju CCTVs from direct HLS to proper UTIC iframe format.
The user provided correct URL format with cctvid and id parameters.

User provided examples:
- 마석사거리(웹): cctvid=L180075, id=L180111
- 마석윗3: cctvid=L180076, id=L180009

Current incorrect format:
  https://211.57.45.101/media/L180111/chunklist.m3u8

Correct UTIC iframe format:
  https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=...&cctvid=L180075&id=L180111&cctvip=211.57.45.101&kind=n
"""

import json
import re
from pathlib import Path

UTIC_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"

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
        
        # Only process L180 entries with direct HLS URLs
        if cctv_id.startswith("L180") and "211.57.45.101/media/" in url:
            # Extract stream ID from URL
            match = re.search(r'/media/(L\d+)/', url)
            if match:
                stream_id = match.group(1)
                # Build UTIC iframe URL
                encoded_name = name  # Could URL encode, but UTIC seems to handle it
                new_url = (
                    f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?"
                    f"key={UTIC_KEY}"
                    f"&cctvid={cctv_id}"
                    f"&cctvName={name}"
                    f"&kind=n"
                    f"&cctvip=211.57.45.101"
                    f"&cctvch=undefined"
                    f"&id={stream_id}"
                    f"&cctvpasswd=undefined"
                    f"&cctvport=undefined"
                )
                cctv["url"] = new_url
                fixed += 1
                fixed_list.append({
                    "id": cctv_id,
                    "name": name,
                    "stream_id": stream_id
                })
    
    # Save updated data
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Converted {fixed} Namyangju CCTVs to UTIC iframe format")
    print("=" * 60)
    
    # Show specific targets
    targets = ["마석사거리", "마석윗3", "창현A앞4"]
    for item in fixed_list:
        if any(t in item["name"] for t in targets):
            print(f"  {item['id']}: {item['name']} → stream={item['stream_id']}")
    
    print(f"\nSaved to: {data_path}")

if __name__ == "__main__":
    main()
