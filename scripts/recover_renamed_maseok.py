
import json
import math

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"
TARGET_IP = "211.57.45.101"

def dist(lat1, lng1, lat2, lng2):
    return math.sqrt((lat1-lat2)**2 + (lng1-lng2)**2)

def main():
    print("Matching Namyangju Streams by Coordinates...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = json.load(f)
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        cur_items = []
        for item in cur_data:
            if item.get('lat') and item.get('lng'):
                cur_items.append(item)
    
    restored = 0
    
    # 0.0005 degrees is roughly 50 meters
    TOLERANCE = 0.0005 
    
    for pre in pre_data:
        # Filter for our target IP links that are NOT yet restored
        if TARGET_IP in pre.get('url', '') and "utic.go.kr" not in pre.get('url', ''):
             
            # Check if this name was already restored (check current DB)
            # Or simplified: check if we can find a match in current DB that needs restoration
            
            p_lat = pre.get('lat')
            p_lng = pre.get('lng')
            
            if not p_lat or not p_lng: continue
            
            best_match = None
            min_d = 999
            
            for cur in cur_items:
                d = dist(p_lat, p_lng, cur['lat'], cur['lng'])
                if d < min_d:
                    min_d = d
                    best_match = cur
            
            if best_match and min_d < TOLERANCE:
                # Found a geographic match!
                # Check if URL needs update
                if best_match['url'] != pre['url']:
                    print(f"Match: '{pre['name']}' -> '{best_match['name']}' (Dist: {min_d:.6f})")
                    print(f"  Url: {pre['url']}")
                    
                    best_match['url'] = pre['url']
                    tags = best_match.get('tags', [])
                    if "direct_source" not in tags: tags.append("direct_source")
                    best_match['tags'] = tags
                    restored += 1

    if restored > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(cur_data, f, ensure_ascii=False, indent=2)
        print(f"\nRecovered {restored} renamed streams via coordinate match.")
    else:
        print("No matches found.")

if __name__ == "__main__":
    main()
