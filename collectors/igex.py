import requests
import urllib3
import re
from bs4 import BeautifulSoup

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class IGEXCollector:
    """
    Incheon-Gimpo Expressway (IGEX) Collector.
    Fetches CCTV data from igex.co.kr.
    """
    def __init__(self):
        self.url = "http://www.igex.co.kr/html/traffic/traffic01.html"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "http://www.igex.co.kr/"
        }

    def fetch_data(self):
        print("[IGEX] Fetching CCTV list from website...")
        try:
            response = requests.get(self.url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                print(f"[IGEX] Failed to fetch page: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            select = soup.find('select', id='cctv_select')
            if not select:
                print("[IGEX] Could not find cctv_select in page.")
                return []

            options = select.find_all('option')
            normalized_data = []
            
            # Static coordinates mapping if possible, or leave 0.0
            # Since IGEX doesn't provide lat/lng in the select, 
            # we might need to find a source with coordinates later or keep as 0.0
            
            for opt in options:
                name = opt.text.strip()
                hls_url = opt.get('value_hls')
                
                if not hls_url:
                    continue
                
                # Generate a unique ID based on the stream name in the URL
                # Example: http://58.232.33.232:1935/live/CTN0101_l.stream/playlist.m3u8 -> CTN0101
                match = re.search(r'/(CT[NS]\d+)', hls_url)
                stream_id = match.group(1) if match else h = hashlib.md5(name.encode()).hexdigest()[:8]
                
                normalized_data.append({
                    "id": f"IGEX_{stream_id}",
                    "original_id": stream_id,
                    "name": f"[인천김포고속도로] {name}",
                    "lat": 0.0,
                    "lng": 0.0,
                    "url": hls_url,
                    "source": "IGEX",
                    "status": "active",
                    "tags": ["highway", "igex"]
                })

            print(f"[IGEX] Successfully found {len(normalized_data)} streams.")
            return normalized_data

        except Exception as e:
            print(f"[IGEX] Error in fetch_data: {e}")
            return []

if __name__ == "__main__":
    import hashlib # Needed for fallback
    collector = IGEXCollector()
    data = collector.fetch_data()
    for item in data[:3]:
        print(f"Sample: {item['name']} -> {item['url']}")
