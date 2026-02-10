import requests
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class BusanCollector:
    """
    Busan ITS (Information Technology & Services) Collector.
    Fetches CCTV data from the public API endpoint.
    """
    def __init__(self):
        self.api_url = "https://its.busan.go.kr/api/cctv/list.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.busan.go.kr/trf/cctv.do"
        }

    def fetch_data(self):
        print("[BUSAN] Fetching CCTV list via API...")
        try:
            response = requests.get(self.api_url, headers=self.headers, timeout=30, verify=False)
            if response.status_code != 200:
                print(f"[BUSAN] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            items = data.get("list", [])
            print(f"[BUSAN] Found {len(items)} CCTVs.")

            normalized_data = []
            for item in items:
                cctv_id = item.get("cctvId")
                name = item.get("instlPos", "Unknown").strip()
                lat = item.get("lat")
                lng = item.get("lot")
                url = item.get("hlsAddr")

                if not cctv_id or not url or not lat or not lng:
                    continue

                # Ensure https for the stream URL if it's on a known busan.go.kr host
                if url.startswith("http://") and "busan.go.kr" in url:
                    url = url.replace("http://", "https://")

                normalized_data.append({
                    "id": f"BUSAN_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "url": url,
                    "source": "BUSAN_ITS",
                    "status": "active"
                })

            print(f"[BUSAN] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[BUSAN] Error in fetch_data: {e}")
            return []
