
import json
import re

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"

# Generic Kinds that we generally treat as "standard"/low-priority and allowed to be overwritten
GENERIC_KINDS = ["1", "2", "3", "null", ""]

def get_kind(url):
    match = re.search(r"kind=([^&]+)", url)
    return match.group(1) if match else ""

def main():
    print("Starting ENHANCED Global Restoration (Busan kind=I, etc)...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = {item['id']: item for item in json.load(f)}
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        cur_map = {item['id']: item for item in cur_data}
        
    restored_count = 0
    
    for cid, pre_item in pre_data.items():
        pre_url = pre_item.get("url", "")
        pre_kind = get_kind(pre_url)
        
        # If the OLD kind was "Special" (not 1, 2, 3)
        # E.g. kind=I (Busan), kind=e (Paju), kind=KB (Guri)
        if pre_kind and pre_kind not in GENERIC_KINDS:
            
            cur_item = cur_map.get(cid)
            if cur_item:
                cur_url = cur_item.get("url", "")
                
                # If current URL is using a "Generic" kind or is just different
                if cur_url != pre_url:
                    cur_kind = get_kind(cur_url)
                    
                    # Log the restore
                    if cur_kind in GENERIC_KINDS:
                        print(f"Restoring Special Kind [{pre_kind}]: {pre_item['name']} ({cid})")
                        print(f"  WAS: ...kind={pre_kind}...")
                        print(f"  NOW: ...kind={cur_kind}...")
                        
                        cur_item['url'] = pre_url
                        tags = cur_item.get('tags', [])
                        if "direct_source" not in tags: tags.append("direct_source") # Protect it
                        cur_item['tags'] = tags
                        
                        restored_count += 1

    if restored_count > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(list(cur_map.values()), f, ensure_ascii=False, indent=2)
        print(f"\nENHANCED RESTORE: Successfully restored {restored_count} special-kind streams.")
    else:
        print("No further special-kind streams found to restore.")

if __name__ == "__main__":
    main()
