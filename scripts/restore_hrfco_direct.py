
import json

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"
TARGET_DOMAIN = "lw.hrfco.go.kr"

def main():
    print("Restoring HRFCO Direct Links...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = {item['id']: item for item in json.load(f)}
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        cur_map = {item['id']: item for item in cur_data}
        
    restored = 0
    
    for cid, pre_item in pre_data.items():
        pre_url = pre_item.get("url", "")
        
        # Check if pre-audit URL was a Direct HRFCO link
        if TARGET_DOMAIN in pre_url:
            cur_item = cur_map.get(cid)
            if cur_item:
                # Check if current is NOT the same direct link
                if cur_item['url'] != pre_url:
                    print(f"Restoring {pre_item['name']} ({cid})")
                    print(f"  WAS: {pre_url}")
                    print(f"  NOW: {cur_item['url']}")
                    
                    cur_item['url'] = pre_url
                    tags = cur_item.get('tags', [])
                    if "direct_source" not in tags: tags.append("direct_source")
                    cur_item['tags'] = tags
                    restored += 1

    if restored > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(list(cur_map.values()), f, ensure_ascii=False, indent=2)
        print(f"\nSuccessfully restored {restored} HRFCO direct streams.")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()
