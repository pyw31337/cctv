import requests
import urllib3
import time
import datetime

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DaejeonCollector:
    """
    Daejeon Traffic Information Center Collector.
    Fetches CCTV data from the public API and constructs stream URLs.
    """
    def __init__(self):
        self.list_url = "https://traffic.daejeon.go.kr/web-service/api/v1/traffic/getCctvList"
        self.video_api_url = "https://traffic.daejeon.go.kr/web-service/api/v1/traffic/getCctvVideoUrl"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://traffic.daejeon.go.kr/traffic/cctv",
            "Content-Type": "application/json"
        }

    def fetch_data(self):
        print("[DAEJEON] Fetching CCTV list via API...")
        try:
            response = requests.post(self.list_url, json={}, headers=self.headers, timeout=30, verify=False)
            if response.status_code != 200:
                print(f"[DAEJEON] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            items = data if isinstance(data, list) else data.get("list", [])
            print(f"[DAEJEON] Found {len(items)} CCTVs.")

            normalized_data = []
            now = datetime.datetime.now()
            # Timestamp for URL construction: YYYYMMDD.HHMMSS
            # Note: Daejeon uses 100-second offsets (00, 01, 02) or similar.
            # Usually, the current minute or previous minute works.
            # Pattern: 20260210.090300
            # From research: 09:03:00 and 09:05:00 were seen.
            # We'll use a slightly lagging timestamp to ensure the file exists.
            target_time = now - datetime.timedelta(minutes=2)
            timestamp = target_time.strftime("%Y%m%d.%H%M00")

            for item in items:
                # equipLocatn: name, matrixinId: ID
                cctv_id = item.get("matrixinId")
                name = item.get("equipLocatn", "Unknown").strip()
                lat = item.get("convY") # Note: Daejeon response used convY for lat
                lng = item.get("convX") # convX for lng

                if not cctv_id or not lat or not lng:
                    continue

                # Construction pattern: https://tportal.daejeon.go.kr:37084/01/media/{cctv_id}/{cctv_id}_{timestamp}.000.mp4
                # Note: matrixinId is like CCTV08, but in URL it was CTV0008.
                # Let's check the ID formats. CCTV08 -> CTV0008? or just CTV0008 directly?
                # Browser research showed: matrixinId "CCTV08" -> media "CTV0008"
                # This suggests a transformation: 'CCTV' -> 'CTV00' or padding.
                
                # If matrixinId is CCTV08, we need CTV0008.
                # If matrixinId is CTV0008 already, we use it.
                stream_id = cctv_id
                if cctv_id.startswith("CCTV"):
                    num = cctv_id[4:] # "08"
                    stream_id = f"CTV{num.zfill(4)}"

                # Construct stream URL
                url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_{timestamp}.000.mp4"

                normalized_data.append({
                    "id": f"DAEJEON_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "url": url,
                    "urlType": "daejeon_mp4_dynamic",
                    "source": "DAEJEON_ITS",
                    "status": "active"
                })

            print(f"[DAEJEON] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[DAEJEON] Error in fetch_data: {e}")
            return []
