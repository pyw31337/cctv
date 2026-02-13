import json
import os

def final_sync(filepath):
    if not os.path.exists(filepath):
        print("File not found.")
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    g_count = 0
    d_count = 0
    
    for item in data:
        # Gangwon Sync
        if item.get('source') == 'GANGWON' and 'gangneung_player.html' in item.get('url', ''):
            if not item['url'].startswith('http'):
                item['url'] = "https://its.gn.go.kr/popup/" + item['url']
                g_count += 1
        
        # Daejeon Sync
        if item.get('source') == 'DAEJEON_ITS' and 'chunklist.m3u8' not in item.get('url', ''):
            cctv_id = item.get('id', '').replace('DAEJEON_', '')
            stream_id = cctv_id
            if cctv_id.startswith("CCTV"):
                num = cctv_id[4:]
                stream_id = f"CTV{num.zfill(4)}"
            
            # Use 01 as default, sentinel will try both
            item['url'] = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/chunklist.m3u8"
            d_count += 1
            
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"Synced {g_count} Gangwon and {d_count} Daejeon URLs.")

if __name__ == "__main__":
    final_sync("cctv_data.json")
