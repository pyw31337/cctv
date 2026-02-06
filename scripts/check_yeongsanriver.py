#!/usr/bin/env python3
"""
Check all Yeongsangang Flood Control Office CCTV streams.
Test the HLS URLs to ensure they are working properly.
Reference working example: https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd=110083
Direct HLS: https://cctvlo.yeongsanriver.go.kr/live/cctv110083/hls.m3u8
"""

import json
import sys
import requests
from pathlib import Path

def check_hls_stream(url, timeout=5):
    """Check if an HLS stream URL is accessible."""
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            content = resp.text
            # Check if it's a valid HLS playlist
            if "#EXTM3U" in content:
                return "OK", resp.status_code
            else:
                return "INVALID_CONTENT", resp.status_code
        else:
            return "HTTP_ERROR", resp.status_code
    except requests.exceptions.Timeout:
        return "TIMEOUT", None
    except requests.exceptions.ConnectionError:
        return "CONNECTION_ERROR", None
    except Exception as e:
        return f"ERROR: {str(e)}", None

def main():
    # Load CCTV data
    data_path = Path(__file__).parent.parent / "cctv_data.json"
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Filter for Yeongsanriver CCTVs
    yeongsang_cctvs = [c for c in data if "yeongsanriver.go.kr" in (c.get("url") or "")]
    
    print(f"Found {len(yeongsang_cctvs)} Yeongsangang Flood Control Office CCTVs")
    print("=" * 60)
    
    results = {"ok": [], "failed": []}
    
    for cctv in yeongsang_cctvs:
        cctv_id = cctv.get("id", "unknown")
        name = cctv.get("name", "unnamed")
        url = cctv.get("url", "")
        
        print(f"Checking {cctv_id}: {name}...")
        status, code = check_hls_stream(url)
        
        if status == "OK":
            results["ok"].append({"id": cctv_id, "name": name, "url": url})
            print(f"  ✓ OK")
        else:
            results["failed"].append({
                "id": cctv_id, 
                "name": name, 
                "url": url, 
                "status": status, 
                "code": code
            })
            print(f"  ✗ FAILED ({status}, code={code})")
    
    print("\n" + "=" * 60)
    print(f"Summary: {len(results['ok'])} OK, {len(results['failed'])} FAILED")
    
    if results["failed"]:
        print("\nFailed CCTVs:")
        for item in results["failed"]:
            print(f"  - {item['id']}: {item['name']}")
            print(f"    URL: {item['url']}")
            print(f"    Status: {item['status']}, Code: {item['code']}")
    
    # Output JSON report
    report_path = Path(__file__).parent.parent / "yeongsanriver_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nReport saved to: {report_path}")
    
    return 0 if not results["failed"] else 1

if __name__ == "__main__":
    sys.exit(main())
