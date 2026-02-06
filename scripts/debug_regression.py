
import json
import requests

TARGETS = ["온수", "서울시(너부대교)", "오류IC"]

with open("cctv_data.json", "r") as f:
    data = json.load(f)

print(f"Checking {len(TARGETS)} targets...")

for item in data:
    for t in TARGETS:
        if item["name"] == t or (t in item["name"] and len(item["name"]) < len(t) + 5):
            print(f"MATCH: {item['name']} ({item['id']})")
            print(f"  URL: {item['url']}")
            # Check status
            try:
                resp = requests.head(item['url'], timeout=5, verify=False)
                print(f"  STATUS: {resp.status_code}")
            except Exception as e:
                print(f"  ERROR: {e}")
            print("-" * 40)
