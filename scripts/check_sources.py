
import json
import os
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")

def main():
    if not os.path.exists(CCTV_DATA_FILE):
        return
        
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    sources = Counter([item.get("source", "UNKNOWN") for item in data])
    print("Sources found:")
    for s, c in sources.items():
        print(f"{s}: {c}")

if __name__ == "__main__":
    main()
