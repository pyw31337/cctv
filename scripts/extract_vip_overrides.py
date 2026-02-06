
import json

INPUT_FILE = "cctv_data.json"
OUTPUT_FILE = "cctv_overrides.json"
VIP_KEYWORDS = ["파주", "남양주", "부산", "해운대", "진도", "구리", "왕숙천", "왕숙교", "역곡", "부천", "너부대교"]

def main():
    try:
        with open(INPUT_FILE, "r") as f:
            data = json.load(f)
            
        overrides = []
        for item in data:
            name = item.get("name", "")
            tags = item.get("tags", [])
            
            # Match strict VIP criteria: Name match AND direct_source (or explicitly important ones)
            is_vip = any(k in name for k in VIP_KEYWORDS)
            
            # We want to protect:
            # 1. Anything user explicitly fixed (Paju, Jindo, Yeokgok)
            # 2. Existing Direct Sources in VIP regions (Busan)
            
            if is_vip:
                # Capture the "Golden" state
                override_entry = {
                    "id": item["id"],
                    "name": item["name"],
                    "url": item["url"],
                    "tags": tags,
                    "_comment": "Auto-extracted from VIP logic"
                }
                overrides.append(override_entry)
                
        print(f"Found {len(overrides)} VIP items to protect.")
        
        # Save to overrides file
        with open(OUTPUT_FILE, "w", encoding='utf-8') as f:
            json.dump(overrides, f, ensure_ascii=False, indent=2)
            
        print(f"Saved to {OUTPUT_FILE}")
        
        # Validation: Check important ones
        check_list = ["진도", "역곡", "파주", "너부대교"]
        for k in check_list:
            found = any(k in o["name"] for o in overrides)
            print(f"  Includes {k}? {'YES' if found else 'NO'}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
