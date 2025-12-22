import requests
import re
import json
import urllib.parse
import time

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
MAIN_URL = "https://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
API_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
HEADERS = {
    "Referer": MAIN_URL,
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
OUTPUT_FILE = "cctv_data.json"

def get_cctv_ids():
    print("Fetching main page...")
    response = requests.get(MAIN_URL, headers=HEADERS, verify=False)
    response.raise_for_status()
    
    # Extract IDs using regex: javascript:test('L933061')
    ids = re.findall(r"javascript:test\('([^']+)'\)", response.text)
    print(f"Found {len(ids)} CCTV IDs.")
    return list(set(ids)) # Remove duplicates

def fetch_cctv_details(cctv_id):
    params = {"cctvId": cctv_id}
    try:
        response = requests.get(API_URL, params=params, headers=HEADERS, verify=False)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching details for {cctv_id}: {e}")
        return None

def check_url_status(url):
    """Check if URL is accessible"""
    if not url:
        return "unknown"
    
    try:
        # For regular URLs, try HEAD request
        response = requests.head(url, timeout=3, verify=False, allow_redirects=True)
        if response.status_code < 400:
            return "active"
        else:
            return "error"
    except:
        # If HEAD fails, try GET with minimal data
        try:
            response = requests.get(url, timeout=3, verify=False, allow_redirects=True, stream=True)
            if response.status_code < 400:
                return "active"
            else:
                return "error"
        except:
            return "error"

def construct_url(cctv_id, details):
    if not details:
        return None
        
    # Extract fields with defaults
    cctv_ip = details.get("CCTVIP", "")
    cctv_name = details.get("CCTVNAME", "")
    kind = details.get("KIND", "")
    cctv_ch = details.get("CH", "")
    cctv_passwd = details.get("PASSWD", "")
    cctv_port = details.get("PORT", "")
    # Some fields might be missing or null in JSON, handle gracefully
    
    # Special Cases (Flood Control)
    if "E61" in cctv_id: # Nakdong River
        return f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={details.get('ID', '')}"
    elif "E60" in cctv_id: # Han River
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={details.get('ID', '')}"
    elif "E62" in cctv_id: # Geum River
        return f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={cctv_passwd}&cctvcd={details.get('ID', '')}"
    elif "E63" in cctv_id: # Yeongsan River
        return f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={cctv_passwd}"
    
    # General Case
    # URL Encode Name
    encoded_name = urllib.parse.quote(cctv_name)
    encoded_name_double = urllib.parse.quote(encoded_name) # The JS does encodeURI(encodeURIComponent(name)) which is double encoding? 
    # Wait, JS: encodeURI(encodeURIComponent(streamCctv.gCctvName))
    # encodeURIComponent encodes everything. encodeURI encodes spaces etc but leaves ://.
    # If name is "가거도", encodeURIComponent -> "%EA%B0%80%EA%B1%B0%EB%8F%84"
    # encodeURI("%EA%B0%80%EA%B1%B0%EB%8F%84") -> "%25EA%25B0%2580%25EA%25B1%25B0%25EB%258F%2584" ?
    # Let's check the JS again: encodeURI(encodeURIComponent(streamCctv.gCctvName))
    # Yes, it seems to double encode special chars because % becomes %25.
    # Let's try single encoding first as it's safer for now, or replicate exactly.
    # Python's quote is similar to encodeURIComponent.
    
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))

    base_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
    query_params = {
        "key": KEY,
        "cctvid": cctv_id,
        "cctvName": encoded_name, # We manually encoded this, so pass as string? No, requests will encode again.
        # Actually, if we construct the string manually we have control.
        "kind": kind,
        "cctvip": cctv_ip,
        "cctvch": cctv_ch if cctv_ch else "null",
        "id": details.get("ID", "null"),
        "cctvpasswd": cctv_passwd if cctv_passwd else "null",
        "cctvport": cctv_port if cctv_port else "null"
    }
    
    # Construct query string manually to match the double encoding behavior if needed, 
    # but requests.get params usually encodes. 
    # The JS constructs: ...&cctvName=' + encodeURI(encodeURIComponent(streamCctv.gCctvName)) + ...
    # So the final URL has double encoded name.
    
    # Let's build the URL string manually to be safe and exact.
    
    params_str = f"key={KEY}&cctvid={cctv_id}&cctvName={encoded_name}&kind={kind}&cctvip={cctv_ip}&cctvch={query_params['cctvch']}&id={query_params['id']}&cctvpasswd={query_params['cctvpasswd']}&cctvport={query_params['cctvport']}"
    
    return f"{base_url}?{params_str}"

def main():
    ids = get_cctv_ids()
    # Collect all items (removed limit)
    print(f"Found {len(ids)} total CCTV IDs")
    results = []
    
    print(f"Processing {len(ids)} items...")
    for i, cctv_id in enumerate(ids):
        details = fetch_cctv_details(cctv_id)
        if details:
            url = construct_url(cctv_id, details)
            if url:
                # Check URL status
                print(f"Checking {cctv_id}...", end=" ")
                status = check_url_status(url)
                print(status)
                
                # Add coords for the map service
                results.append({
                    "id": cctv_id,
                    "name": details.get("CCTVNAME"),
                    "lat": details.get("YCOORD"),
                    "lng": details.get("XCOORD"),
                    "url": url,
                    "status": status
                })
        
        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(ids)}")
        
        time.sleep(0.2) # Slightly longer delay for status checking

    print(f"Saving {len(results)} records to {OUTPUT_FILE}...")
    
    # Print summary
    active_count = sum(1 for r in results if r.get("status") == "active")
    error_count = sum(1 for r in results if r.get("status") == "error")
    print(f"Summary: {active_count} active, {error_count} error/unreachable")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Done.")

if __name__ == "__main__":
    main()
