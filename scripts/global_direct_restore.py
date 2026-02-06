
import json
import re

PRE_FILE = "cctv_data_pre_audit_v2.json"
CUR_FILE = "cctv_data.json"

# Patterns that indicate a "High Quality" or "Direct" source
# If a URL matches these, it should be preferred over a generic UTIC wrapper
DIRECT_INDICATORS = [
    r"cctv\.kt\.com",        # KT Direct
    r"rtsp://",              # RTSP
    r"\.mp4",                # MP4 File
    r"\.m3u8",               # HLS File (direct)
    r"lw\.hrfco\.go\.kr",    # Flood Control Direct
    r"211\.57\.45\.101",     # Namyangju IP
    r"kind=e",               # Paju/Special Paju Type?
    r"210\.99",              # Other common static IPs
    r":8080", r":1935",      # Common streaming ports
    r"cctvsec\.ktict\.co\.kr" # Secure Stream
]

def is_direct(url):
    if not url: return False
    for p in DIRECT_INDICATORS:
        if re.search(p, url):
            return True
    return False

def main():
    print("Starting GLOBAL Direct Source Restoration...")
    
    with open(PRE_FILE, "r") as f:
        pre_data = {item['id']: item for item in json.load(f)}
        
    with open(CUR_FILE, "r") as f:
        cur_data = json.load(f)
        cur_map = {item['id']: item for item in cur_data}
        
    restored_count = 0
    total_checked = 0
    
    for cid, pre_item in pre_data.items():
        pre_url = pre_item.get("url", "")
        
        # We only care if the OLD url was "Direct/Special"
        # OR if the user specifically complained about "kind=e" downgrades
        if is_direct(pre_url):
            total_checked += 1
            cur_item = cur_map.get(cid)
            
            if cur_item:
                cur_url = cur_item.get("url", "")
                
                # If current URL is different (and presumably "worse" / generic)
                if cur_url != pre_url:
                    # Special check: If both are UTIC, but params differ?
                    # E.g. kind=e vs kind=1
                    
                    print(f"Restoring {pre_item['name']} ({cid})")
                    print(f"  WAS: {pre_url}")
                    print(f"  NOW: {cur_url}")
                    
                    cur_item['url'] = pre_url
                    tags = cur_item.get('tags', [])
                    if "direct_source" not in tags: tags.append("direct_source")
                    cur_item['tags'] = tags
                    
                    restored_count += 1

    if restored_count > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(list(cur_map.values()), f, ensure_ascii=False, indent=2)
        print(f"\nGLOBAL RESTORE: Successfully restored {restored_count} streams.")
    else:
        print("No further direct streams found to restore.")

if __name__ == "__main__":
    main()
