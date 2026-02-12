
import requests
import urllib3
urllib3.disable_warnings()

def check_ssl(name, url, method="GET", data=None):
    print(f"Checking {name} SSL ({url})...")
    try:
        if method == "POST":
            resp = requests.post(url, data=data, timeout=10, verify=False)
        else:
            resp = requests.get(url, timeout=10, verify=False)
        print(f"  Result: {resp.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

# Gangwon
check_ssl("Gangwon List", "https://its.gn.go.kr/main/selectCctvList", "POST", "layerGubn=CCTV")

# GITS
check_ssl("GITS List", "https://gits.gg.go.kr/web/map/webLoadCCTVData.do")

# ITS
check_ssl("ITS API", "https://openapi.its.go.kr:9443/cctvInfo?apiKey=test&type=all&cctvType=1&minX=127&maxX=128&minY=37&maxY=38&getType=json")

# Daejeon
check_ssl("Daejeon List", "https://traffic.daejeon.go.kr/web-service/api/v1/traffic/getCctvList", "POST", {})

