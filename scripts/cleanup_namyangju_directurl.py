import json
from pathlib import Path

def main():
    data_path = Path("cctv_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    fixed = 0
    for item in data:
        if item.get("id", "").startswith("L180"):
            # If directUrl exists and is different from url, it's a potential source of confusion
            if "directUrl" in item:
                # For Namyangju, we want to rely on the manually fixed 'url'
                # If we have a directUrl, it should match the url or be removed.
                if item["directUrl"] != item["url"]:
                    print(f"Cleaning {item['name']} ({item['id']}): Removing directUrl '{item['directUrl']}' which mismatch url '{item['url']}'")
                    del item["directUrl"]
                    fixed += 1
                else:
                    # Even if they match, let's just keep 'url' to be simple for L180
                    del item["directUrl"]
                    fixed += 1

    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Cleaned directUrl from {fixed} Namyangju entries.")

if __name__ == "__main__":
    main()
