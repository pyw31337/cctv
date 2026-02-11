
import json
import sys

DATA_FILE = "cctv_data.json"

MOVES = [
    {
        "id": "L030049",
        "name": "역곡고가사거리",
        "url": "http://localhost:8080/proxy?url=https://stream6.bcits.go.kr/bucheon/TM098TC07P.stream/playlist.m3u8",
        "tags": ["proxy_source"]
    },
    {
        "id": "E600016",
        "name": "서울시(너부대교)",
        "url": "https://lw.hrfco.go.kr/live/cctv1120210/hls.m3u8",
        "tags": ["direct_source"]
    }
]

def main():
    print("Loading CCTV Data...")
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {DATA_FILE}: {e}")
        return

    updated_count = 0
    data_map = {item['id']: item for item in data}

    for move in MOVES:
        cid = move['id']
        if cid in data_map:
            item = data_map[cid]
            if item['url'] != move['url']:
                print(f"Updating {item['name']} ({cid})")
                print(f"  WAS: {item['url']}")
                print(f"  NOW: {move['url']}")
                item['url'] = move['url']
                
                # Update tags
                current_tags = item.get('tags', [])
                for tag in move['tags']:
                    if tag not in current_tags:
                        current_tags.append(tag)
                item['tags'] = current_tags
                
                updated_count += 1
        else:
            print(f"Warning: ID {cid} not found in data.")

    if updated_count > 0:
        print(f"Saving {updated_count} updates to {DATA_FILE}...")
        with open(DATA_FILE, "w") as f:
            json.dump(list(data_map.values()), f, ensure_ascii=False, indent=2)
        print("Done.")
    else:
        print("No updates needed.")

if __name__ == "__main__":
    main()
