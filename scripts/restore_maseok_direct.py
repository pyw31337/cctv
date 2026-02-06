
import json
import time

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"
TARGET_IP = "211.57.45.101" # Namyangju ITS

def main():
    print(f"Restoring Direct Links for IP {TARGET_IP}...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = {item['id']: item for item in json.load(f)}
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        cur_map = {item['id']: item for item in cur_data}
        
    restored = 0
    
    for cid, pre_item in pre_data.items():
        pre_url = pre_item.get("url", "")
        
        # Check if pre-audit URL was from the target IP
        if TARGET_IP in pre_url and "utic.go.kr" not in pre_url:
            cur_item = cur_map.get(cid)
            if cur_item:
                # Check if current is wrapped/different
                if cur_item['url'] != pre_url:
                    print(f"Restoring {pre_item['name']} ({cid})")
                    print(f"  WAS: {pre_url}")
                    print(f"  NOW: {cur_item['url']}")
                    
                    # Restore
                    cur_item['url'] = pre_url
                    
                    # Add tag
                    tags = cur_item.get('tags', [])
                    if "direct_source" not in tags:
                        tags.append("direct_source")
                    cur_item['tags'] = tags
                    
                    restored += 1
                    print("  -> RESTORED + TAGGED")

    if restored > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(list(cur_map.values()), f, ensure_ascii=False, indent=2)
        print(f"\nSuccessfully restored {restored} Namyangju/Maseok direct streams.")
    else:
        print("No missing streams found for this IP.")

if __name__ == "__main__":
    main()
