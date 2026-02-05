import json
import re

DATA_FILE = "cctv_data.json"

def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated_count = 0
    report = []
    
    print("| Region | Name | ID | New URL |")
    print("|---|---|---|---|")

    for item in data:
        url = item.get('url', '')
        name = item.get('name', '')
        
        # 1. Nakdong River
        if "nakdongriver.go.kr" in url and "popup" in url:
            match = re.search(r'Obscd=([\d]+)', url)
            if match:
                code = match.group(1)
                new_url = f"https://cctvlo.nakdongriver.go.kr/live/cctv{code}/hls.m3u8"
                item['url'] = new_url
                updated_count += 1
                report.append(f"| Nakdong | {name} | {code} | [Link]({new_url}) |")

        # 2. Geum River
        elif "geumriver.go.kr" in url and "rtmpView.jsp" in url:
            match = re.search(r'cctvcd=([\d]+)', url) # Uses cctvcd
            if match:
                code = match.group(1)
                new_url = f"https://cctvlo.geumriver.go.kr/live/cctv{code}/hls.m3u8"
                item['url'] = new_url
                updated_count += 1
                report.append(f"| Geum | {name} | {code} | [Link]({new_url}) |")

        # 3. Yeongsan River
        elif "yeongsanriver.go.kr" in url:
            match = re.search(r'wlobscd=([\d]+)', url) # Uses wlobscd
            if match:
                code = match.group(1)
                new_url = f"https://cctvlo.yeongsanriver.go.kr/live/cctv{code}/hls.m3u8"
                item['url'] = new_url
                updated_count += 1
                report.append(f"| Yeongsan | {name} | {code} | [Link]({new_url}) |")

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
