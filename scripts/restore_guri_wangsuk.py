
import json

TARGET_NAME = "구리 왕숙천"
PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"

def main():
    print(f"Restoring {TARGET_NAME} by Name...")
    
    pre_item = None
    with open(PRE_FILE, "r") as f:
        pre_data = json.load(f)
        for item in pre_data:
            if TARGET_NAME in item['name']:
                pre_item = item
                break
    
    if not pre_item:
        print("Pre-audit item not found.")
        return

    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        
    restored = False
    for item in cur_data:
        if TARGET_NAME in item['name']:
            print(f"Match found: {item['name']} ({item['id']})")
            print(f"  Current URL: {item['url']}")
            print(f"  Target URL: {pre_item['url']}")
            
            if item['url'] != pre_item['url']:
                item['url'] = pre_item['url']
                # Guri L-codes often need tags to prevent overwrite?
                tags = item.get('tags', [])
                if "direct_source" not in tags: tags.append("direct_source")
                item['tags'] = tags
                restored = True
                print("  -> RESTORED")
    
    if restored:
        with open(CUR_FILE, "w") as f:
            json.dump(cur_data, f, ensure_ascii=False, indent=2)
        print("Required changes saved.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    main()
