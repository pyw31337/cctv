
import requests
import json
import urllib.parse

# Target: Onsu (L010227)
# Base URL parameters
BASE_URL = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
CCTV_ID = "L010227"
CCTV_NAME_RAW = "온수"
ENCODED_NAME = urllib.parse.quote(urllib.parse.quote(CCTV_NAME_RAW))

# Parameters from debug output
# kind=MODE, cctvch=51, id=31

KINDS = ["MODE", "1", "2", "3", "a", "b", "c", "Z3", "C"]
CH_VALS = ["51", "null"]

print(f"Fuzzing Onsu ({CCTV_ID})...")

for k in KINDS:
    for ch in CH_VALS:
        params = {
            "key": KEY,
            "cctvid": CCTV_ID,
            "cctvName": ENCODED_NAME,
            "kind": k,
            "cctvip": "",
            "cctvch": ch,
            "id": "31",
            "cctvpasswd": "null",
            "cctvport": "null"
        }
        qs = "&".join([f"{key}={val}" for key, val in params.items()])
        url = f"{BASE_URL}?{qs}"
        
        try:
            resp = requests.head(url, timeout=3, verify=False)
            print(f"KIND={k}, CH={ch} -> {resp.status_code}")
        except Exception as e:
            print(f"KIND={k}, CH={ch} -> ERROR")

