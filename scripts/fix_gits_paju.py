import json

CCTV_DATA_FILE = "cctv_data.json"

def fix_gits_streams():
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    fixed_count = 0
    for item in data:
        # Check if it's a GITS stream using 211.57.45.101
        if "211.57.45.101" in item.get("url", "") or "211.57.45.101" in item.get("directUrl", ""):
            cctv_id = item["id"]
            # Construct direct HLS URL
            # Pattern: https://211.57.45.101/media/{id}/chunklist.m3u8
            new_url = f"https://211.57.45.101/media/{cctv_id}/chunklist.m3u8"
            
            if item.get("directUrl") != new_url:
                item["directUrl"] = new_url
                item["tags"] = list(set(item.get("tags", []) + ["direct_source"]))
                fixed_count += 1
                
        # Also fix Paju streams that use UTIC JSP but have direct variants
        if item["id"].startswith("L12") and "utic.go.kr" in item.get("url", ""):
             new_url = f"https://211.57.45.101/media/{item['id']}/chunklist.m3u8"
             if item.get("directUrl") != new_url:
                item["directUrl"] = new_url
                item["tags"] = list(set(item.get("tags", []) + ["direct_source"]))
                fixed_count += 1

    if fixed_count > 0:
        with open(CCTV_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Fixed {fixed_count} GITS/Paju streams.")
    else:
        print("No streams needed fixing.")

if __name__ == "__main__":
    fix_gits_streams()
