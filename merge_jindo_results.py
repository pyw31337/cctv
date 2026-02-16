import json
import os

DATA_FILE = "cctv_data.json"
RESULTS_FILE = "jindo_survey_results.json"
UTIC_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"

def main():
    if not os.path.exists(RESULTS_FILE):
        print(f"Error: {RESULTS_FILE} not found.")
        return

    with open(RESULTS_FILE, "r") as f:
        results = json.load(f)

    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Create a lookup for existing items
    existing_map = {item["id"]: item for item in data}
    
    updated_count = 0
    added_count = 0
    
    for res in results:
        if res["status"] != "OK":
            continue
            
        cid = res["id"]
        name = res["name"]
        
        # Determine cctvip from parsed IP if possible, or use the one from the survey
        # In the survey script, we parsed the IP using regex from ConnectSrv.
        # However, the full URL requires many params. 
        # For UTIC, we can just regenerate the URL with the ID and Key.
        
        # Use a standardized URL format for UTIC
        # Note: cctvName in URL is often double-encoded in the original data, 
        # but the simple encoded version usually works or is ignored if cid is present.
        import urllib.parse
        encoded_name = urllib.parse.quote(name)
        new_url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={UTIC_KEY}&cctvid={cid}&cctvName={encoded_name}&kind=Z3"

        if cid in existing_map:
            # Update existing if needed
            existing_map[cid]["url"] = new_url
            existing_map[cid]["status"] = "active"
            # Ensure name is not SCAN_xxx
            if "SCAN_" not in name:
                existing_map[cid]["name"] = name
            updated_count += 1
        else:
            # Add new
            new_item = {
                "id": cid,
                "name": name if "SCAN_" not in name else f"진도군 CCTV ({cid})",
                "source": "UTIC",
                "status": "active",
                "url": new_url,
                "backup_urls": [],
                "lat": 34.48, # Approximate for Jindo if unknown
                "lng": 126.26
            }
            data.append(new_item)
            added_count += 1

    # Save updated data
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    print(f"Merge completed:")
    print(f" - Updated: {updated_count}")
    print(f" - Added: {added_count}")
    print(f" - Total Jindo Items: {len([item for item in data if '진도' in item.get('name', '')])}")

if __name__ == "__main__":
    main()
