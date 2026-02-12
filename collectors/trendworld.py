import requests
import re
import random
import time

class TrendWorldCollector:
    def __init__(self):
        self.base_url = "https://www.trendworld.kr/b/jeju_online_cctv"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Approximate coordinates for known locations
        self.location_map = {
            '백록담': (33.3617, 126.5292),
            '왕관릉': (33.3617, 126.5292), # Close to Baengnokdam
            '윗세오름': (33.3572, 126.5113),
            '어승생악': (33.3917, 126.4950),
            '1100고지': (33.3578, 126.4623),
            '성산일출봉': (33.4580, 126.9425),
            '성산': (33.4580, 126.9425),
            '용두암': (33.5163, 126.5120),
            '협재': (33.3938, 126.2396),
            '함덕': (33.5434, 126.6688),
            '중문': (33.2450, 126.4124),
            '천지연': (33.2460, 126.5590),
            '정방폭포': (33.2448, 126.5718),
            '산방산': (33.2415, 126.3142),
            '마라도': (33.1178, 126.2678),
            '우도': (33.5194, 126.9510),
            '비양도': (33.4077, 126.2305),
            '추자도': (33.9470, 126.3310),
            '가파도': (33.1708, 126.2715),
            '섭지코지': (33.4243, 126.9311),
            '송악산': (33.2050, 126.2890),
            '외돌개': (33.2380, 126.5450),
            '이호테우': (33.4975, 126.4530),
            '곽지': (33.4470, 126.3050),
            '표선': (33.3260, 126.8310),
            '세화': (33.5250, 126.8550),
            '월정리': (33.5550, 126.7960),
            '김녕': (33.5580, 126.7590),
            '애월': (33.4650, 126.3200),
            '한림': (33.4150, 126.2650),
            '대정': (33.2150, 126.2550),
            '안덕': (33.2500, 126.3300),
            '남원': (33.2790, 126.7190),
            '구좌': (33.5300, 126.8500),
            '조천': (33.5350, 126.6350),
            '한경': (33.3500, 126.1700),
        }

    def collect_data(self):
        print("Collecting TrendWorld Jeju CCTV data...")
        cctv_list = []
        
        # Iterate through pages 1 to 13
        # Use concurrent futures for pages if needed, but serial is safer for rate limiting
        # Let's keep it serial but adding sleep
        for page in range(1, 14):
            try:
                page_url = f"{self.base_url}?page={page}"
                print(f"[TrendWorld] Fetching list page {page}...")
                response = requests.get(page_url, headers=self.headers, timeout=10)
                if response.status_code != 200:
                    print(f"Failed to fetch page {page}: {response.status_code}")
                    continue
                
                html = response.text
                
                # regex to find list items:
                # <td class="mw_basic_list_subject"> ... <a href="...">...</a>
                # simplify regex: look for headers or links strictly within list context?
                # The page source has: 
                # <td class="mw_basic_list_subject">
                #    <a href="https://www.trendworld.kr/b/jeju_online_cctv-15" ...> [한라산] ... </a>
                # </td>
                
                # We can find all links that match pattern /b/jeju_online_cctv-[0-9]+
                # But that might catch prev/next buttons.
                # Let's search by class name if possible using regex is tricky.
                # Pattern: <td class="mw_basic_list_subject">.*?<a href="([^"]+)".*?>\s*(.*?)\s*</a>
                
                # Refined Regex to handle variations in class attribute and capture title
                matches = re.finditer(r'<td class="mw_basic_list_subject[^"]*">.*?<a href="([^"]+)".*?>(.*?)</a>', html, re.DOTALL)
                
                count = 0 
                for match in matches:
                    try:
                        detail_url = match.group(1)
                        raw_title = match.group(2)
                        
                        # Clean URL
                        if not detail_url.startswith('http'):
                            # remove leading dots if any
                            detail_url = "https://www.trendworld.kr" + detail_url.lstrip('.')
                        else:
                            # Sometimes it might be absolute but http
                            detail_url = detail_url.replace("http://", "https://")

                        # Clean Title (remove tags inside title like <span...>)
                        cleaned_title_text = re.sub(r'<[^>]+>', '', raw_title)
                        
                        clean_title = cleaned_title_text
                        clean_title = re.sub(r'\[.*?\]', '', clean_title) 
                        clean_title = clean_title.replace('제주도', '').replace('제주', '').replace('서귀포', '')
                        clean_title = clean_title.replace('실시간', '').replace('CCTV', '').replace('보기', '')
                        clean_title = clean_title.strip()
                        
                        if not clean_title:
                            continue

                        # Fetch Detail Info
                        stream_url, player_url = self.__get_stream_info(detail_url)
                        
                        if stream_url:
                            lat, lng = self.__estimate_coords(clean_title, page)
                            
                            cctv_item = {
                                "id": f"TRENDWORLD_{re.sub(r'[^a-zA-Z0-9]', '', clean_title)}_{page}", 
                                "name": clean_title,
                                "lat": lat,
                                "lng": lng,
                                "url": stream_url,
                                "source": "TRENDWORLD", 
                                "status": "active",
                                "backup_urls": [player_url] if player_url else []
                            }
                            cctv_list.append(cctv_item)
                            print(f"[TrendWorld] Found: {clean_title}")
                            count += 1
                            
                    except Exception as e:
                        print(f"Error parsing item: {e}")
                        continue
                
                if count == 0:
                    # Fallback regex if class name changed or matched nothing
                    # Just find links: /b/jeju_online_cctv-[0-9]+
                    pass
                    
                time.sleep(0.5) # Courtesy sleep
                        
            except Exception as e:
                print(f"Error processing page {page}: {e}")
                
        return cctv_list

    def __get_stream_info(self, detail_url):
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=5)
            if response.status_code != 200:
                return None, None
            
            html = response.text
            
            # Regex for player link
            # look for http://cctv.trendworld.kr/cctv/...
            player_match = re.search(r'href=["\'](http://cctv\.trendworld\.kr/cctv/[^"\']+\.php)["\']', html)
            if not player_match:
                return None, None
                
            player_url = player_match.group(1)
            
            # Fetch Player Page
            p_response = requests.get(player_url, headers=self.headers, timeout=5)
            if p_response.status_code != 200:
                return None, player_url
            
            p_html = p_response.text
            
            # Extract .m3u8
            m3u8_match = re.search(r'src=["\'](http[^"\']+\.m3u8)["\']', p_html)
            if m3u8_match:
                return m3u8_match.group(1), player_url
                
            return None, player_url
            
        except Exception as e:
            return None, None

    def __estimate_coords(self, title, page_seed):
        for key, coords in self.location_map.items():
            if key in title:
                lat_jitter = (random.random() - 0.5) * 0.005
                lng_jitter = (random.random() - 0.5) * 0.005
                return coords[0] + lat_jitter, coords[1] + lng_jitter
        
        lat = 33.4996 + ((random.random() - 0.5) * 0.1)
        lng = 126.5312 + ((random.random() - 0.5) * 0.1)
        return lat, lng
