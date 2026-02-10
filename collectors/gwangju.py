import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GwangjuCollector:
    """
    Gwangju Metropolitan City Collector.
    Fetches CCTV data from the Gwangju ITS (gjtic.go.kr).
    """
    def __init__(self):
        self.list_url = "https://gjtic.go.kr/cctvList"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://gjtic.go.kr/cctv",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json"
        }

    def fetch_data(self):
        print("[GWANGJU] Fetching CCTV list via API...")
        try:
            response = requests.get(self.list_url, headers=self.headers, timeout=30, verify=False)
            if response.status_code != 200:
                print(f"[GWANGJU] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            sect_groups = data.get("sectGroups", {})
            
            normalized_data = []
            for sect_name, items in sect_groups.items():
                if not isinstance(items, list):
                    continue
                for item in items:
                    # Fields: id, cctvNm, lgtd, lttd, videoLink
                    cctv_id = item.get("id")
                    name = item.get("cctvNm") or "Unknown"
                    lat = item.get("lttd")
                    lng = item.get("lgtd")
                    url = item.get("videoLink")

                    if not cctv_id or not url:
                        continue

                    if url.startswith("/"):
                        url = f"https://gjtic.go.kr{url}"

                    normalized_data.append({
                        "id": f"GWANGJU_{cctv_id}",
                        "original_id": str(cctv_id),
                        "name": f"[{sect_name}] {name.strip()}",
                        "lat": float(lat) if lat else 0.0,
                        "lng": float(lng) if lng else 0.0,
                        "url": url,
                        "source": "GWANGJU",
                        "status": "active"
                    })

            print(f"[GWANGJU] Successfully normalized {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[GWANGJU] Error in fetch_data: {e}")
            return []
