
import json
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = "cctv_data.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def main():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    
    jindo_items = [item for item in data if "진도" in item.get("name", "") and "당진" not in item.get("name", "")]
    print(f"Testing {len(jindo_items)} Jindo items...")
    
    for item in jindo_items:
        url = item.get("url", "")
        print(f"Testing [{item['id']}] {item['name']}...", end=" ", flush=True)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            if resp.status_code == 200:
                if "비정상적인 접근" in resp.text:
                    print("❌ BLOCKED")
                elif "ConnectSrv" in resp.text:
                    # Check for invalid IP
                    import re
                    match = re.search(r"ConnectSrv\('[^']+', '[^']+', '([^']+)'", resp.text)
                    if match:
                        ip = match.group(1)
                        if ".73606" in ip or ".50247" in ip: # Common Jindo garbage
                            print(f"❌ INVALID_IP ({ip})")
                        else:
                            print(f"✅ OK ({ip})")
                    else:
                        print("✅ OK (Manual Check needed)")
                else:
                    print(f"✅ OK ({resp.status_code})")
            else:
                print(f"❌ FAIL ({resp.status_code})")
        except Exception as e:
            print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    main()
