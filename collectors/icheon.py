import requests
import json

class IcheonCollector:
    """
    Icheon ITS CCTV Collector.
    Fetches data from https://its.icheon.go.kr/traf/selectLiveCCTVList.do
    """
    def __init__(self):
        self.url = "https://its.icheon.go.kr/traf/selectLiveCCTVList.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.icheon.go.kr/cctv.view",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://its.icheon.go.kr"
        }

    def fetch_data(self):
        print("[Icheon] Fetching CCTV list...")
        try:
            payload = "cctv_name="
            response = requests.post(self.url, data=payload, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"[Icheon] Failed to fetch list: {response.status_code}")
                return []
            
            data = response.json()
            if "resultList" not in data:
                print("[Icheon] Unexpected response format")
                return []
                
            cctvs = self.parse_cctv_list(data["resultList"])
            print(f"[Icheon] Successfully collected {len(cctvs)} streams.")
            return cctvs

        except Exception as e:
            print(f"[Icheon] Error in fetch_data: {e}")
            return []

    def parse_cctv_list(self, items):
        parsed = []
        for item in items:
            try:
                # Basic validation
                url = item.get("STRM_EXT_HTTP_ADDR")
                name = item.get("LOC_NAME")
                if not url or not name:
                    continue

                # Normalized Object
                cctv = {
                    "id": f"ICITS_{item.get('DEVC_ID', name)}",
                    "original_id": str(item.get('DEVC_ID', '')),
                    "name": name,
                    "lat": float(item["Y_CRDN"]),
                    "lng": float(item["X_CRDN"]),
                    "url": url,
                    "source": "ICITS",
                    "status": "active",
                    "address": item.get("LOC_ADDR", "")
                }
                parsed.append(cctv)
            except Exception as e:
                print(f"[Icheon] Error parsing item {item.get('LOC_NAME', 'unknown')}: {e}")
                continue
                
        return parsed
