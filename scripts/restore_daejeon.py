
import json
import os
import requests
import urllib3
import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_daejeon_status(cctv_id):
    if cctv_id.startswith("DAEJEON_"):
        raw_id = cctv_id.replace("DAEJEON_", "")
    else:
        raw_id = cctv_id
        
    if raw_id.startswith("CCTV"):
        num = raw_id[4:]
        stream_id = f"CTV{num.zfill(4)}"
    else:
        stream_id = raw_id

    base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_"
    now = datetime.datetime.now()
    
    # Check last 5 minutes
    for m in range(0, 5):
        t = now - datetime.timedelta(minutes=m)
        ts = t.strftime("%Y%m%d.%H%M00")
        url = f"{base_url}{ts}.000.mp4"
        try:
            r = requests.head(url, timeout=2, verify=False)
            if r.status_code == 200:
                return True
        except:
            pass
    return False

def main():
    print("Checking disabled Daejeon streams...")
    data = load_json(CCTV_DATA_FILE)
    
    # Find inactive Daejeon streams
    targets = [item for item in data if item.get("id", "").startswith("DAEJEON_") and item.get("status") == "inactive"]
    
    print(f"Found {len(targets)} inactive Daejeon streams.")
    
    restored_count = 0
    for item in targets:
        if check_daejeon_status(item["id"]):
            print(f"[RESTORE] {item['name']} ({item['id']}) is UP.")
            item["status"] = "active"
            item["status_note"] = "Restored after manual check"
            restored_count += 1
        else:
            print(f"[DEAD] {item['name']} ({item['id']}) is still DOWN.")
            
    if restored_count > 0:
        save_json(CCTV_DATA_FILE, data)
        print(f"Restored {restored_count} Daejeon streams.")
    else:
        print("No Daejeon streams recovered.")

if __name__ == "__main__":
    main()
