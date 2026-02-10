import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SejongCollector:
    """
    Sejong Special Self-Governing City Collector.
    Fetches CCTV data via bis.sejong.go.kr API.
    """
    def __init__(self):
        self.list_url = "https://bis.sejong.go.kr/web/atms/selectCctvList.do"
        self.api_url = "https://bis.sejong.go.kr/web/atms/getAtmsCctv.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://bis.sejong.go.kr/web/atms/atms_map.view?type=1",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

    def fetch_data(self):
        print("[SEJONG] Fetching CCTV list via API...")
        try:
            # Research shows selectCctvList.do with empty payload
            response = requests.post(self.list_url, headers=self.headers, data="", timeout=30, verify=False)
            if response.status_code != 200:
                print(f"[SEJONG] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            items = data.get("cctvInfoList", [])
            print(f"[SEJONG] Found {len(items)} CCTVs. Resolving stream URLs...")

            normalized_data = []
            for item in items:
                # Fields: cctvid, cctvname, coordx, coordy
                cctv_id = item.get("cctvid")
                name = item.get("cctvname") or "Unknown"
                lat = item.get("coordy") 
                lng = item.get("coordx")

                if not cctv_id:
                    continue

                # Stream URL is resolved via getAtmsCctv.do
                url = self.resolve_stream_url(cctv_id)
                if not url:
                    # Alternative pattern: https://sejongn2.kr/vod/hls-url/{cctv_id}
                    url = self.resolve_alt_stream_url(cctv_id)
                
                if not url:
                    continue

                normalized_data.append({
                    "id": f"SEJONG_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name.strip(),
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "SEJONG",
                    "status": "active"
                })

            print(f"[SEJONG] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[SEJONG] Error in fetch_data: {e}")
            return []

    def resolve_stream_url(self, cctv_id):
        try:
            payload = {"cctv_id": cctv_id}
            resp = requests.post(self.api_url, headers=self.headers, data=payload, timeout=5, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                # Returns cctvList with items containing strm_rtsp_addr or similar
                # However, research suggested sejongn2.kr might be better for HLS
                pass
        except:
            pass
        return None

    def resolve_alt_stream_url(self, cctv_id):
        try:
            # This API was identified as a reliable HLS provider for Sejong
            api_url = f"https://sejongn2.kr/vod/hls-url/{cctv_id}"
            resp = requests.get(api_url, timeout=5, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "SUCCESS":
                    return data.get("msg")
        except:
            pass
        return None
