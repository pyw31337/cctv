import json
import os

# Priority Configuration (Lower value = Higher Priority)
PRIORITY = {
    'KBS': 1,       # Best Quality (Direct HLS)
    'ULLEUNG': 1,   # Best Quality (Direct HLS)
    ' NOWJEJU': 1,   # Best Quality (Direct HLS)
    'GIGAEYES': 1,  # Best Quality (YouTube)
    'YT_CUSTOM': 1, # Best Quality (YouTube)
    'SPATIC': 1,    # Best Quality (Police HLS)
    'GITS': 2,      # Direct HLS
    'TOPIS': 2,     # Direct HLS
    'DAEJEON': 2,   # Direct HLS
    'ULSAN': 2,     # Direct HLS
    'DAEGU': 2,     # Direct HLS
    'SEJONG': 2,    # Direct HLS
    'GWANGJU': 2,   # Direct HLS
    'FITIC': 1,
    'ICITS': 1,
    'GGEX': 1,
    'GOYANG': 1,
    'CHUNGJU': 1,
    'KNPS': 1,
    'BUSAN_ITS': 3, 
    'INCHEON_ITS': 3,
    'DAEJEON_ITS': 3,
    'JEJU': 3,      # Proxy'd HLS
    'GANGWON': 3,   # Proxy'd HLS
    'UTIC': 5,      # Fallback (JSP)
    'NTIC': 6,      # Fallback (JSP)
}

def organize_streams(filepath):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for item in data:
        # 1. Collect all available URLs (main + backups)
        all_options = []
        
        # Add main
        main_source = item.get('source', 'UNKNOWN')
        main_url = item.get('url', '')
        if main_url:
            all_options.append({
                'source': main_source,
                'url': main_url,
                'priority': PRIORITY.get(main_source, 99)
            })
        
        # Add backups
        for backup in item.get('backup_urls', []):
            if isinstance(backup, dict):
                src = backup.get('source', 'UNKNOWN')
                url = backup.get('url', '')
            else:
                # Handle cases where backup might be just a URL string
                src = 'UNKNOWN'
                url = str(backup)
                
            if url:
                all_options.append({
                    'source': src,
                    'url': url,
                    'priority': PRIORITY.get(src, 99)
                })
            
        if not all_options:
            continue

        # 2. Sort by priority
        # Tie-break: prefer HLS over JSP/other
        def sort_key(x):
            url_lower = x['url'].lower()
            hls_bonus = 0 if (".m3u8" in url_lower or "/live/" in url_lower) else 0.5
            return (x['priority'] + hls_bonus)

        all_options.sort(key=sort_key)
        
        # 3. Deduplicate URLs
        seen_urls = set()
        unique_options = []
        for opt in all_options:
            if opt['url'] not in seen_urls:
                unique_options.append(opt)
                seen_urls.add(opt['url'])
        
        # 4. Assign Main Stream
        main = unique_options[0]
        item['url'] = main['url']
        item['source'] = main['source']
        
        # 5. Assign Backups (Sub1, Sub2, Sub3...)
        backups = []
        for i, opt in enumerate(unique_options[1:], 1):
            backups.append({
                'label': f"Sub{i}",
                'source': opt['source'],
                'url': opt['url']
            })
        item['backup_urls'] = backups

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Organized streams for {len(data)} cameras in {filepath}")

if __name__ == "__main__":
    organize_streams("cctv_data.json")
