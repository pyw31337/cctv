#!/usr/bin/env python3
"""
Convert Yeongsangang Flood Control Office CCTV URLs from broken HLS direct URLs
to working iframe (videoDetail.do) format.

Example conversion:
  FROM: https://cctvlo.yeongsanriver.go.kr/live/cctv110083/hls.m3u8
  TO:   https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd=110083
"""

import json
import re
from pathlib import Path

def convert_yeongsanriver_url(url):
    """
    Convert HLS URL to videoDetail.do format.
    Pattern: https://cctvlo.yeongsanriver.go.kr/live/cctv{CODE}/hls.m3u8
    Result: https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={CODE}
    """
    # Already in iframe format
    if "videoDetail.do" in url:
        return url, False
    
    # Match the HLS URL pattern
    match = re.search(r'cctvlo\.yeongsanriver\.go\.kr/live/cctv(\d+)/hls\.m3u8', url)
    if match:
        code = match.group(1)
        new_url = f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={code}"
        return new_url, True
    
    return url, False

def main():
    # Load CCTV data
    data_path = Path(__file__).parent.parent / "cctv_data.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    converted_count = 0
    converted_list = []
    
    for cctv in data:
        url = cctv.get("url", "")
        if "yeongsanriver.go.kr" in url and "cctvlo." in url:
            new_url, was_converted = convert_yeongsanriver_url(url)
            if was_converted:
                converted_count += 1
                converted_list.append({
                    "id": cctv.get("id"),
                    "name": cctv.get("name"),
                    "old_url": url,
                    "new_url": new_url
                })
                cctv["url"] = new_url
    
    # Save updated data
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Converted {converted_count} Yeongsangang CCTVs from HLS to iframe format")
    print("=" * 60)
    
    for item in converted_list[:10]:
        print(f"  {item['id']}: {item['name']}")
        print(f"    OLD: {item['old_url']}")
        print(f"    NEW: {item['new_url']}")
    
    if converted_count > 10:
        print(f"  ... and {converted_count - 10} more")
    
    print(f"\nData saved to: {data_path}")

if __name__ == "__main__":
    main()
