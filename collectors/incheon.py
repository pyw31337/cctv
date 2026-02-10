import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class IncheonCollector:
    """
    Incheon Traffic Information Center Collector.
    Fetches CCTV data from the public GIS endpoint.
    """
    def __init__(self):
        self.list_url = "https://www.fitic.go.kr/gis/selectListData.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.fitic.go.kr/gis/gisPage.do?preParam=cctv",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[INCHEON] Fetching CCTV list via GIS API...")
        try:
            # Payload discovered from network inspection
            payload = "type=cctv"
            response = requests.post(self.list_url, data=payload, headers=self.headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[INCHEON] Failed to fetch list: {response.status_code}")
                return []

            # The response might be a JSON string that needs secondary parsing
            data = response.json()
            if isinstance(data, str):
                data = json.loads(data)

            items = data.get("result", [])
            print(f"[INCHEON] Found {len(items)} CCTVs.")

            normalized_data = []
            for item in items:
                # Fields: CCTV_NM, CCTV_MNGM_NMBR, HTTPADDR, X_CRDN, Y_CRDN
                cctv_id = item.get("CCTV_MNGM_NMBR")
                name = item.get("CCTV_NM", "Unknown").strip()
                lat = item.get("Y_CRDN")
                lng = item.get("X_CRDN")
                url = item.get("HTTPADDR")

                if not cctv_id or not url:
                    continue
                
                normalized_data.append({
                    "id": f"INCHEON_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name,
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "INCHEON_ITS",
                    "status": "active"
                })

            print(f"[INCHEON] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[INCHEON] Error in fetch_data: {e}")
            return []
