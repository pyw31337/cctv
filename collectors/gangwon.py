import requests
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GangwonCollector:
    """
    Gangwon Province Collector (Gangneung ITS).
    Fetches CCTV data from the Gangneung ITS public endpoints.
    
    Gangneung uses Genetec GWP (Gateway Web Player) with MSE/WebSocket streaming.
    Since there's no HLS endpoint, we resolve each camera's UUID (camUrl) from
    the ITS API during collection, then use a local GWP player page for playback:
      gangneung_player.html?camUrl={uuid}
    """
    def __init__(self):
        self.list_url = "https://its.gn.go.kr/main/selectCctvList"
        self.cam_url_api = "https://its.gn.go.kr/popup/getCctvCamUrl"
        self.player_base = "gangneung_player.html?camUrl="
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://its.gn.go.kr/main",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }

    def fetch_data(self):
        print("[GANGWON] Fetching Gangneung CCTV list...")
        try:
            # Step 1: Get CCTV list
            payload = "layerGubn=CCTV"
            response = requests.post(self.list_url, headers=self.headers, data=payload, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[GANGWON] Failed to fetch list: {response.status_code}")
                return []

            data = response.json()
            items = data.get("rows", [])
            print(f"[GANGWON] Found {len(items)} CCTVs in Gangneung.")

            # Step 2: Resolve camUrl for each CCTV and build player URLs
            normalized_data = []
            active_count = 0
            
            for item in items:
                cctv_id = item.get("code")
                name = item.get("name") or "Unknown"
                lat = item.get("wgs84Y")
                lng = item.get("wgs84X")

                if not cctv_id:
                    continue

                # Resolve the camera's Genetec entity UUID
                cam_url = self._resolve_cam_url(cctv_id)
                
                if cam_url:
                    # Build player URL with pre-resolved camUrl
                    url = f"{self.player_base}{cam_url}"
                    active_count += 1
                else:
                    url = ""
                
                normalized_data.append({
                    "id": f"GANGWON_GN_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": f"[강릉] {name.strip()}",
                    "lat": float(lat) if lat else 0.0,
                    "lng": float(lng) if lng else 0.0,
                    "url": url,
                    "source": "GANGWON",
                    "status": "active" if url else "inactive"
                })

            print(f"[GANGWON] Successfully normalized {active_count} playable streams.")
            return normalized_data

        except Exception as e:
            print(f"[GANGWON] Error in fetch_data: {e}")
            return []

    def _resolve_cam_url(self, cctv_code):
        """Resolve a CCTV code to its Genetec entity UUID via the ITS API."""
        try:
            resp = requests.post(
                self.cam_url_api,
                data=f"cctvId={cctv_code}",
                headers=self.headers,
                timeout=5,
                verify=False
            )
            if resp.status_code == 200:
                data = resp.json()
                cam_url = data.get("camUrl", "")
                # Valid UUID format means the camera is online
                if cam_url and len(cam_url) > 10:
                    return cam_url
        except Exception:
            pass
        return None
