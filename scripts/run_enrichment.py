import json
import time
from utils.geocoder import GeocodeHelper

def run_enrichment():
    try:
        with open('cctv_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    geo = GeocodeHelper()
    count = 0
    missing = [i for i in data if not i.get('lat') or i['lat'] == 0]
    print(f"Total missing coordinates: {len(missing)}")
    
    # Process small batch to avoid API issues
    for i in missing[:30]:
        res = geo.geocode(i['name'])
        if not res and i.get('address'):
            res = geo.geocode(i['address'])
            
        if res:
            i['lat'], i['lng'] = res
            count += 1
            print(f"Resolved [{i['name']}]: {res}")
            time.sleep(1)
            
    if count > 0:
        with open('cctv_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
    print(f"Resolved {count} coordinates in this pass.")

if __name__ == "__main__":
    run_enrichment()
