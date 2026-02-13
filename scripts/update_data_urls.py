import json
import os

def update_daejeon_urls(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    count = 0
    for item in data:
        if item.get('source') == 'DAEJEON_ITS' and 'chunklist.m3u8' not in item.get('url', ''):
            cctv_id = item.get('original_id') or item.get('id', '').replace('DAEJEON_', '')
            
            # Map based on ID (rough heuristic if cctvUrl is missing in JSON)
            # Based on browser research earlier: CTV0008 (.101) -> 01, CTV0071 (.102) -> 02
            # Let's try to detect from the existing list or just default/try both in sentinel
            # But the JSON needs a specific URL. Default to 01 and sentinel will check both.
            
            stream_id = cctv_id
            if cctv_id.startswith("CCTV"):
                num = cctv_id[4:]
                stream_id = f"CTV{num.zfill(4)}"
            
            item['url'] = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/chunklist.m3u8"
            if 'urlType' in item:
                del item['urlType']
            count += 1
            
    if count > 0:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Updated {count} Daejeon URLs.")

if __name__ == "__main__":
    update_daejeon_urls("cctv_data.json")
