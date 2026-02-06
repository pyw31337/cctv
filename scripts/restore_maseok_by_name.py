
import json
import time

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"
TARGET_IP = "211.57.45.101"

def normalize_name(n):
    return n.replace(" ", "").strip()

def main():
    print(f"Restoring Direct Links for IP {TARGET_IP} BY NAME...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = json.load(f)
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        
    # Map Pre-Audit Name -> URL
    name_to_url = {}
    for item in pre_data:
        if TARGET_IP in item.get('url', ''):
            # Key by normalized name
            name_to_url[normalize_name(item['name'])] = item['url']
            
    print(f"Found {len(name_to_url)} target URLs in pre-audit data.")
    
    # Apply to Current Data
    restored = 0
    cur_map = {item['id']: item for item in cur_data}
    
    for item in cur_data:
        norm_name = normalize_name(item['name'])
        if norm_name in name_to_url:
            direct_url = name_to_url[norm_name]
            
            # Only update if different
            if item['url'] != direct_url:
                print(f"Restoring {item['name']} ({item['id']})")
                print(f"  WAS: {item['url']}")
                print(f"  NOW: {direct_url}")
                
                item['url'] = direct_url
                tags = item.get('tags', [])
                if "direct_source" not in tags:
                    tags.append("direct_source")
                item['tags'] = tags
                
                restored += 1

    if restored > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(cur_data, f, ensure_ascii=False, indent=2)
        print(f"\nSuccessfully restored {restored} streams by name match.")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()
