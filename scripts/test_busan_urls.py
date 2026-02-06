
import json
import requests

TARGET_KEYWORDS = ["동부산", "이케아", "롯데몰"]

def test_busan_urls():
    print("Testing Busan stream URLs...")
    
    with open("cctv_data.json", "r") as f:
        data = json.load(f)
        
    for item in data:
        name = item.get("name", "")
        if any(k in name for k in TARGET_KEYWORDS):
            url = item.get("url", "")
            
            # Quick HEAD request
            try:
                resp = requests.head(url, timeout=5, verify=False, allow_redirects=True)
                status = "OK" if resp.status_code < 400 else f"FAIL ({resp.status_code})"
            except Exception as e:
                status = f"ERROR ({str(e)[:30]})"
            
            print(f"{status}: {name}")
            if "FAIL" in status or "ERROR" in status:
                print(f"   URL: {url[:100]}...")

if __name__ == "__main__":
    test_busan_urls()
