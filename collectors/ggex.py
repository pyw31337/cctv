import requests
import json

class GGEXCollector:
    """
    Gyeonggi Expressway (GGEX) CCTV Collector.
    Fetches data from http://www.ggex.co.kr/traffic/getCctvList.do
    """
    def __init__(self):
        self.url = "http://www.ggex.co.kr/traffic/getCctvList.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://www.ggex.co.kr/traffic/realTime.do",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[GGEX] Fetching CCTV list...")
        try:
            response = requests.post(self.url, headers=self.headers, timeout=15)
            
            if response.status_code != 200:
                print(f"[GGEX] Failed to fetch list: {response.status_code}")
                return []
            
            data = response.json()
            rows = data.get("rows", [])
            if not rows:
                print("[GGEX] No data found or unexpected response format")
                return []
                
            cctvs = self.parse_cctv_list(rows)
            print(f"[GGEX] Successfully collected {len(cctvs)} streams.")
            return cctvs

        except Exception as e:
            print(f"[GGEX] Error in fetch_data: {e}")
            return []

    def parse_cctv_list(self, items):
        parsed = []
        for item in items:
            try:
                # Fields: cctvId, title, posLat, posLong, streamHttp
                url = item.get("streamHttp")
                name = item.get("title")
                if not url or not name:
                    continue

                # Normalized Object
                cctv = {
                    "id": f"GGEX_{item.get('cctvId', name)}",
                    "original_id": str(item.get('cctvId', '')),
                    "name": name,
                    "lat": float(item["posLat"]),
                    "lng": float(item["posLong"]),
                    "url": url,
                    "source": "GGEX",
                    "status": "active"
                }
                parsed.append(cctv)
            except Exception as e:
                print(f"[GGEX] Error parsing item {item.get('title', 'unknown')}: {e}")
                continue
                
        return parsed
