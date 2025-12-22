import json
import math

def get_distance(lat1, lng1, lat2, lng2):
    try:
        lat1, lng1, lat2, lng2 = map(float, [lat1, lng1, lat2, lng2])
    except ValueError:
        return float('inf')
        
    R = 6371000 # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def merge_data():
    print("Loading data...")
    try:
        with open('cctv_data.json', 'r') as f:
            utic_data = json.load(f)
    except FileNotFoundError:
        utic_data = []
        
    try:
        with open('ntic_data.json', 'r') as f:
            ntic_data = json.load(f)
    except FileNotFoundError:
        ntic_data = []
        
    print(f"UTIC: {len(utic_data)}, NTIC: {len(ntic_data)}")
    
    merged = []
    # Add all NTIC data first (High quality HLS)
    for item in ntic_data:
        item['source'] = 'NTIC'
        merged.append(item)
        
    # Add UTIC data if not duplicate
    added_utic = 0
    skipped_utic = 0
    
    for u_item in utic_data:
        is_duplicate = False
        
        # Check against NTIC data
        for n_item in ntic_data:
            dist = get_distance(u_item['lat'], u_item['lng'], n_item['lat'], n_item['lng'])
            if dist < 100: # 100m radius duplicate check
                is_duplicate = True
                break
        
        if not is_duplicate:
            u_item['source'] = 'UTIC'
            merged.append(u_item)
            added_utic += 1
        else:
            skipped_utic += 1
            
    print(f"Merged Total: {len(merged)}")
    print(f"Added UTIC: {added_utic}, Skipped UTIC (Duplicate): {skipped_utic}")
    
    with open('cctv_data.json', 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        
    print("Saved to cctv_data.json")

if __name__ == '__main__':
    merge_data()
