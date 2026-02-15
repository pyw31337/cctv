import json

CCTV_DATA_FILE = "cctv_data.json"
STREAM_PATTERNS = {
    "HLS": [".m3u8", "!hls", "playlist.m3u8"],
    "MP4": [".mp4"],
    "UTIC_API": ["openDataCctvStream.jsp", "cctvPopup.do", "cctvView.do", "videoDetail.do"]
}

def categorize_streams(data):
    categories = {cat: [] for cat in STREAM_PATTERNS}
    categories["Other"] = []
    
    for item in data:
        if item.get("status") in ["inactive", "broken"]:
            continue
            
        url = item.get("url", "")
        categorized = False
        
        for category, patterns in STREAM_PATTERNS.items():
            if any(p in url for p in patterns):
                categories[category].append(item)
                categorized = True
                break
        
        if not categorized:
            categories["Other"].append(item)
    
    return categories

with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

categories = categorize_streams(data)
for cat, items in categories.items():
    print(f"Category {cat}: {len(items)} items")
    if items:
        print(f"  Sample URL: {items[0].get('url')}")
