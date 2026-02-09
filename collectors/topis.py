import os
import requests
import json
import concurrent.futures
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TopisCollector:
    """
    Seoul TOPIS (Transport Operation & Information Service) Collector.
    Scrapes data from the public map interface.
    """
    def __init__(self):
        self.list_url = "https://topis.seoul.go.kr/map/cctv/selectCctvList.do"
        self.info_url = "https://topis.seoul.go.kr/map/selectCctvInfo.do"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": "https://topis.seoul.go.kr/map/openCctvMap.do"
        }

    def fetch_data(self):
        print("[TOPIS] Fetching CCTV list via scraping...")
        try:
            # 1. Fetch the full list
            # Some servers use recordCountPerPage or different pageSize names. Let's try pageSize=1000
            list_payload = "pageIndex=1&pageSize=1000&cctvName="
            response = requests.post(self.list_url, data=list_payload, headers=self.headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                print(f"[TOPIS] Failed to fetch list: {response.status_code}")
                return []
            
            data = response.json()
            rows = data.get("rows", [])
            total_rows = data.get("TotalRows", len(rows))
            print(f"[TOPIS] TotalRows reported: {total_rows}. Rows fetched: {len(rows)}.")
            
            # If we only got 10 but total is 502, the pageSize might be capped or the parameter is wrong.
            # We'll try to fetch all 502 by iterating if needed, but let's first check if we can get more.
            if len(rows) < total_rows and len(rows) == 10:
                print("[TOPIS] Capped at 10 rows. Iterating through pages...")
                all_rows = []
                all_rows.extend(rows)
                for p in range(2, (total_rows // 10) + 2):
                    p_payload = f"pageIndex={p}&pageSize=10&cctvName="
                    p_resp = requests.post(self.list_url, data=p_payload, headers=self.headers, timeout=10, verify=False)
                    if p_resp.status_code == 200:
                        p_rows = p_resp.json().get("rows", [])
                        all_rows.extend(p_rows)
                        if len(all_rows) >= total_rows: break
                rows = all_rows
                print(f"[TOPIS] Total rows after iteration: {len(rows)}")

            print(f"[TOPIS] Fetching stream URLs for {len(rows)} CCTVs...")
            
            # 2. Fetch stream URLs concurrently
            full_data = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                future_to_row = {executor.submit(self.fetch_stream_url, row): row for row in rows}
                
                checked = 0
                for future in concurrent.futures.as_completed(future_to_row):
                    row = future_to_row[future]
                    try:
                        normalized_item = future.result()
                        if normalized_item:
                            full_data.append(normalized_item)
                    except Exception as exc:
                        print(f"[TOPIS] Error fetching stream for {row.get('camId')}: {exc}")
                    
                    checked += 1
                    if checked % 100 == 0:
                        print(f"[TOPIS] Progress: {checked}/{len(rows)} ({100*checked/len(rows):.1f}%)")

            print(f"[TOPIS] Successfully collected {len(full_data)} streams.")
            return full_data

        except Exception as e:
            print(f"[TOPIS] Error in fetch_data: {e}")
            return []

    def fetch_stream_url(self, row):
        cam_id = row.get("camId")
        if not cam_id:
            return None
            
        info_payload = f"camId={cam_id}&cctvSourceCd=HP"
        try:
            response = requests.post(self.info_url, data=info_payload, headers=self.headers, timeout=10, verify=False)
            if response.status_code == 200:
                data = response.json()
                rows = data.get("rows", [])
                if not rows:
                    return None
                
                info = rows[0]
                # Try hlsUrl first, then remark5
                hls_url = info.get("hlsUrl") or info.get("remark5")
                
                if hls_url:
                    # Resolve any http to https if possible
                    if hls_url.startswith("http://"):
                        hls_url = hls_url.replace("http://", "https://")
                        
                    return {
                        "id": f"TOPIS_{cam_id}",
                        "original_id": str(cam_id),
                        "name": row.get("camName", "Unknown").strip(),
                        "lat": float(row.get("lat", 0)),
                        "lng": float(row.get("lng", 0)),
                        "url": hls_url,
                        "source": "TOPIS",
                        "status": "active"
                    }
        except Exception:
            pass
            
        return None
