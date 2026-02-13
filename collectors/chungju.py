import requests
from bs4 import BeautifulSoup
import re
import json

class ChungjuCollector:
    """
    Chungju ITS CCTV Collector.
    Scrapes data from https://its.chungju.go.kr/traffic/cctv.do
    """
    def __init__(self):
        self.url = "https://its.chungju.go.kr/traffic/cctv.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_data(self):
        print("[Chungju] Fetching CCTV page...")
        try:
            response = requests.get(self.url, headers=self.headers, timeout=15, verify=False)
            
            if response.status_code != 200:
                print(f"[Chungju] Failed to fetch page: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            links = soup.find_all('a', href=re.compile(r'showCctv'))
            
            if not links:
                print("[Chungju] No CCTV links found")
                return []
                
            cctvs = self.parse_links(links)
            print(f"[Chungju] Successfully collected {len(cctvs)} streams.")
            return cctvs

        except Exception as e:
            print(f"[Chungju] Error in fetch_data: {e}")
            return []

    def parse_links(self, links):
        parsed = []
        # Pattern: showCctv('33','33.탄금공원삼거리','rtmp://...','36.9861322','127.9039782',',N','CCTVLIST','https://...m3u8')
        pattern = re.compile(r"showCctv\('([^']+)','([^']+)','([^']+)','([^']+)','([^']+)','[^']*','[^']*','([^']+)'\)")
        
        for link in links:
            try:
                href = link.get('href', '')
                match = pattern.search(href)
                if not match:
                    continue
                    
                cctv_id, name, rtmp_url, lat, lng, m3u8_url = match.groups()
                
                # Cleanup name (remove leading ID if present: "33.탄금공원삼거리" -> "탄금공원삼거리")
                clean_name = name.split('.', 1)[-1] if '.' in name else name

                # Normalized Object
                cctv = {
                    "id": f"CHUNGJU_{cctv_id}",
                    "original_id": str(cctv_id),
                    "name": clean_name,
                    "lat": float(lat),
                    "lng": float(lng),
                    "url": m3u8_url,
                    "source": "CHUNGJU",
                    "status": "active"
                }
                parsed.append(cctv)
            except Exception as e:
                print(f"[Chungju] Error parsing link: {e}")
                continue
                
        return parsed
