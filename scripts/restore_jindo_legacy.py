
import json

TARGET_NAME = "[국도18호선]진도터미널"
PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"

def main():
    print(f"Restoring {TARGET_NAME} to Legacy Pre-Audit Configuration...")
    
    # 1. Find the ORIGINAL correct item from Pre-Audit
    pre_item = None
    with open(PRE_FILE, "r") as f:
        pre_data = json.load(f)
        for item in pre_data:
            if "진도터미널" in item['name']:
                pre_item = item
                break
    
    if not pre_item:
        print("CRITICAL: Pre-audit item not found!")
        return

    print(f"Original Item Found: {pre_item['name']} (ID: {pre_item['id']})")
    print(f"Original URL: {pre_item['url']}")

    # 2. Find the BROKEN item in Current Data (likely E901120 or similar name)
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        
    updated = False
    
    # We look for the item by NAME mainly
    for item in cur_data:
        if "진도터미널" in item['name']:
            print(f"Found broken item: {item['name']} (ID: {item['id']})")
            
            # FORCE RESTORE ID and URL
            # Only if they differ
            if item['id'] != pre_item['id'] or item['url'] != pre_item['url']:
                print(f"Restoring to Legacy ID {pre_item['id']} and URL...")
                item['id'] = pre_item['id']
                item['url'] = pre_item['url']
                
                # Protect it
                tags = item.get('tags', [])
                if "direct_source" not in tags: tags.append("direct_source")
                item['tags'] = tags
                
                updated = True
            else:
                print("Item already matches legacy config.")
                
            # If we found it, we stop (assuming only one Jindo Terminal)
            break
            
    if updated:
        with open(CUR_FILE, "w") as f:
            json.dump(cur_data, f, ensure_ascii=False, indent=2)
        print("Jindo Terminal restored successfully.")
    else:
        print("No changes made (or item not found in current DB to replace).")

if __name__ == "__main__":
    main()
