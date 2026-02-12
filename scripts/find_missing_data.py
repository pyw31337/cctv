import json

def main():
    try:
        with open('cctv_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        missing_latlng = []
        missing_address = []
        
        for item in data:
            # Check Lat/Lng
            if item.get('lat', 0.0) == 0.0 or item.get('lng', 0.0) == 0.0:
                missing_latlng.append(item)
                
            # Check Address
            addr = item.get('address', '').strip()
            if not addr:
                missing_address.append(item)

        print(f"Total Items: {len(data)}")
        print(f"Missing Lat/Lng: {len(missing_latlng)}")
        for item in missing_latlng:
            print(f" - {item['id']} ({item['name']})")
            
        print(f"Missing Address: {len(missing_address)}")
        if len(missing_address) > 0:
            print("Sample Missing Address items:")
            for item in missing_address[:20]:
                print(f" - {item['id']} ({item['name']})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
