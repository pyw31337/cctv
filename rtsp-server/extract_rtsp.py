#!/usr/bin/env python3
"""
Extract RTSP streams from cctv_data.json for conversion server.
Identifies ActiveX-dependent streams (Kind: C, y, J, H, F, Y) and
constructs potential RTSP URLs based on known patterns.
"""
import json
import os
from urllib.parse import urlparse, parse_qs

CCTV_DATA = "../cctv_data.json"
OUTPUT_FILE = "streams.json"

# Known RTSP patterns by Kind
RTSP_PATTERNS = {
    "C": {  # 수원 (Suwon)
        "template": "rtsp://{cctvip}:554/live/{id}.stream",
        "notes": "Suwon ITS RTSP"
    },
    "y": {  # 여수 (Yeosu)
        "template": "rtsp://{cctvip}:554/{id}",
        "notes": "Yeosu ITS"
    },
    "J": {  # 울산 (Ulsan)
        "template": "rtsp://{cctvip}:554/live/{id}",
        "notes": "Ulsan ITS"
    },
    "H": {  # 대구 (Daegu)
        "template": "rtsp://{cctvip}:554/{id}",
        "notes": "Daegu ITS"
    },
    "F": {  # 전주 (Jeonju)
        "template": "rtsp://{cctvip}:554/live/{id}",
        "notes": "Jeonju ITS"
    },
    "Y": {  # 창원 (Changwon)
        "template": "rtsp://{cctvip}:554/{id}",
        "notes": "Changwon ITS"
    }
}

def extract_params(url):
    """Extract parameters from popup URL"""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return {
            "kind": params.get("kind", [""])[0],
            "cctvip": params.get("cctvip", [""])[0],
            "id": params.get("id", [""])[0],
            "cctvid": params.get("cctvid", [""])[0],
        }
    except:
        return {}

def construct_rtsp_url(params):
    """Construct RTSP URL based on known patterns"""
    kind = params.get("kind", "")
    if kind not in RTSP_PATTERNS:
        return None
    
    pattern = RTSP_PATTERNS[kind]
    template = pattern["template"]
    
    try:
        return template.format(
            cctvip=params.get("cctvip", ""),
            id=params.get("id", params.get("cctvid", ""))
        )
    except:
        return None

def main():
    # Load CCTV data
    with open(CCTV_DATA, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    streams = []
    stats = {}
    
    for item in data:
        url = item.get("url", "")
        name = item.get("name", "Unknown")
        
        # Skip already secured streams
        if ".m3u8" in url or ".mp4" in url:
            continue
        
        # Skip non-popup streams
        if "openDataCctvStream.jsp" not in url:
            continue
        
        params = extract_params(url)
        kind = params.get("kind", "")
        
        if kind in RTSP_PATTERNS:
            rtsp_url = construct_rtsp_url(params)
            if rtsp_url:
                stream_id = f"{kind.lower()}_{params.get('id', 'unknown')}"
                streams.append({
                    "id": stream_id,
                    "name": name,
                    "kind": kind,
                    "rtsp_url": rtsp_url
                })
                
                stats[kind] = stats.get(kind, 0) + 1
    
    # Save output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(streams, f, ensure_ascii=False, indent=2)
    
    print(f"Extracted {len(streams)} RTSP streams")
    print("\nBy Kind:")
    for kind, count in sorted(stats.items()):
        notes = RTSP_PATTERNS.get(kind, {}).get("notes", "Unknown")
        print(f"  {kind}: {count} ({notes})")
    
    print(f"\nSaved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
