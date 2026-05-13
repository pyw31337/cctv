import requests
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JejuCollector:
    """
    Jeju Special Self-Governing Province Collector.
    Uses the Oracle HTTPS Proxy to bypass authentication/session issues.
    """
    def __init__(self):
        self.list_url = "https://www.jejuits.go.kr/jido/getCurFeatures.do"
        self.proxy_base = "https://158.179.194.163.sslip.io/jeju"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[JEJU] Fetching CCTV list via ITS API...")
        try:
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
            response = requests.post(self.list_url, data=payload, headers=self.headers, timeout=15, verify=False)
            
            if response.status_code != 200:
                print(f"[JEJU] Failed to fetch list: {response.status_code}")
                return []

            items = response.json()
            print(f"[JEJU] Found {len(items)} CCTVs. Applying proxy URLs...")

            normalized_data = []
            for item in items:
                # STRM_RTSP_ADDR is the stream UUID used by streamUrl.do.
                cctv_id = item.get("DEVICE_ID")
                stream_id = item.get("STRM_RTSP_ADDR")
                name = item.get("FCLT_LCTN") or item.get("CCTV_NM") or f"Jeju CCTV {cctv_id}"
                lat = item.get("Y_CRDN")
                lng = item.get("X_CRDN")

                if not cctv_id or not stream_id:
                    continue

                if "시험" in name or "테스트" in name:
                    continue

                # Point to the Oracle proxy with the UUID to avoid a second lookup per play.
                url = f"{self.proxy_base}?id={stream_id}"

                normalized_data.append({
                    "id": f"JEJU_{cctv_id}",
                    "original_id": stream_id,
                    "device_id": cctv_id,
                    "name": name.strip(),
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "JEJU",
                    "status": "active"
                })

            print(f"[JEJU] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[JEJU] Error in fetch_data: {e}")
            return []
