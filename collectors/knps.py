import requests
from bs4 import BeautifulSoup
import re
import json
import concurrent.futures

class KNPSCollector:
    """
    KNPS (Korea National Park Service) CCTV Collector.
    Crawls detail pages to extract live stream URLs.
    """
    def __init__(self):
        self.base_url = "https://m.knps.or.kr"
        self.list_url = f"{self.base_url}/main/menuctrl.do?menuNo=10"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.base_url
        }
        # Pre-defined mapping from research (id -> detail_path)
        self.id_map = {
            "1": "/live/bukhan.do",
            "2": "/live/seorak.do",
            "3": "/live/sobaek.do",
            "4": "/live/jiri.do",
            "5": "/live/cctv5.do", # 한려해상
            "6": "/live/cctv6.do", # 태백산
            "7": "/live/cctv7.do", # 지리산장터목
            "8": "/live/cctv8.do", # 설악산 중청
            "9": "/live/cctv9.do", # 주왕산
            "10": "/live/cctv10.do", # 덕유산
            "11": "/live/cctv11.do", # 오대산
            "12": "/live/cctv12.do", # 다도해
            "13": "/live/cctv13.do", # 월악산
            "14": "/live/cctv14.do", # 북한산 사패산
            "15": "/live/cctv15.do", # 무등산
            "16": "/live/cctv16.do", # 계룡산
            "17": "/live/cctv17.do", # 치악산
            "18": "/live/cctv18.do", # 변산반도
            "21": "/live/cctv21.do", # 태안해안
        }

    def fetch_data(self):
        print("[KNPS] Fetching CCTV list page...")
        try:
            response = requests.get(self.list_url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                print(f"[KNPS] Failed to fetch list: {response.status_code}")
                return []
            
            # Use BS4 but manually parse onclick for robustness against malformed tags
            soup = BeautifulSoup(response.text, 'html.parser')
            items = soup.find_all('li')
            
            targets = []
            for item in items:
                onclick = item.get('onclick', '')
                if 'openCCTV' not in onclick:
                    continue
                    
                match = re.search(r"openCCTV\('(\d+)'", onclick)
                if match:
                    cctv_id = match.group(1)
                    # Use a custom text extraction to avoid joining sibling li text if parsed incorrectly
                    # Get only the immediate text content of this li
                    name = "".join([t for t in item.find_all(text=True, recursive=False)]).strip()
                    if not name:
                        name = item.get_text(strip=True) # Fallback
                        
                    if cctv_id in self.id_map:
                        targets.append({
                            "id": cctv_id,
                            "name": name,
                            "path": self.id_map[cctv_id]
                        })

            print(f"[KNPS] Found {len(targets)} potential cameras. Fetching detail pages...")
            
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(self.fetch_detail, target) for target in targets]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res:
                        results.append(res)
            
            print(f"[KNPS] Successfully collected {len(results)} streams.")
            return results

        except Exception as e:
            print(f"[KNPS] Error in fetch_data: {e}")
            return []

    def fetch_detail(self, target):
        try:
            url = f"{self.base_url}{target['path']}"
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return None
                
            # Look for HLS URL in script or video tag
            # Pattern: http://live.knps.or.kr:1935/live/cctv_1.stream/playlist.m3u8
            # or: https://live.knps.or.kr/cctv/hls/bukhan.m3u8
            match = re.search(r'https?://[^\s"\']+\.m3u8', resp.text)
            if not match:
                # Try relative or other patterns if needed
                return None
                
            stream_url = match.group(0)
            
            # Geocoding might be needed as Lng/Lat are not in HTML
            # I'll return with 0,0 and let GeocodeHelper handle it in main
            
            return {
                "id": f"KNPS_{target['id']}",
                "original_id": target["id"],
                "name": target["name"],
                "lat": 0.0,
                "lng": 0.0,
                "url": stream_url,
                "source": "KNPS",
                "status": "active"
            }
        except Exception as e:
            print(f"[KNPS] Error fetching detail for {target['name']}: {e}")
            return None
