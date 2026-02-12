import requests
import re
import urllib3
import concurrent.futures
from playwright.sync_api import sync_playwright

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class KBSCollector:
    """
    KBS Disaster Portal Collector (d.kbs.co.kr).
    Hybrid Approach:
    1. Playwright: Loads the main page to extraction the CCTV list from the DOM/JS (bypassing complex API protections).
    2. Requests: rapid, lightweight resolution of stream tokens.
    """
    def __init__(self):
        self.target_url = "https://d.kbs.co.kr/special/cctv"
        self.popup_api_url = "https://d.kbs.co.kr/special/cctv/cctvPopup"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://d.kbs.co.kr/special/cctv",
        }

    def fetch_data(self):
        print("[KBS] Fetching CCTV list via Playwright (Headless)...")
        cctv_list = []
        
        try:
            with sync_playwright() as p:
                # Launch lightweight browser instance
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Block heavy resources to save memory
                page.route("**/*", lambda route: route.abort() 
                           if route.request.resource_type in ["image", "media", "font", "stylesheet"] 
                           else route.continue_())
                
                try:
                    page.goto(self.target_url, timeout=30000, wait_until="domcontentloaded")
                    
                    # Wait for the list to be populated (checking for markers or list items)
                    # The subagent showed .cctvList elements
                    try:
                        page.wait_for_selector(".cctvList a", timeout=10000)
                    except:
                        print("[KBS] Warning: Timeout waiting for .cctvList, attempting extraction anyway.")

                    # Extract data from DOM 
                    # We extract 'onclick' attributes which contain the ID and coordinates
                    # onclick="cctvPopOpen(14373, 37.524, 126.936)"
                    items = page.evaluate("""() => {
                        const links = Array.from(document.querySelectorAll('.cctvList a'));
                        return links.map(a => {
                            const onclick = a.getAttribute('onclick') || '';
                            const text = a.innerText.trim();
                            // Parse onclick for ID, Lat, Lng
                            // Format: cctvPopOpen(9952, 37.752, 128.891)
                            const match = onclick.match(/cctvPopOpen\\s*\\(\\s*(\\d+)\\s*,\\s*([\\d.]+)\\s*,\\s*([\\d.]+)/);
                            if (match) {
                                return {
                                    id: match[1],
                                    lat: match[2],
                                    lng: match[3],
                                    name: text
                                };
                            }
                            return null;
                        }).filter(i => i !== null);
                    }""")
                    
                    cctv_list = items
                    print(f"[KBS] Extracted {len(cctv_list)} items from DOM.")
                    
                except Exception as e:
                    print(f"[KBS] Browser Error: {e}")
                finally:
                    browser.close()

            # Normalize Data
            normalized_list = []
            for item in cctv_list:
                normalized_list.append({
                    "id": f"KBS_{item['id']}",
                    "original_id": str(item['id']),
                    "name": item['name'] if item['name'] else "Unknown",
                    "lat": float(item['lat']),
                    "lng": float(item['lng']),
                    "source": "KBS",
                    "status": "active"
                })

            if not normalized_list:
                return []

            print(f"[KBS] Resolving streams for {len(normalized_list)} cameras...")

            # Concurrent Stream Resolution using Requests (Lightweight)
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                future_to_cctv = {executor.submit(self.resolve_stream_url, item['original_id']): item for item in normalized_list}
                
                completed = 0
                for future in concurrent.futures.as_completed(future_to_cctv):
                    item = future_to_cctv[future]
                    try:
                        stream_url = future.result()
                        if stream_url:
                            item['url'] = stream_url
                            results.append(item)
                    except:
                        pass
                    
                    completed += 1
                    if completed % 50 == 0:
                        print(f"[KBS] Progress: {completed}/{len(normalized_list)}")

            print(f"[KBS] Successfully collected {len(results)} playable streams.")
            return results

        except Exception as e:
            print(f"[KBS] Critical Error in Hybrid Fetch: {e}")
            return []

    def resolve_stream_url(self, cctv_id):
        """
        Resolves the final .m3u8 URL for a given KBS CCTV ID.
        """
        try:
            # Step A: Get Popup HTML
            popup_url = f"{self.popup_api_url}?type=LIVE&cctvId={cctv_id}"
            get_headers = self.headers.copy()
            get_headers.pop("Content-Type", None)
            
            resp = requests.get(popup_url, headers=get_headers, timeout=10, verify=False)
            if resp.status_code != 200:
                return None
            
            html = resp.text
            
            # Step B: Extract Token URL
            # Look for id="url" value="..."
            match = re.search(r'id=["\']url["\'][^>]*value=["\']([^"\']+)["\']', html)
            if not match:
                match = re.search(r'value=["\']([^"\']+)["\'][^>]*id=["\']url["\']', html)
            
            if not match:
                return None
            
            token_api_url = match.group(1)
            
            # Step C: Get Final Stream URL
            resp_stream = requests.get(token_api_url, headers=get_headers, timeout=10, verify=False)
            
            if resp_stream.status_code == 200:
                final_url = resp_stream.text.strip()
                if final_url.startswith("http") and ".m3u8" in final_url:
                    return final_url
            
            return None

        except Exception:
            return None

if __name__ == "__main__":
    collector = KBSCollector()
    data = collector.fetch_data()
    print(f"Collected {len(data)} items.")
    if data:
        print(f"Sample: {data[0]}")
