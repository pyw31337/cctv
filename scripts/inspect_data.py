
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA_FILE = os.path.join(BASE_DIR, "cctv_data.json")

def main():
    if not os.path.exists(CCTV_DATA_FILE):
        print("File not found")
        return
        
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total items: {len(data)}")
    
    # Check for Daejeon entries
    daejeon_items = [item for item in data if "DAEJEON" in item.get("id", "")]
    print(f"Items with DAEJEON in ID: {len(daejeon_items)}")
    
    if daejeon_items:
        print("Sample DAEJEON item:")
        print(daejeon_items[0])
    else:
        # Check by name or other field
        by_name = [item for item in data if "대전" in item.get("name", "")]
        print(f"Items with '대전' in name: {len(by_name)}")
        if by_name:
            print("Sample item by name:")
            print(by_name[0])

if __name__ == "__main__":
    main()
