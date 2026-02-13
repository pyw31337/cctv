import requests
import json

class FITICCollector:
    """
    Fishing Information and Technical Institute Center (FITIC) Collector.
    Fetches data from https://fitic.go.kr/gis/selectListData.do
    """
    def __init__(self):
        self.url = "https://fitic.go.kr/gis/selectListData.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://fitic.go.kr/gis/gisPage.do",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://fitic.go.kr"
        }

    def fetch_data(self):
        print("[FITIC] Fetching CCTV list...")
        try:
            payload = "type=cctv"
            response = requests.post(self.url, data=payload, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                print(f"[FITIC] Failed to fetch list: {response.status_code}")
                return []
            
            # FITIC API는 이중 JSON을 반환함
            # response.json() → 문자열 (바깥 JSON)
            # json.loads(문자열) → 실제 딕셔너리 (안쪽 JSON)
            raw = response.json()
            if isinstance(raw, str):
                data = json.loads(raw)
            else:
                data = raw
                
            if "result" not in data:
                print("[FITIC] Unexpected response format")
                return []
                
            cctvs = self.parse_cctv_list(data["result"])
            print(f"[FITIC] Successfully collected {len(cctvs)} streams.")
            return cctvs

        except Exception as e:
            print(f"[FITIC] Error in fetch_data: {e}")
            return []

    def parse_cctv_list(self, items):
        parsed = []
        for item in items:
            try:
                # Basic validation
                if not item.get("HTTPADDR") or not item.get("CCTV_NM"):
                    continue

                # URL Transformation
                # Original: http://61.40.94.13:1935/cctv/L115.stream/playlist.m3u8
                # Target: https://cctv.fitic.go.kr/cctv/L115.stream/playlist.m3u8
                
                original_url = item["HTTPADDR"]
                if "61.40.94.13:1935" in original_url:
                    stream_url = original_url.replace("http://61.40.94.13:1935", "https://cctv.fitic.go.kr")
                else:
                    stream_url = original_url

                # Normalized Object
                cctv = {
                    "id": f"FITIC_{item['CCTV_MNGM_NMBR']}",
                    "original_id": str(item['CCTV_MNGM_NMBR']),
                    "name": item["CCTV_NM"],
                    "lat": float(item["Y_CRDN"]),
                    "lng": float(item["X_CRDN"]),
                    "url": stream_url,
                    "source": "FITIC",
                    "status": "active"
                }
                parsed.append(cctv)
            except Exception as e:
                print(f"[FITIC] Error parsing item {item.get('CCTV_NM', 'unknown')}: {e}")
                continue
                
        return parsed
