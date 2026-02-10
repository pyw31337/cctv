import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class UlsanCollector:
    """
    Ulsan Metropolitan City Collector.
    Fetches CCTV data from the Ulsan ITS (its.ulsan.kr).
    """
    def __init__(self):
        self.list_url = "https://its.ulsan.kr/mpng/getList.json"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.ulsan.kr/traffic/cctv.do",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=UTF-8"
        }

    def fetch_data(self):
        print("[ULSAN] Fetching CCTV list via API...")
        try:
            payload = {
                "postData": {
                    "serviceName": "cctvService",
                    "methodName": "getGridList",
                    "paging": False
                }
            }
            response = requests.post(self.list_url, headers=self.headers, json=payload, timeout=30, verify=False)
            if response.status_code != 200:
                print(f"[ULSAN] Failed to fetch list: {response.status_code}")
                # Try fallback to data= if json= fails or returns empty
                response = requests.post(self.list_url, headers=self.headers, data=json.dumps(payload), timeout=30, verify=False)

            print(f"[ULSAN] Status Code: {response.status_code}")
            try:
                json_data = response.json()
                print(f"[ULSAN] JSON Keys: {json_data.keys()}")
                if "data" in json_data:
                    print(f"[ULSAN] Data Keys: {json_data['data'].keys()}")
            except:
                print(f"[ULSAN] Failed to parse JSON. Body snippet: {response.text[:200]}")
                return []

            rows = json_data.get("data", {}).get("rows", [])
            if not rows and "rows" in json_data:
                 rows = json_data["rows"]
                 
            print(f"[ULSAN] Found {len(rows)} CCTVs.")

            normalized_data = []
            for item in rows:
                # Fields: cdId, cdNm, xCrdn, yCrdn, addr
                cctv_id = item.get("cdId")
                name = item.get("cdNm") or "Unknown"
                lat = item.get("yCrdn")
                lng = item.get("xCrdn")
                url = item.get("addr") # This is already the HLS URL

                if not cctv_id or not url:
                    continue

                normalized_data.append({
                    "id": f"ULSAN_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name.strip(),
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "ULSAN",
                    "status": "active"
                })

            print(f"[ULSAN] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[ULSAN] Error in fetch_data: {e}")
            return []
