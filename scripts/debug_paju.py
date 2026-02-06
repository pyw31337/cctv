
import json

TARGETS = ["삽다리IC", "심학중사거리"]
FILES = [
    ("PRE", "cctv_data_pre_audit_v2.json"),
    ("CUR", "cctv_data.json")
]

for label, fname in FILES:
    print(f"Checking {label}: {fname}")
    try:
        with open(fname, "r") as f:
            data = json.load(f)
        for item in data:
            for t in TARGETS:
                if t in item["name"]:
                    print(f"  FOUND: {item['name']} ({item['id']})")
                    print(f"  URL: {item['url']}")
        print("-" * 20)
    except Exception as e:
        print(f"  ERROR: {e}")
