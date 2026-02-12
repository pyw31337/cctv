import requests
import re
import concurrent.futures
from bs4 import BeautifulSoup

class UlleungCollector:
    BASE_URL = "https://www.ulleung.go.kr/live/index.do"
    
    # Approximate coordinates for known locations
    LOCATIONS = {
        '독도': {'lat': 37.2429, 'lng': 131.8668, 'address': "경상북도 울릉군 울릉읍 독도리"},
        '독도전망대': {'lat': 37.4865, 'lng': 130.9068, 'address': "경상북도 울릉군 울릉읍 도동리 581-1"}, 
        '독도 동도': {'lat': 37.2398, 'lng': 131.8690, 'address': "경상북도 울릉군 울릉읍 독도리 1-96 (동도)"},
        '독도 서도': {'lat': 37.2415, 'lng': 131.8643, 'address': "경상북도 울릉군 울릉읍 독도리 1-96 (서도)"},
        '현포': {'lat': 37.5168, 'lng': 130.8306, 'address': "경상북도 울릉군 북면 현포리"},
        '내수전': {'lat': 37.5085, 'lng': 130.9329, 'address': "경상북도 울릉군 울릉읍 저동리"},
        '태하': {'lat': 37.4934, 'lng': 130.8037, 'address': "경상북도 울릉군 서면 태하리"},
        '석포': {'lat': 37.5310, 'lng': 130.9250, 'address': "경상북도 울릉군 북면 석포리"},
        '행남': {'lat': 37.4831, 'lng': 130.9161, 'address': "경상북도 울릉군 울릉읍 도동리 (행남해안산책로)"},
        '도동': {'lat': 37.4846, 'lng': 130.9079, 'address': "경상북도 울릉군 울릉읍 도동리"},
        '저동': {'lat': 37.4965, 'lng': 130.9167, 'address': "경상북도 울릉군 울릉읍 저동리"},
        '천부': {'lat': 37.5320, 'lng': 130.8756, 'address': "경상북도 울릉군 북면 천부리"},
        '나리': {'lat': 37.5212, 'lng': 130.8679, 'address': "경상북도 울릉군 북면 나리"},
        '남양': {'lat': 37.4690, 'lng': 130.8402, 'address': "경상북도 울릉군 서면 남양리"},
        '남서': {'lat': 37.4725, 'lng': 130.8176, 'address': "경상북도 울릉군 서면 남서리"},
        '사동': {'lat': 37.4619, 'lng': 130.8744, 'address': "경상북도 울릉군 울릉읍 사동리"},
        '죽도': {'lat': 37.5244, 'lng': 130.9388, 'address': "경상북도 울릉군 울릉읍 저동리 1-1 (죽도)"},
    }

    def fetch_data(self):
        print("Fetching Ulleungdo CCTV list...")
        try:
            resp = requests.get(f"{self.BASE_URL}?lnk_uid=43", timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"[Ulleung] Failed to fetch main page: {e}")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.select('a[href*="linkClickCnt.do"]')
        
        cameras = []
        seen_ids = set()
        
        # 1. Parse List
        for link in links:
            href = link.get('href')
            match = re.search(r'id=(\d+)', href)
            if match:
                link_id = match.group(1)
                name = link.get_text(strip=True)
                
                if link_id not in seen_ids:
                    seen_ids.add(link_id)
                    cameras.append((link_id, name))

        print(f"[Ulleung] Found {len(cameras)} cameras. Resolving streams...")
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(self.get_stream_info, cid, name): cid for cid, name in cameras}
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    results.append(res)

        print(f"[Ulleung] Successfully collected {len(results)} streams.")
        return results

    def get_stream_info(self, link_id, name):
        try:
            url = f"{self.BASE_URL}?lnk_uid={link_id}"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            video_source = soup.select_one('source[type="application/x-mpegurl"]')
            
            if video_source and video_source.get('src'):
                stream_url = video_source['src'].strip()
                if not stream_url.startswith('http'):
                    stream_url = f"https://www.ulleung.go.kr{stream_url}"
                
                # Coords & Address
                lat, lng = 37.484, 130.898 # Default Ulleungdo
                address = "경상북도 울릉군 울릉읍"
                for key, coord in self.LOCATIONS.items():
                    if key in name:
                        lat, lng = coord['lat'], coord['lng']
                        address = coord.get('address', address)
                        break
                
                return {
                    'structure_id': f"ULLEUNG_{link_id}", # Internal ID
                    'cctv_name': f"울릉군 {name}",
                    'lat': lat,
                    'lng': lng,
                    'url': stream_url,
                    'source': 'ULLEUNG',
                    'address': address
                }
        except Exception as e:
            print(f"[Ulleung] Error resolving {name}: {e}")
        return None
