import json
import re

DATA_FILE = "cctv_data.json"

def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    report = []
    
    print("| Name | Old Code | New URL |")
    print("|---|---|---|")

    for item in data:
        url = item.get('url', '')
        # Pattern: https://hrfco.go.kr/sumun/cctvPopup.do?Obscd=116032
        if "hrfco.go.kr" in url and "cctvPopup.do" in url:
            match = re.search(r'Obscd=([\d]+)', url)
            if match:
                obscd = match.group(1)
                old_url = url
                new_url = f"https://lw.hrfco.go.kr/live/cctv{obscd}/hls.m3u8"
                
                item['url'] = new_url
                updated_count += 1
                report.append(f"| {item.get('name')} | {obscd} | [Link]({new_url}) |")

    # Save
    if updated_count > 0:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"\nSuccessfully updated {updated_count} items.\n")
        print("\n".join(report))
    else:
        print("No items found to update.")

if __name__ == "__main__":
    main()
