
import json

TARGET = "구리 왕숙천"
FILE = "cctv_data_pre_audit_v2.json"

with open(FILE, "r") as f:
    data = json.load(f)

found = False
for item in data:
    if TARGET in item["name"]:
        print(f"FOUND: {item['name']} ({item['id']})")
        print(f"  URL: {item['url']}")
        found = True

if not found:
    print("NOT FOUND in Pre-Audit")
