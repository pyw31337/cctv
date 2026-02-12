import requests
import re
from bs4 import BeautifulSoup
import concurrent.futures

BASE_URL = "https://www.ulleung.go.kr/live/index.do"

def get_stream_info(link_id, name):
    try:
        url = f"{BASE_URL}?lnk_uid={link_id}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        video_source = soup.select_one('source[type="application/x-mpegurl"]')
        
        if video_source and video_source.get('src'):
            stream_url = video_source['src'].strip()
            if not stream_url.startswith('http'):
                stream_url = f"https://www.ulleung.go.kr{stream_url}"
            return {
                'id': f"ULLEUNG_{link_id}",
                'name': name.strip(),
                'url': stream_url
            }
    except Exception as e:
        print(f"Error fetching {name} ({link_id}): {e}")
    return None

def main():
    print("Fetching camera list...")
    resp = requests.get(f"{BASE_URL}?lnk_uid=43", timeout=10)
    html = resp.text
    
    # Simple regex to find IDs and Names
    # <a href="/link/linkClickCnt.do?id=43..." ...><span>Name</span></a>
    
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.select('a[href*="linkClickCnt.do"]')
    
    cameras = []
    seen_ids = set()
    
    for link in links:
        href = link.get('href')
        match = re.search(r'id=(\d+)', href)
        if match:
            link_id = match.group(1)
            name = link.get_text(strip=True)
            
            if link_id not in seen_ids:
                seen_ids.add(link_id)
                cameras.append((link_id, name))
                print(f"Found camera: {name} (ID: {link_id})")
    
    print(f"\nFetching streams for {len(cameras)} cameras concurrently...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(get_stream_info, cid, name): cid for cid, name in cameras}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
                print(f"Collected: {res['name']} -> {res['url']}")

    print(f"\nTotal collected: {len(results)}")

if __name__ == "__main__":
    main()
