import json
import re

def migrate():
    input_file = 'cctv_data.json'
    output_file = 'cctv_data.json'
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    count = 0
    for item in data:
        cctv_id = item.get('id', '')
        url = item.get('url', '')
        direct_url = item.get('directUrl', '')
        
        # Check for Paju IDs
        if cctv_id.startswith('L12'):
            stream_id = None
            
            # Try to find 'id=cctv_XX' or 'cctv_XX' in url or directUrl or elsewhere
            search_text = json.dumps(item)
            match = re.search(r'id=(cctv_\d+)', search_text)
            if not match:
                match = re.search(r'media/(cctv_\d+)', search_text)
            if not match:
                # Some might just have the stream ID in a field?
                # Let's try cctv_XX pattern anywhere
                match = re.search(r'(cctv_\d+)', search_text)
                
            if match:
                stream_id = match.group(1)
                
            if stream_id:
                new_url = f"https://trafficcctv.paju.go.kr/live/{stream_id}.stream/playlist.m3u8"
                
                # Update url if it was a GITS IP or if it was a UTIC JSP URL (to make it faster)
                if '211.57.45.101' in url or 'utic.go.kr' in url:
                    item['url'] = new_url
                    count += 1
                
                # Update directUrl if it exists
                if direct_url:
                    item['directUrl'] = new_url
                    count += 1
                else:
                    item['directUrl'] = new_url
                    count += 1
                
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Migrated {count} Paju CCTV URLs.")

if __name__ == "__main__":
    migrate()
