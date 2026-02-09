import requests
import re
import concurrent.futures
import time

class GitsCollector:
    """
    Gyeonggi Intelligent Transportation System (GITS) Collector.
    Scrapes data from https://gits.gg.go.kr/web/map/webLoadCCTVData.do
    and extracts stream URLs from the popup page.
    """
    def __init__(self):
        self.list_url = "https://gits.gg.go.kr/web/map/webLoadCCTVData.do"
        self.popup_base_url = "https://gits.gg.go.kr/web/popup/webCctvPopup.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://gits.gg.go.kr/web/map/webMap.do?opt=3"
        }

    def fetch_data(self):
        print("[GITS] Fetching CCTV list...")
        try:
            response = requests.get(self.list_url, headers=self.headers, timeout=30)
            if response.status_code != 200:
                print(f"[GITS] Failed to fetch list: {response.status_code}")
                return []
            
            raw_data = response.text
            cctvs = self.parse_cctv_list(raw_data)
            print(f"[GITS] Found {len(cctvs)} CCTVs. Fetching stream URLs...")
            
            # Fetch stream URLs concurrently
            full_data = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                # Map cctv objects to futures
                future_to_cctv = {executor.submit(self.fetch_stream_url, cctv): cctv for cctv in cctvs}
                
                checked = 0
                for future in concurrent.futures.as_completed(future_to_cctv):
                    cctv = future_to_cctv[future]
                    try:
                        stream_url = future.result()
                        if stream_url:
                            cctv['url'] = stream_url
                            full_data.append(cctv)
                    except Exception as exc:
                        print(f"[GITS] Error fetching stream for {cctv['id']}: {exc}")
                    
                    checked += 1
                    if checked % 100 == 0:
                        print(f"[GITS] Progress: {checked}/{len(cctvs)} ({100*checked/len(cctvs):.1f}%)")

            print(f"[GITS] Successfully collected {len(full_data)} streams.")
            return full_data

        except Exception as e:
            print(f"[GITS] Error in fetch_data: {e}")
            return []

    def parse_cctv_list(self, data):
        # Format: item1@item2@...
        # Item: id/name/lng/lat/code
        items = data.strip().split('@')
        parsed = []
        for item in items:
            parts = item.split('/')
            if len(parts) >= 4:
                try:
                    cctv_id = parts[0]
                    name = parts[1]
                    lng = float(parts[2])
                    lat = float(parts[3])
                    
                    # Store as normalized object
                    cctv = {
                        "id": f"GITS_{cctv_id}",
                        "original_id": cctv_id,
                        "name": name,
                        "lat": lat,
                        "lng": lng,
                        "source": "GITS",
                        "status": "active"
                    }
                    parsed.append(cctv)
                except ValueError:
                    continue
        return parsed

    def fetch_stream_url(self, cctv):
        cctv_id = cctv['original_id']
        url = f"{self.popup_base_url}?cctvId={cctv_id}"
        
        try:
            # Small delay to be polite? With 50 workers, maybe not needed if server is robust.
            # time.sleep(0.05) 
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                html = response.text
                
                # Pattern 1: iPhone videoUrl (Often HLS or MP4)
                # var videoUrl = "http://gitsview.gg.go.kr/..."
                match_iphone = re.search(r'var videoUrl = "(http[^"]+)"', html)
                if match_iphone:
                    vid_url = match_iphone.group(1)
                    return vid_url.replace("http://", "https://")

                # Pattern 2: $.get HLS token
                # $.get("//gitsview.gg.go.kr/...!hls"
                match_hls = re.search(r'\$\.get\("([^"]+!hls)"', html)
                if match_hls:
                    hls_token_url = match_hls.group(1)
                    if hls_token_url.startswith("//"):
                        hls_token_url = "https:" + hls_token_url
                    
                    # Resolve the redirect to get the final .m3u8 or .mp4
                    try:
                        # Use head request to follow redirect
                        resp_head = requests.head(hls_token_url, headers=self.headers, allow_redirects=True, timeout=5)
                        if resp_head.status_code == 200:
                            return resp_head.url
                    except:
                        pass
                    
                    # Fallback to token URL if resolution fails
                    return hls_token_url

                # Pattern 3: <video src="...">
                match_video = re.search(r'<video src="([^"]+)"', html)
                if match_video:
                    return match_video.group(1)

        except Exception:
            pass
        
        return None
