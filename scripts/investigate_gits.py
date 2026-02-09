import requests
import re
from urllib.parse import unquote

def fetch_cctv_list():
    url = "https://gits.gg.go.kr/web/map/webLoadCCTVData.do"
    print(f"Fetching list from {url}...")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to fetch list: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching list: {e}")
        return None

def parse_cctv_list(data):
    # data format: pipe separated string with @ delimiters? No, loop in JS splits by @ then /
    # .../1@1200/호매실IC/126.948265/37.26113/3/2/1@...
    
    items = data.strip().split('@')
    parsed = []
    for item in items:
        parts = item.split('/')
        if len(parts) >= 4:
            # layout based on JS:
            # var id = eachValue[0];
            # var location = eachValue[1];
            # var x = eachValue[2];
            # var y = eachValue[3];
            cctv = {
                "id": parts[0],
                "name": parts[1],
                "lng": parts[2],
                "lat": parts[3]
            }
            parsed.append(cctv)
    return parsed

def fetch_stream_token(cctv_id):
    url = f"https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId={cctv_id}"
    print(f"Fetching popup for ID {cctv_id}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            html = response.text
            # Look for: var videoUrl = "http://gitsview.gg.go.kr/1200/4+B70..."
            # or: $.get("//gitsview.gg.go.kr/1200/gas16...!hls"
            
            # Pattern 1: iPhone videoUrl
            match_iphone = re.search(r'var videoUrl = "(http://gitsview.gg.go.kr/[^"]+)"', html)
            if match_iphone:
                return match_iphone.group(1)
            
            # Pattern 2: $.get HLS
            match_hls = re.search(r'\$\.get\("([^"]+!hls)"', html)
            if match_hls:
                # Often scheme-less //
                url = match_hls.group(1)
                if url.startswith("//"):
                    url = "http:" + url
                return url
                
            return None
        return None
    except Exception as e:
        print(f"Error fetching popup: {e}")
        return None

def main():
    raw_data = fetch_cctv_list()
    if not raw_data:
        return

    cctvs = parse_cctv_list(raw_data)
    print(f"Found {len(cctvs)} CCTVs.")
    
    # Check specific ID 1200
    print("\nChecking known ID: 1200")
    token_url = fetch_stream_token("1200")
    if token_url:
        print(f"  Stream URL: {token_url}")
    else:
        print("  Failed to extract token URL for 1200")

    # Check first few from list
    for cctv in cctvs[:3]:
        print(f"\nChecking: {cctv['name']} (ID: {cctv['id']})")
        token_url = fetch_stream_token(cctv['id'])
        if token_url:
            print(f"  Stream URL: {token_url}")
        else:
            print("  Failed to extract token URL")
            # Dump HTML for debugging
            cctv_id = cctv['id']
            with open(f"gits_popup_{cctv_id}.html", "w") as f:
                # Re-fetch or pass headers... just re-fetch for simplicity
                headers = {"User-Agent": "Mozilla/5.0"}
                resp = requests.get(f"https://gits.gg.go.kr/web/popup/webCctvPopup.do?cctvId={cctv_id}", headers=headers)
                f.write(resp.text)
            print(f"  Dumped HTML to gits_popup_{cctv_id}.html")

if __name__ == "__main__":
    main()
