
import json

TARGET_KEYWORDS = ["동부산", "이케아", "롯데몰"]
FILES = [
    ("cctv_data.json", "Current DB"),
    ("cctv_overrides.json", "Overrides")
]

def debug_busan():
    for fname, label in FILES:
        print(f"\n=== {label}: {fname} ===")
        try:
            with open(fname, "r") as f:
                data = json.load(f)
                
            for item in data:
                name = item.get("name", "")
                if any(k in name for k in TARGET_KEYWORDS):
                    print(f"\nID: {item.get('id')}")
                    print(f"Name: {name}")
                    print(f"URL: {item.get('url', 'MISSING')[:150]}...")
                    print(f"Tags: {item.get('tags', [])}")
                    print(f"Status: {item.get('status', 'N/A')}")
        except Exception as e:
            print(f"Error loading {fname}: {e}")

if __name__ == "__main__":
    debug_busan()
