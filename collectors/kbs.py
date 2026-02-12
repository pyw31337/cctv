import requests
import re
import urllib3
import concurrent.futures

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class KBSCollector:
    """
    KBS Disaster Portal Collector (d.kbs.co.kr).
    Pure requests-based approach using the discovered JSON API endpoint.
    
    API: POST /special/cctv/list  {area: '', disaster: '8'}
    Returns JSON with cctvList[] containing cctvId, lat, lng, name, url (HLS token).
    
    No Playwright/Chromium needed — eliminates ~200-400MB memory overhead.
    """
    def __init__(self):
        self.list_api_url = "https://d.kbs.co.kr/special/cctv/list"
        self.popup_api_url = "https://d.kbs.co.kr/special/cctv/cctvPopup"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://d.kbs.co.kr/special/cctv",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

    def fetch_data(self):
        print("[KBS] Fetching CCTV list via API (lightweight, no browser)...")
        
        try:
            # Step 1: Fetch CCTV list from JSON API
            resp = requests.post(
                self.list_api_url,
                data={"area": "", "disaster": "8"},
                headers=self.headers,
                timeout=30,
                verify=False
            )
            
            if resp.status_code != 200:
                print(f"[KBS] Failed to fetch list: {resp.status_code}")
                return []
            
            data = resp.json()
            cctv_list = data.get("cctvList", [])
            print(f"[KBS] API returned {len(cctv_list)} items.")
            
            if not cctv_list:
                return []
            
            # Step 2: Normalize and resolve stream URLs
            results = []
            for item in cctv_list:
                cctv_id = item.get("cctvId")
                if not cctv_id:
                    continue
                
                name = item.get("name", "Unknown")
                lat = float(item.get("lat", 0))
                lng = float(item.get("lng", 0))
                
                # The API provides a token URL directly
                token_url = item.get("url", "")
                
                # Resolve the token URL to get the final .m3u8 stream
                stream_url = None
                if token_url and token_url.startswith("http"):
                    stream_url = self._resolve_token_url(token_url)
                
                # Fallback: try popup method if token URL didn't work
                if not stream_url:
                    stream_url = self.resolve_stream_url(cctv_id)
                
                if stream_url:
                    results.append({
                        "id": f"KBS_{cctv_id}",
                        "original_id": str(cctv_id),
                        "name": name,
                        "lat": lat,
                        "lng": lng,
                        "url": stream_url,
                        "source": "KBS",
                        "status": "active"
                    })
            
            print(f"[KBS] Successfully collected {len(results)} playable streams.")
            return results

        except Exception as e:
            print(f"[KBS] Critical Error: {e}")
            return []

    def _resolve_token_url(self, token_url):
        """Resolves a KBS token URL to get the final .m3u8 stream URL."""
        try:
            get_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": "https://d.kbs.co.kr/special/cctv",
            }
            resp = requests.get(token_url, headers=get_headers, timeout=10, verify=False)
            if resp.status_code == 200:
                final_url = resp.text.strip()
                if final_url.startswith("http") and ".m3u8" in final_url:
                    return final_url
        except Exception:
            pass
        return None

    def resolve_stream_url(self, cctv_id):
        """
        Fallback: Resolves the final .m3u8 URL via the popup page.
        """
        try:
            popup_url = f"{self.popup_api_url}?type=LIVE&cctvId={cctv_id}"
            get_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": "https://d.kbs.co.kr/special/cctv",
            }
            
            resp = requests.get(popup_url, headers=get_headers, timeout=10, verify=False)
            if resp.status_code != 200:
                return None
            
            html = resp.text
            
            # Extract Token URL from hidden input
            match = re.search(r'id=["\']url["\'][^>]*value=["\']([^"\']+)["\']', html)
            if not match:
                match = re.search(r'value=["\']([^"\']+)["\'][^>]*id=["\']url["\']', html)
            
            if not match:
                return None
            
            token_api_url = match.group(1)
            return self._resolve_token_url(token_api_url)

        except Exception:
            return None

if __name__ == "__main__":
    collector = KBSCollector()
    data = collector.fetch_data()
    print(f"Collected {len(data)} items.")
    if data:
        print(f"Sample: {data[0]}")
