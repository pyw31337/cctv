#!/usr/bin/env python3
"""
Fix Namyangju (남양주) CCTV URL mismatch issues.
The URL stream ID should match the CCTV ID.

Problem: 
- L180195 (창현A앞4) has URL pointing to L180013 (different CCTV)
- L180196 (창현A앞4) has URL pointing to L180077

Solution: 
Fix URL to use the CCTV ID in the stream path.
Pattern: https://211.57.45.101/media/{CCTV_ID}/chunklist.m3u8
"""

import json
import re
from pathlib import Path

def main():
    data_path = Path(__file__).parent.parent / "cctv_data.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    fixed_count = 0
    fixed_list = []
    
    for cctv in data:
        url = cctv.get("url", "")
        cctv_id = cctv.get("id", "")
        
        # Match Namyangju pattern: https://211.57.45.101/media/{stream_id}/chunklist.m3u8
        if "211.57.45.101/media/" in url and cctv_id.startswith("L180"):
            match = re.search(r"/media/(L\d+)/", url)
            if match:
                stream_id = match.group(1)
                if stream_id != cctv_id:
                    # Mismatch! Fix the URL
                    new_url = url.replace(f"/media/{stream_id}/", f"/media/{cctv_id}/")
                    fixed_count += 1
                    fixed_list.append({
                        "id": cctv_id,
                        "name": cctv.get("name"),
                        "old_url": url,
                        "new_url": new_url,
                        "old_stream": stream_id
                    })
                    cctv["url"] = new_url
    
    # Save updated data
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Fixed {fixed_count} Namyangju CCTV URL mismatches")
    print("=" * 60)
    
    for item in fixed_list[:20]:
        print(f"  {item['id']}: {item['name']}")
        print(f"    Stream was: {item['old_stream']} -> Changed to: {item['id']}")
    
    if fixed_count > 20:
        print(f"  ... and {fixed_count - 20} more")
    
    print(f"\nData saved to: {data_path}")

if __name__ == "__main__":
    main()
