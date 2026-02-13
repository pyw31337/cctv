import json
import time
import re
import subprocess
import random
import os
import sys

DATA_FILE = "cctv_data.json"
UserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def load_data():
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found.")
        sys.exit(1)
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, DATA_FILE)

def fetch_content(url):
    try:
        cmd = [
            "curl", "-s", "-k", "-L",
            "--max-time", "15",
            "-H", f"User-Agent: {UserAgent}",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""

def main():
    print("=== Suwon SAFE Collector (Boringly Safe Mode) ===")
    data = load_data()
    
    suwon_indices = []
    for i, item in enumerate(data):
        name = item.get('name', '')
        url = item.get('url', '')
        # Only target items that are Suwon and still use the JSP/Popup wrapper
        if ('수원' in name or 'suwon' in url) and ('openDataCctvStream.jsp' in url or 'cctvPopup.do' in url):
            suwon_indices.append(i)
            
    if not suwon_indices:
        print("No Suwon popup targets found. Everything might already be secured.")
        return

    print(f"Found {len(suwon_indices)} Suwon targets. Processing SEQUENTIALLY with 5s delay.")
    
    modified_count = 0
    for idx, target_idx in enumerate(suwon_indices):
        item = data[target_idx]
        name = item.get('name')
        url = item.get('url')
        
        print(f"[{idx+1}/{len(suwon_indices)}] Processing: {name}...")
        
        # Step 1: Fetch Popup HTML
        html = fetch_content(url)
        
        # Step 2: Extract AJAX Info
        suwon_match = re.search(r'var\s+getCctvUrl\s*=\s*[\'"]([^\'"]+)[\'"]\s*\+\s*streamCctv\.gCctvIp', html)
        id_match = re.search(r'new\s+StreamCctv\([\'"]([^\'"]+)[\'"]', html)
        
        found_url = None
        if suwon_match and id_match:
            api_path = suwon_match.group(1)
            cctv_id = id_match.group(1)
            base_domain = "https://its.suwon.go.kr" if "suwon" in url else "https://its.gg.go.kr"
            
            # Step A: Get CCTV Info (IP)
            time.sleep(1.0) # Conservative sub-delay
            info_url = f"{base_domain}/map/getCctvInfoById.do?cctvId={cctv_id}"
            info_json = fetch_content(info_url).strip()
            try:
                import json
                info_data = json.loads(info_json)
                ip = info_data.get('CCTVIP')
                if ip:
                    # Step B: Get Stream URL
                    time.sleep(1.0)
                    ajax_url = f"{base_domain}{api_path}{ip}"
                    ajax_resp = fetch_content(ajax_url).strip()
                    if ajax_resp and ajax_resp != "null" and ajax_resp.startswith("http"):
                        found_url = ajax_resp
            except:
                pass
        
        # Fallback to standard regex if AJAX fails
        if not found_url:
            match = re.search(r'var\s+[hl]url\s*=\s*"([^"]+\.(m3u8|mp4)[^"]*)"', html)
            if match: found_url = match.group(1)

        if found_url:
            data[target_idx]['url'] = found_url
            modified_count += 1
            print(f"  -> SUCCESS: {found_url}")
            # Immediate save for Suwon to ensure we don't lose progress if it crashes
            save_data(data)
        else:
            print("  -> FAILED: No stream URL found.")

        # MANDATORY SAFETY DELAY: 5 seconds
        if idx < len(suwon_indices) - 1:
            wait_time = 5.0 + random.random() * 2
            print(f"  Waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

    print(f"\nSuwon Collection Complete. Secured: {modified_count}")

if __name__ == "__main__":
    main()
