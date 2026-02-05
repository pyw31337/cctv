
import json

DATA_FILE = "cctv_data.json"

def main():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    blocked_count = 0
    
    for item in data:
        # Identify the RTSP streams we just converted
        if item.get("source") == "UTIC_RTSP_Proxy":
            # Mark as inactive clearly
            item["status"] = "inactive"
            item["note"] = "Inactive: RTSP Geo-blocked (Requires Korea IP)"
            blocked_count += 1
            
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Marked {blocked_count} RTSP streams as inactive (Geo-blocked).")
    print("Hwaseong/Bucheon SSL streams remain ACTIVE.")

if __name__ == "__main__":
    main()
