import json

def analyze_data():
    try:
        with open('cctv_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"Total CCTVs: {len(data)}")
        
        # Simple bucket analysis
        regions = {
            "Seoul/Gyeonggi (37-38)": 0,
            "South (34-36)": 0,
            "Other": 0
        }
        
        for item in data:
            lat = float(item.get('lat', 0))
            if 37 <= lat <= 38:
                regions["Seoul/Gyeonggi (37-38)"] += 1
            elif 34 <= lat < 37:
                regions["South (34-36)"] += 1
            else:
                regions["Other"] += 1
                
        print(json.dumps(regions, indent=2))
        
        # Sample execution to check if valid
        if len(data) > 0:
            print(f"Sample: {data[0]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_data()
