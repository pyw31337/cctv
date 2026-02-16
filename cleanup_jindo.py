import json
import os

DATA_FILE = "cctv_data.json"

def main():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # 1. Identify Jindo items (and keep others)
    jindo_items = []
    other_items = []
    
    for item in data:
        name = item.get("name", "")
        if "진도" in name and "당진" not in name:
            jindo_items.append(item)
        else:
            other_items.append(item)
            
    print(f"Initial Jindo items: {len(jindo_items)}")

    # 2. De-duplicate Jindo items
    # Normalize names and look for duplicates
    # We'll group by a simplified name
    seen_locations = {}
    cleaned_jindo = []
    
    # Priority for de-duplication
    # We prefer items that:
    # 1. Don't have "SCAN_" in name
    # 2. Have valid status
    # 3. Have more metadata
    
    # Sort so that "better" items come first
    jindo_items.sort(key=lambda x: (
        0 if "SCAN_" not in x.get("name", "") else 1,
        0 if x.get("status") == "active" else 1,
        -len(str(x)) # more data
    ))

    for item in jindo_items:
        name = item["name"]
        # Basic name normalization: remove "[국도18호선]" etc.
        norm_name = name.replace("[국도18호선]", "").strip()
        
        # Special case for "진도향토문화회관"
        if "진도향토문화회관" in norm_name:
            norm_name = "진도향토문화회관"
            
        if norm_name not in seen_locations:
            seen_locations[norm_name] = item
            cleaned_jindo.append(item)
        else:
            print(f"Removing duplicate: {item['id']} ({item['name']}) -> keeping {seen_locations[norm_name]['id']}")

    print(f"Cleaned Jindo items: {len(cleaned_jindo)}")
    
    # 3. Merge back
    final_data = other_items + cleaned_jindo
    
    # Sort final data for consistency
    final_data.sort(key=lambda x: x["id"])

    with open(DATA_FILE, "w") as f:
        json.dump(final_data, f, indent=2, sort_keys=True)
        
    print(f"Total items in {DATA_FILE}: {len(final_data)}")

if __name__ == "__main__":
    main()
