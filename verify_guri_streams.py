import json
import requests
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, verify=False, timeout=10)
        r.encoding = 'utf-8'
        body = r.text
        
        # Try to extract .m3u8 URL
        m3u8_url = None
        match = re.search(r'(http[s]?://[^\s"\']+\.m3u8[^\s"\']*)', body)
        if match:
            m3u8_url = match.group(1)

        has_video = '<video' in body
        has_m3u8 = '.m3u8' in body
        has_error = 'error' in body.lower() or '실패' in body

        return {
            'status': r.status_code,
            'x_frame': r.headers.get('X-Frame-Options', 'OK'),
            'type': r.headers.get('Content-Type', 'Unknown'),
            'length': len(r.content),
            'body_snippet': body[:200].replace('\n', ' '),
            'has_video': has_video,
            'has_m3u8': has_m3u8,
            'has_error': has_error,
            'm3u8_url': m3u8_url
        }
    except Exception as e:
        print(f"DEBUG EXCEPTION: {e}")
        return {'status': 'Error', 'error': str(e)}

def main():
    print("Loading cctv_data.json...")
    with open('cctv_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Filter for Gu-ri (String Search)
    targets = [d for d in data if '구리' in d['name'] or '삼육고등학교' in d['name']]
    print(f"Found {len(targets)} targets.")
    
    for i, t in enumerate(targets[:10]):
        print(f"\n[{i+1}] {t['name']}")
        print(f"    URL: {t['url']}")
        res = check_url(t['url'])
        print(f"    -> Status: {res.get('status')}")
        print(f"    -> X-Frame-Options: {res.get('x_frame')}")
        print(f"    -> Content-Type: {res.get('type')}")
        print(f"    -> Body: {res.get('body_snippet')}...")
        print(f"    -> Indicators: Video={res.get('has_video')}, M3U8={res.get('has_m3u8')}, Error={res.get('has_error')}")
        if res.get('m3u8_url'):
            print(f"    -> Extracted HLS: {res.get('m3u8_url')}")

if __name__ == "__main__":
    main()
