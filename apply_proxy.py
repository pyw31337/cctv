
import json
import os
from urllib.parse import urlparse, parse_qs

PROXY_BASE = "https://cctv-proxy-hoon-001.fly.dev"
DATA_FILE = "cctv_data.json"

# Known RTSP patterns (Same as extract_rtsp.py)
RTSP_PATTERNS = {
    "C": {"template": "rtsp://{cctvip}:554/live/{id}.stream", "notes": "Suwon ITS"},
    "y": {"template": "rtsp://{cctvip}:554/{id}", "notes": "Yeosu ITS"},
    "J": {"template": "rtsp://{cctvip}:554/live/{id}", "notes": "Ulsan ITS"},
    "H": {"template": "rtsp://{cctvip}:554/{id}", "notes": "Daegu ITS"},
    "F": {"template": "rtsp://{cctvip}:554/live/{id}", "notes": "Jeonju ITS"},
    "Y": {"template": "rtsp://{cctvip}:554/{id}", "notes": "Changwon ITS"}
}

def extract_params(url):
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
    kind = params.get("kind", "")
    if kind not in RTSP_PATTERNS: return None
    
    template = RTSP_PATTERNS[kind]["template"]
    try:
        url = template.format(
            cctvip=params.get("cctvip", ""),
            id=params.get("id", params.get("cctvid", ""))
        )
        return url
    except:
        return None

def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated_ssl = 0
    updated_rtsp = 0
    
    for item in data:
        original_url = item.get("url", "")
        
        # 1. Apply proxy to SSL issue streams
        if item.get("sslIssue") is True:
            # Avoid double proxying
            if PROXY_BASE not in original_url:
                item["url"] = f"{PROXY_BASE}/proxy?url={original_url}"
                item["proxyActive"] = True
                updated_ssl += 1
                
        # 2. Convert ActiveX Popup to RTSP Proxy
        if "openDataCctvStream.jsp" in original_url:
            params = extract_params(original_url)
            kind = params.get("kind", "")
            
            if kind in RTSP_PATTERNS:
                rtsp_url = construct_rtsp_url(params)
                if rtsp_url:
                    item["url"] = f"{PROXY_BASE}/stream?url={rtsp_url}"
                    item["proxyActive"] = True
                    item["source"] = f"{item.get('source', 'UTIC')}_RTSP_Proxy"
                    item["note"] = f"Converted from {kind} Popup to RTSP"
                    updated_rtsp += 1

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Updated {updated_ssl} SSL streams.")
    print(f"Updated {updated_rtsp} RTSP streams (from Popup).")

if __name__ == "__main__":
    main()
