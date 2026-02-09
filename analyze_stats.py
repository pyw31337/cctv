import json
import os

CCTV_DATA_FILE = "cctv_data.json"

def analyze_quality():
    if not os.path.exists(CCTV_DATA_FILE):
        print("Data file not found.")
        return

    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    by_source = {}
    direct_hls = 0 # .m3u8, .mp4, or specific direct domains
    jsp_wrappers = 0 # .jsp or .do urls

    for item in data:
        source = item.get('source', 'Unknown')
        by_source[source] = by_source.get(source, 0) + 1
        
        url = item.get('url', '').lower()
        # Quality check
        if any(ext in url for ext in ['.m3u8', '.mp4']) and 'jsp' not in url:
            direct_hls += 1
        elif 'jsp' in url or 'popup' in url or '.do' in url:
            jsp_wrappers += 1
        else:
            # Other (maybe direct but unknown pattern)
            direct_hls += 1 # NTIC and some other sources are often direct even without extension in this simple check

    print(f"Total Streams: {total}")
    print("\nBy Source:")
    for src, count in by_source.items():
        print(f"  - {src}: {count}")

    print("\nQuality Profile:")
    print(f"  - High Quality (Direct HLS/Direct): {direct_hls} ({100*direct_hls/total:.1f}%)")
    print(f"  - Standard (JSP/Wrappers): {jsp_wrappers} ({100*jsp_wrappers/total:.1f}%)")

if __name__ == "__main__":
    analyze_quality()
