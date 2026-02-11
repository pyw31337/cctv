
import json

DATA_FILE = "cctv_data.json"

def main():
    print("Fixing Daejeon Metadata...")
    
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    updated_count = 0
    
    for item in data:
        if item.get('source') == 'DAEJEON_ITS':
            # Check if needs update
            if item.get('urlType') != 'daejeon_mp4_dynamic':
                item['urlType'] = 'daejeon_mp4_dynamic'
                updated_count += 1
    
    if updated_count > 0:
        print(f"Updating {updated_count} Daejeon entries...")
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Done.")
    else:
        print("No Daejeon updates needed.")

if __name__ == "__main__":
    main()
