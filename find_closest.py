import json
import math

def get_distance(lat1, lng1, lat2, lng2):
    # Haversine formula
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

target_lat = 37.52348
target_lng = 126.8812
target_name = "Omokgyo"

try:
    with open('ntic_data.json', 'r') as f:
        data = json.load(f)
        
    closest_dist = float('inf')
    closest_cctv = None
    
    for cctv in data:
        dist = get_distance(target_lat, target_lng, cctv['lat'], cctv['lng'])
        if dist < closest_dist:
            closest_dist = dist
            closest_cctv = cctv
            
    if closest_cctv:
        print(f"Closest CCTV to {target_name}:")
        print(f"Name: {closest_cctv['name']}")
        print(f"Distance: {closest_dist:.2f} meters")
        print(f"URL: {closest_cctv['url']}")
    else:
        print("No CCTVs found.")
        
except Exception as e:
    print(f"Error: {e}")
