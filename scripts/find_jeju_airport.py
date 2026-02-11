
import json
import math

# Jeju Airport Coords
TARGET_LAT = 33.5104
TARGET_LNG = 126.4913

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

with open('cctv_data.json', 'r') as f:
    data = json.load(f)

print("Searching for cameras near Jeju Airport...")
found = False
for item in data:
    lat = float(item.get('lat', 0))
    lng = float(item.get('lng', 0))
    
    if 33.0 < lat < 34.0 and 126.0 < lng < 127.0: # Filter for Jeju Island first
        dist = haversine(TARGET_LAT, TARGET_LNG, lat, lng)
        if dist < 2.0: # Within 2km
            print(f"Option: {item['name']} (Type: {item['source']}, ID: {item['id']}, Dist: {dist:.2f}km)")
            found = True

if not found:
    print("No cameras found within 2km of Jeju Airport.")
