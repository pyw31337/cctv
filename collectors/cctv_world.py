import requests
import xml.etree.ElementTree as ET
import concurrent.futures
import re
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class CCTVWorldCollector:
    """
    CCTV World Collector (cctv-world.kr).
    Parses the sitemap to find all CCTV detail pages.
    Scrapes each page to find the 'View' button which links to the actual source.
    Useful for finding:
    1. KBS cameras not in the main list.
    2. YouTube streams.
    3. Other government sources (National Parks, etc).
    
    NOTE: This site does not provide coordinates. Collected items will have lat=0, lng=0
    unless matched with existing data.
    """
    def __init__(self):
        self.sitemap_url = "https://www.cctv-world.kr/sitemap.xml"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    def fetch_data(self):
        print("[CCTVWorld] Fetching sitemap...")
        try:
            # 1. Fetch Sitemap
            response = requests.get(self.sitemap_url, headers=self.headers, timeout=10, verify=False)
            if response.status_code != 200:
                print(f"[CCTVWorld] Failed to fetch sitemap: {response.status_code}")
                return []

            # 2. Parse Sitemap
            # XML namespace is usually http://www.sitemaps.org/schemas/sitemap/0.9
            root = ET.fromstring(response.content)
            namespace = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            
            urls = []
            for url in root.findall('ns:url', namespace):
                loc = url.find('ns:loc', namespace).text
                if '/cctv/' in loc and loc != "https://www.cctv-world.kr/cctv/":
                    # Exclude category pages if possible. 
                    # Detail pages usually have 3 segments: /cctv/category/name
                    parts = loc.replace("https://www.cctv-world.kr", "").split("/")
                    if len(parts) >= 4: # /cctv/seoul/gangnamdaero -> 4 parts (empty, cctv, seoul, name)
                        urls.append(loc)
            
            print(f"[CCTVWorld] Found {len(urls)} detail pages in sitemap. Scraping concurrently...")
            
            # 3. Scrape Detail Pages
            cctv_data = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                future_to_url = {executor.submit(self.scrape_page, url): url for url in urls}
                
                completed = 0
                for future in concurrent.futures.as_completed(future_to_url):
                    item = future.result()
                    if item:
                        cctv_data.append(item)
                    
                    completed += 1
                    if completed % 20 == 0:
                        print(f"[CCTVWorld] Progress: {completed}/{len(urls)}")
            
            print(f"[CCTVWorld] Collected {len(cctv_data)} valid items.")
            return cctv_data

        except Exception as e:
            print(f"[CCTVWorld] Critical Error: {e}")
            return []

    def scrape_page(self, url):
        try:
            resp = requests.get(url, headers=self.headers, timeout=10, verify=False)
            if resp.status_code != 200:
                return None
            
            html = resp.text
            
            # 1. Extract Name (Title)
            # <title>강남대교 실시간 라이브캠 CCTV</title>
            name_match = re.search(r'<title>(.*?) CCTV</title>', html)
            name = name_match.group(1).replace("실시간", "").replace("라이브캠", "").strip() if name_match else "Unknown"
            
            # 2. Extract "View" Link
            # Pattern: href="https://d.kbs.co.kr..." class="...bg-[#007BFF]..."
            # Or just look for specific domains in hrefs that look like streams
            
            # KBS
            # href="https://d.kbs.co.kr/special/cctvShare?cctvId=9999"
            kbs_match = re.search(r'href="(https://d\.kbs\.co\.kr/special/cctvShare\?cctvId=(\d+))"', html)
            if kbs_match:
                cctv_id = kbs_match.group(2)
                return {
                    "id": f"KBS_{cctv_id}",
                    "original_id": cctv_id,
                    "name": name,
                    "lat": 0.0, # Unknown
                    "lng": 0.0, # Unknown
                    "source": "KBS",
                    "status": "active",
                    "page_url": url,
                    # We don't resolve the stream here, we let the main script merge it 
                    # with KBSCollector data which has the resolver.
                    # Or if it's new, the KBSCollector logic in main script should handle it.
                    "is_candidate": True 
                }
            
            # YouTube
            # href="https://www.youtube.com/watch?v=..." or youtu.be
            yt_match = re.search(r'href="(https://(www\.)?youtube\.com/watch\?v=[^"]+|https://youtu\.be/[^"]+)"', html)
            if yt_match:
                yt_url = yt_match.group(1)
                slug = url.split("/")[-1]
                return {
                    "id": f"CCTVWORLD_YT_{slug}",
                    "name": name,
                    "lat": 0.0,
                    "lng": 0.0,
                    "source": "YOUTUBE",
                    "url": yt_url,
                    "status": "active",
                    "page_url": url
                }
            
            # National Parks (KNPS)
            if "knps.or.kr" in html:
                 slug = url.split("/")[-1]
                 return {
                    "id": f"CCTVWORLD_KNPS_{slug}",
                    "name": name,
                    "lat": 0.0,
                    "lng": 0.0,
                    "source": "KNPS",
                    "url": url, # Point to page url as we can't easily extract activex/video
                    "status": "manual_check",
                    "page_url": url
                }

            return None

        except Exception:
            return None

if __name__ == "__main__":
    c = CCTVWorldCollector()
    data = c.fetch_data()
    print(f"Found {len(data)}")
    for d in data[:5]:
        print(d)
