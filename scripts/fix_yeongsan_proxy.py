import json
import re

DATA_FILE = 'cctv_data.json'
PROXY_BASE = "http://158.179.194.163:8080/proxy"

def fix_yeongsan_streams():
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
    
    count = 0
    # Pattern to extract wlobscd from:
    # https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd=13046
    pattern = re.compile(r'wlobscd=(\d+)')
    
    for item in data:
        url = item.get('url', '')
        if 'yeongsanriver.go.kr' in url and '/proxy' not in url:
            match = pattern.search(url)
            if match:
                code = match.group(1)
                # Construct HLS URL
                hls_url = f"https://cctvlo.yeongsanriver.go.kr/live/cctv{code}/hls.m3u8"
                # Wrap in Proxy
                new_url = f"{PROXY_BASE}?url={hls_url}"
                
                print(f"Updating {item['name']} ({item['id']}) -> {new_url}")
                item['url'] = new_url
                count += 1
            else:
                print(f"Skipping {item['name']} - No ID found in URL: {url}")

    if count > 0:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"Updated {count} Yeongsan River streams.")
    else:
        print("No Yeongsan River streams found to update.")

if __name__ == "__main__":
    fix_yeongsan_streams()
