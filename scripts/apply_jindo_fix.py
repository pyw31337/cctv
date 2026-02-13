
import json
import os

DATA_FILE = "cctv_data.json"

# Extracted HLS URLs from National ITS
JINDO_HLS_MAPPING = {
    "진도 향토문화회관": "https://cctvsec.ktict.co.kr/73604/TZyaRqBZxHm3rPvMBbYDvZBh6cTnxbHhhd80NOpNxhdkZwgaHpZAUkj/A8xLkDTw!hls",
    "진도 포산삼거리": "https://cctvsec.ktict.co.kr/73604/TZyaRqBZxHm3rPvMBbYDvZBh6cTnxbHhhd80NOpNxhdkZwgaHpZAUkj/A8xLkDTw!hls",
    "진도 진도터미널인근": "https://cctvsec.ktict.co.kr/73605/RKWAsnW8ynSCBsOVL5jlhuLrz5tgjEitCAFegAAk6ZYpORyQ526wacoE5+LYz+Kp!hls",
    "진도 진도고교앞교차로": "https://cctvsec.ktict.co.kr/73582/8F5Csbtc0x0UryIW33BKf0MDzN93GoGqyowtGsgY3rMuBMm4I8SptiqiIi9fnoxU!hls",
    "진도 정거럼재삼거리 인근": "https://cctvsec.ktict.co.kr/73607/Xx5aRJUClcJezBiFe6i4UFLgDlxyoge8pb3dE9lUr4BFKLXTM2p9JpJoWX9yW/dX!hls",
    "진도 월가리마을회관인근": "https://cctvsec.ktict.co.kr/73583/vjQtRelIryeiizCoAQKMNfIGb/YZv85TM0umJLMcTAIXhcyvCvVSfOVXrOms18Dz!hls",
    "진도 군내교차로인근": "https://cctvsec.ktict.co.kr/73584/qJ3Bb6NwJZnAWATnzdxzQzvL+MPPMBuzIqc5rkCa8oNwaae6cPbVOtU/xzyf/68F!hls",
    "진도 진도터널입구": "https://cctvsec.ktict.co.kr/73609/J6EN9D093v05AP/zBlFsnAswffBSS3meiidQs9iap99BCA6RW3eEK2po3uUvCjrK!hls",
    "진도 안농마을인근": "https://cctvsec.ktict.co.kr/73608/yfIeWhCkcV6L76eUbsu5SJ5A/WcLDiXjZwRZB+f+0E14yfNxTNy0ejF9H1aYIKQC!hls",
    "진도 금성마을인근": "https://cctvsec.ktict.co.kr/78814/9Np/nvgDn/7seDmrTVnTXtwQcfeVpVYr21L5LufFp+iDdY+QLIRD2CuFlrHaw3gb!hls",
    "진도 신동교차로인근": "https://cctvsec.ktict.co.kr/73585/bbnKrWmhrIoWYB/FQTqZwFyKxI3Cokk9dIXQqyCZjnD2B4q4Y4ca8LJJ8uah1sGY!hls",
    "진도 진도대교": "https://cctvsec.ktict.co.kr/73586/kHywnvgbZFDdPVywyPdPpEQn3N9P6Es9e2nvHW2NnB25xYHyJiKjZpvEfYq0AHFE!hls"
}

JINDO_PORT_URL = "https://www.khoa.go.kr/SEAFOG/m4NiLawsC202gM5ixA7MPTYtO19KmV/hls/khoa/Jindo/s.m3u8"

def main():
    if not os.path.exists(DATA_FILE):
        print(f"Error: {DATA_FILE} not found.")
        return

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    updated_count = 0
    added_count = 0
    
    # 1. Update existing entries
    for item in data:
        name = item.get("name", "")
        if "진도" in name and "당진" not in name:
            # Map by sub-string match
            found = False
            for loc_name, hls_url in JINDO_HLS_MAPPING.items():
                # Remove common prefixes like [국도18호선] for matching
                clean_name = name.replace("[국도18호선]", "").replace("[국도2호선]", "").strip()
                clean_loc = loc_name.replace("진도 ", "").strip()
                
                if clean_loc in clean_name or clean_name in clean_loc:
                    print(f"Updating [{item['id']}] {name} -> {loc_name}")
                    item["url"] = hls_url
                    item["urlType"] = "hls"
                    item["status"] = "active"
                    tags = item.get("tags", [])
                    if "direct_source" not in tags: tags.append("direct_source")
                    item["tags"] = tags
                    updated_count += 1
                    found = True
                    break
            
            if not found:
                print(f"No exact mapping found for {name} (ID: {item['id']}), skipping update.")

    # 2. Add Jindo Port as a new high-quality entry
    # Check if already exists
    if not any(item.get("id") == "KHOA_JINDO_PORT" for item in data):
        new_item = {
            "id": "KHOA_JINDO_PORT",
            "name": "진도항 (실시간 해양영상)",
            "lat": 34.3942,
            "lng": 126.1310,
            "url": JINDO_PORT_URL,
            "urlType": "hls",
            "source": "KHOA",
            "status": "active",
            "tags": ["direct_source", "high_quality"]
        }
        data.append(new_item)
        added_count += 1
        print("Added Jindo Port (KHOA_JINDO_PORT)")

    # 3. Add any missing HLS items from National ITS as new entries
    # This ensures we have full coverage even if IDs changed
    for loc_name, hls_url in JINDO_HLS_MAPPING.items():
        if not any(item.get("url") == hls_url for item in data):
            # Create a simple unique ID
            import hashlib
            h = hashlib.md5(loc_name.encode()).hexdigest()[:8]
            new_id = f"ITS_JINDO_{h}"
            
            new_item = {
                "id": new_id,
                "name": loc_name,
                "url": hls_url,
                "urlType": "hls",
                "source": "ITS_GO_KR",
                "status": "active",
                "tags": ["direct_source"]
                # Cords are missing, but we can fill them later if needed or leave 0
            }
            data.append(new_item)
            added_count += 1
            print(f"Added new Jindo location: {loc_name} ({new_id})")

    if updated_count > 0 or added_count > 0:
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Done. Updated {updated_count} items, added {added_count} items.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    main()
