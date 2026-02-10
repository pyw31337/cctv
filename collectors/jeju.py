import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class JejuCollector:
    """
    Jeju Special Self-Governing Province Collector.
    Fetches CCTV data from the public Jeju ITS endpoints.
    """
    def __init__(self):
        self.list_url = "https://www.jejuits.go.kr/jido/getCurFeatures.do"
        self.stream_url_api = "https://www.jejuits.go.kr/jido/streamUrl.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.jejuits.go.kr/jido/mainView.do?DEVICE_KIND=CCTV",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[JEJU] Fetching CCTV list via ITS API...")
        try:
            # Refined payload for the list
            payload = {
                "layerNm": "CCTV",
                "searchWord": "",
                "swLat": 33.1906,
                "swLng": 126.1501,
                "neLat": 33.5855,
                "neLng": 126.9859,
                "maplevel": 10,
                "DEVICE_KIND": "CCTV"
            }
            response = requests.post(self.list_url, data=payload, headers=self.headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[JEJU] Failed to fetch list: {response.status_code}")
                if response.status_code == 403:
                    print(f"[JEJU] 403 Forbidden. Body: {response.text[:200]}")
                return []

            items = response.json()
            print(f"[JEJU] Found {len(items)} CCTVs. Fetching stream URLs...")

            normalized_data = []
            # We fetch stream URLs for all discovered items
            processed = 0
            for item in items:
                # Fields: CCTV_NM, DEVICE_ID, X_CRDN, Y_CRDN, STRM_RTSP_ADDR
                cctv_id = item.get("DEVICE_ID")
                name = item.get("CCTV_NM") or item.get("FCLT_LCTN") or "Unknown"
                lat = item.get("Y_CRDN")
                lng = item.get("X_CRDN")
                stream_uuid = item.get("STRM_RTSP_ADDR")

                if not cctv_id or not stream_uuid:
                    continue

                url = self.fetch_stream_url(stream_uuid)
                if not url:
                    continue

                normalized_data.append({
                    "id": f"JEJU_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name.strip(),
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "JEJU",
                    "status": "active"
                })
                
                processed += 1
                if processed % 50 == 0:
                    print(f"[JEJU] Progress: {processed}/{len(items)} ({len(normalized_data)} successful)")

            print(f"[JEJU] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[JEJU] Error in fetch_data: {e}")
            # If it's a JSON decode error, the response might be HTML (like 403)
            return []

    def fetch_stream_url(self, stream_uuid):
        try:
            payload = {"DEVICE_ID": stream_uuid}
            # Note: streamUrl.do might also be sensitive to UA
            response = requests.post(self.stream_url_api, data=payload, headers=self.headers, timeout=10, verify=False)
            if response.status_code == 200:
                url = response.text.strip()
                if "m3u8" in url:
                    # Clean the URL if it has quotes or extra whitespace
                    url = url.replace('"', '').replace("'", "")
                    return url
        except:
            pass
        return None
