import requests
import urllib3
import json

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GangwonCollector:
    """
    Gangwon Province Collector (Gangneung ITS).
    Fetches CCTV data from the Gangneung ITS public endpoints.
    """
    def __init__(self):
        self.list_url = "https://its.gn.go.kr/main/selectCctvList"
        self.stream_api_url = "https://its.gn.go.kr/popup/getCctvCamUrl"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.gn.go.kr/main",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[GANGWON] Fetching Gangneung CCTV list...")
        try:
            # The list endpoint expects a POST, often with empty or simple data
            payload = "layerGubn=CCTV"
            response = requests.post(self.list_url, headers=self.headers, data=payload, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[GANGWON] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            # Gangneung list is under 'rows'
            items = data.get("rows", [])
            print(f"[GANGWON] Found {len(items)} CCTVs in Gangneung.")

            normalized_data = []
            for item in items:
                # Fields: name, code (e.g., CCTV000019), wgs84X, wgs84Y
                cctv_id = item.get("code")
                name = item.get("name") or "Unknown"
                lat = item.get("wgs84Y")
                lng = item.get("wgs84X")

                if not cctv_id:
                    continue

                # Note: Gangneung's getCctvCamUrl often returns MSE/blob info 
                # that is not directly playable as HLS. 
                # However, many Gangwon CCTVs are also in UTIC/ITS.
                # We fetch the stream URL if it returns HLS.
                url = self.fetch_stream_url(cctv_id, name)
                
                # If we couldn't get a direct URL, we still provide the entry 
                # if coordinates are available, as the main pipeline might refine it.
                # But for now, let's only add if we have a URL or if it's a known regional source.
                
                normalized_data.append({
                    "id": f"GANGWON_GN_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": f"[강릉] {name.strip()}",
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url if url else "", 
                    "source": "GANGWON",
                    "status": "active" if url else "inactive"
                })

            print(f"[GANGWON] Successfully normalized {len([d for d in normalized_data if d['url']])} playable streams.")
            return normalized_data

        except Exception as e:
            print(f"[GANGWON] Error in fetch_data: {e}")
            return []

    def fetch_stream_url(self, code, name):
        try:
            payload = f"cctvCode={code}&name={name}"
            response = requests.post(self.stream_api_url, data=payload, headers=self.headers, timeout=10, verify=False)
            if response.status_code == 200:
                # Based on research, this might return a JSON snippet or a redirect.
                # Many GN streams use a custom player. We look for m3u8.
                text = response.text.strip()
                if "m3u8" in text:
                    return text
                
                try:
                    res_json = json.loads(text)
                    return res_json.get("url") or res_json.get("streamUrl")
                except:
                    pass
        except:
            pass
        return None
