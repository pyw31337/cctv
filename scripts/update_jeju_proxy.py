
import json

DATA_FILE = "cctv_data.json"
# Placeholder IP - User must replace this on their server or via env var if the frontend supports it.
# Ideally, the frontend should have a config. But for now, we edit the data.
# Since I don't know the IP, I will use a clearer placeholder.
PROXY_BASE = "http://YOUR_ORACLE_SERVER_IP:8080/jeju"

def main():
    print("Updating Jeju Streams to use Oracle Proxy...")
    
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    updated_count = 0
    
    for item in data:
        if item.get('source') == 'JEJU':
            # Construct proxy URL
            # Use original_id or id (w/o prefix if needed, but the server handles prefix stripping)
            # Server expects ?id=...
            # We use the item['id'] usually.
            
            # Check if already proxied (avoid double proxying if re-run)
            current_url = item.get('url', '')
            if PROXY_BASE in current_url:
                continue
                
            # Update to proxy
            # We keep the ID as is. Server logic: cctv_id.replace("JEJU_", "")
            # So passing "JEJU_C39" is fine.
            new_url = f"http://158.179.194.163:8080/jeju?id={item['id']}"
            
            item['url'] = new_url
            # Add tag to indicate it's proxied
            tags = item.get('tags', [])
            if "oracle_proxy" not in tags:
                tags.append("oracle_proxy")
            item['tags'] = tags
            
            updated_count += 1
    
    if updated_count > 0:
        print(f"Updated {updated_count} Jeju streams to point to {PROXY_BASE}")
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Done. IMPORTANT: You must replace YOUR_ORACLE_SERVER_IP with your actual server IP in cctv_data.json!")
    else:
        print("No Jeju streams found or all already updated.")

if __name__ == "__main__":
    main()
