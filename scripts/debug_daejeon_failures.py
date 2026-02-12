
import requests
import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# CCTV08 appeared in the API sample. Let's see if it works.
IDS_TO_CHECK = ["CCTV08", "CCTV15", "CCTV16", "CCTV70"] 

def check_daejeon(cctv_id):
    if cctv_id.startswith("CCTV"):
        num = cctv_id[4:]
        stream_id = f"CTV{num.zfill(4)}"
    else:
        stream_id = cctv_id
        
    base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_"
    
    now = datetime.datetime.now()
    
    print(f"Checking {cctv_id} ({stream_id})...")
    
    for m in range(0, 10):
        t = now - datetime.timedelta(minutes=m)
        ts = t.strftime("%Y%m%d.%H%M00")
        url = f"{base_url}{ts}.000.mp4"
        
        try:
            r = requests.head(url, timeout=2, verify=False)
            if r.status_code == 200:
                print(f"[FOUND] {cctv_id} -> Offset {m}m: {url}")
                return True
        except Exception as e:
            # print(f"Err {url}: {e}")
            pass
            
    print(f"[FAIL] {cctv_id} - No working URL found in last 10 mins")
    return False

if __name__ == "__main__":
    for i in IDS_TO_CHECK:
        check_daejeon(i)
