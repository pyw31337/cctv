
import json

TARGETS = ["구리 왕숙천", "왕숙교"]
FILE = "cctv_data.json"

with open(FILE, "r") as f:
    data = json.load(f)

for item in data:
    for t in TARGETS:
        if t in item["name"]:
            print(f"FOUND: {item['name']} ({item['id']})")
            print(f"  URL: {item['url']}")
            print(f"  TAGS: {item.get('tags', [])}")
            print("-" * 20)
