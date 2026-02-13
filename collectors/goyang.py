import requests
import json

class GoyangCollector:
    """
    Goyang ITS CCTV Collector.
    Fetches data from https://its.goyang.go.kr/traf/selectMainCCTVList.do
    """
    def __init__(self):
        self.url = "https://its.goyang.go.kr/traf/selectMainCCTVList.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.goyang.go.kr/traffic_cctv.view",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

    def fetch_data(self):
        print("[Goyang] Fetching CCTV list...")
        try:
            # Although research showed null payload, POST often needs empty strings
            payload = ""
            response = requests.post(self.url, data=payload, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"[Goyang] Failed to fetch list: {response.status_code}")
                return []
            
            data = response.json()
            if "resultList" not in data:
                print("[Goyang] Unexpected response format")
                return []
                
            cctvs = self.parse_cctv_list(data["resultList"])
            print(f"[Goyang] Successfully collected {len(cctvs)} streams.")
            return cctvs

        except Exception as e:
            print(f"[Goyang] Error in fetch_data: {e}")
            return []

    def parse_cctv_list(self, items):
        parsed = []
        for item in items:
            try:
                # Actual Fields: LOC_NAME, STRM_HTTP_ADDR, X_CRDN, Y_CRDN
                url = item.get("STRM_HTTP_ADDR")
                name = item.get("LOC_NAME")
                if not url or not name:
                    continue

                # Normalized Object
                cctv = {
                    "id": f"GOYANG_{item.get('MGMT_NUM', name)}",
                    "original_id": str(item.get('MGMT_NUM', '')),
                    "name": name,
                    "lat": float(item.get("Y_CRDN", 0)),
                    "lng": float(item.get("X_CRDN", 0)),
                    "url": url,
                    "source": "GOYANG",
                    "status": "active"
                }
                parsed.append(cctv)
            except Exception as e:
                print(f"[Goyang] Error parsing item {item.get('LOC_NAME', 'unknown')}: {e}")
                continue
                
        return parsed
