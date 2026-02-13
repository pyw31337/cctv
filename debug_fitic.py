from collectors.fitic import FITICCollector
import json

def debug_fitic():
    print("Running FITIC Collector...")
    collector = FITICCollector()
    data = collector.fetch_data()
    print(f"Collected {len(data)} items.")
    
    # Find '신포사거리'
    target = next((x for x in data if "신포사거리" in x['name']), None)
    if target:
        print("Found target in FITIC data:")
        print(json.dumps(target, indent=2, ensure_ascii=False))
        
        # Load existing
        with open('cctv_data.json', 'r') as f:
            full_data = json.load(f)
            
        existing = next((x for x in full_data if "신포사거리" in x['name']), None)
        if existing:
            print("Found existing target in cctv_data.json:")
            print(json.dumps(existing, indent=2, ensure_ascii=False))
            
            # Compare coords
            lat_diff = abs(target['lat'] - existing['lat'])
            lng_diff = abs(target['lng'] - existing['lng'])
            print(f"Lat diff: {lat_diff}, Lng diff: {lng_diff}")
    else:
        print("Target '신포사거리' not found in FITIC data.")

if __name__ == "__main__":
    debug_fitic()
