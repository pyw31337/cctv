
import json

TARGETS = ["마석사거리(웹)", "마석윗3", "창현A앞4"]
FILE = "cctv_data_pre_audit_v2.json"

with open(FILE, "r") as f:
    data = json.load(f)

for item in data:
    for t in TARGETS:
        if t in item["name"]:
            print(f"FOUND: {item['name']} ({item['id']})")
            print(f"  URL: {item['url']}")
            print("-" * 20)
