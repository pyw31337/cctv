import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Jeju ITS API Enpoints
LIST_API = "https://www.jejuits.go.kr/jido/getCurFeatures.do"
PROXY_BASE = "https://158.179.194.163.sslip.io/jeju"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}

def collect_jeju_cctv():
    print("Collecting Jeju CCTV list...")
    
    # Bounding box covering Jeju Island
    payload = {
        "layerNm": "CCTV",
        "searchWord": "",
        "swLat": "33.1",
        "swLng": "126.1",
        "neLat": "33.6",
        "neLng": "127.0",
        "maplevel": "11",
        "DEVICE_KIND": "CCTV"
    }

    try:
        resp = requests.post(LIST_API, data=payload, headers=HEADERS, timeout=10, verify=False)
        if resp.status_code != 200:
            print(f"Failed to fetch list: {resp.status_code}")
            return []
        
        items = resp.json()
        print(f"Found {len(items)} items.")
        
        cctv_list = []
        for item in items:
            # STRM_RTSP_ADDR is the stream UUID used by streamUrl.do.
            short_id = item.get('DEVICE_ID')
            uuid = item.get('STRM_RTSP_ADDR')
            name = item.get('FCLT_LCTN') or item.get('CCTV_NM') or f"Jeju CCTV {short_id}"
            lat = item.get('Y_CRDN')
            lng = item.get('X_CRDN')

            if not short_id or not uuid:
                continue

            # Skip if name indicates it's not a real CCTV (sometimes they have dummy entries)
            if "시험" in name or "테스트" in name:
                continue

            proxy_url = f"{PROXY_BASE}?id={uuid}"

            cctv_entry = {
                "id": f"JEJU_{short_id}",
                "original_id": uuid,
                "device_id": short_id,
                "name": name,
                "lat": float(lat) if lat else 0.0,
                "lng": float(lng) if lng else 0.0,
                "url": proxy_url,
                "source": "JEJU",
                "status": "active"
            }
            cctv_list.append(cctv_entry)
            
        return cctv_list

    except Exception as e:
        print(f"Error during collection: {e}")
        return []

def merge_data(new_data):
    try:
        with open('cctv_data.json', 'r') as f:
            existing_data = json.load(f)
    except FileNotFoundError:
        existing_data = []

    # Remove old JEJU entries
    print(f"Existing total: {len(existing_data)}")
    filtered_data = [x for x in existing_data if x.get('source') != 'JEJU' and not x['id'].startswith('JEJU_')]
    print(f"After removing old JEJU: {len(filtered_data)}")
    
    # Add new JEJU entries
    merged = filtered_data + new_data
    print(f"New total: {len(merged)}")
    
    with open('cctv_data.json', 'w', encoding='utf-8') as f:
        json.dump(merged, f, indent=2, ensure_ascii=False, sort_keys=True)
    print("cctv_data.json updated.")

if __name__ == "__main__":
    jeju_cctvs = collect_jeju_cctv()
    if jeju_cctvs:
        merge_data(jeju_cctvs)
    else:
        print("No data collected.")
