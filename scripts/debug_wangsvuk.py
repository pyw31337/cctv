
import json

NAME = "남양주시(왕숙교)"
FILES = [
    ("PRE", "cctv_data_pre_audit_v2.json"),
    ("CUR", "cctv_data.json")
]

for label, fname in FILES:
    print(f"Checking {label}: {fname}")
    try:
        with open(fname, "r") as f:
            data = json.load(f)
        found = False
        for item in data:
            if NAME in item["name"]:
                print(f"  FOUND: {item['name']} ({item['id']})")
                print(f"  URL: {item['url']}")
                found = True
        if not found:
            print("  NOT FOUND")
    except Exception as e:
        print(f"  ERROR: {e}")
    print("-" * 20)
