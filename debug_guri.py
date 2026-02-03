import json
import math

def get_distance(lat1, lng1, lat2, lng2):
    R = 6371000  # meters
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2) * math.sin(dLat/2) + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(dLng/2) * math.sin(dLng/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def main():
    # Gu-ri City Hall (Approximate)
    target_lat = 37.5943124
    target_lng = 127.1295646
    
    print(f"Target: Gu-ri City Hall ({target_lat}, {target_lng})")
    
    with open('cctv_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    print(f"Total CCTVs: {len(data)}")
    
    candidates = []
    for item in data:
        dist = get_distance(target_lat, target_lng, float(item['lat']), float(item['lng']))
        candidates.append((dist, item))
        
    candidates.sort(key=lambda x: x[0])
    
    print("\nTop 10 Closest CCTVs:")
    for dist, item in candidates[:10]:
        print(f"{dist:.1f}m - {item['name']} ({item['lat']}, {item['lng']})")

if __name__ == "__main__":
    main()
