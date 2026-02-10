import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class DaeguCollector:
    """
    Daegu Metropolitan City Collector.
    Fetches CCTV data from the Daegu Car ITS (car.daegu.go.kr).
    """
    def __init__(self):
        self.list_url = "https://car.daegu.go.kr/map/ajax/getCCTVList/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://car.daegu.go.kr/",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

    def fetch_data(self):
        print("[DAEGU] Fetching CCTV list via API...")
        try:
            payload = "fac_typ_cd=04"
            response = requests.post(self.list_url, headers=self.headers, data=payload, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[DAEGU] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            # Research shows items are in 'result'
            items = data.get("result", [])
            print(f"[DAEGU] Found {len(items)} CCTVs.")

            normalized_data = []
            for item in items:
                # Fields: cctv (ID), facNm, coordX, coordY
                cctv_id = item.get("cctv")
                name = item.get("facNm") or "Unknown"
                lat = item.get("coordY") 
                lng = item.get("coordX")

                if not cctv_id:
                    continue

                # The 'cctv' field might be a comma-separated list like "3,2". 
                # We take the first one or handle it as a single ID if it's just one.
                first_id = cctv_id.split(',')[0] if ',' in str(cctv_id) else cctv_id

                # Pattern: https://carcctv.daegu.go.kr/live1/_definst_/{CHANNEL}.stream/playlist.m3u8
                # Note: Channel IDs often have 'ch' prefix in the final URL.
                channel_id = f"ch{first_id}"
                url = f"https://carcctv.daegu.go.kr/live1/_definst_/{channel_id}.stream/playlist.m3u8"

                normalized_data.append({
                    "id": f"DAEGU_{first_id}",
                    "original_id": str(first_id),
                    "name": name.strip(),
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "DAEGU",
                    "status": "active"
                })

            print(f"[DAEGU] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[DAEGU] Error in fetch_data: {e}")
            return []
