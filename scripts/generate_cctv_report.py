import json
import re
from collections import defaultdict

DATA_FILE = "cctv_data.json"

def get_region_utic(name):
    # Try to extract "City" from "City(Location)"
    match = re.match(r'^([가-힣]+)(?:시|군|구)?\(', name)
    if match:
        return match.group(1)
    
    # Fallback: First 2 chars of name
    return name[:2] if len(name) >= 2 else "Method"

def main():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    stats = defaultdict(lambda: {'total': 0, 'secured': 0})
    
    # Pre-defined regions for better sorting
    # We will aggregate data into: Source -> Region -> counts
    
    for item in data:
        source = item.get('source', 'Unknown')
        name = item.get('name', 'Unknown')
        url = item.get('url', '')
        
        is_secured = False
        # Secured logic: m3u8, mp4, or specific direct IP patterns
        if '.m3u8' in url or '.mp4' in url:
            is_secured = True
        elif '211.57.45.101' in url or '210.95.12.126' in url: # Known direct IP patterns
            is_secured = True
            
        # Determine Region
        region = "Other"
        if source == 'UTIC':
            # Extract city name
            # Common formats: "서울시(name)", "가평군(name)", "제주(name)"
            # Simplify to just the city name
            if '(' in name:
                region = name.split('(')[0]
                # Remove suffix like 시, 군 if present for grouping?
                # Actually keeping full name like '서울시' is better for display
            else:
                region = name[:2] # Fallback
                
        elif source == 'NTIC':
            region = "National Highway" # ITS/NTIC is generally highways
            
        group_key = (source, region)
        stats[group_key]['total'] += 1
        if is_secured:
            stats[group_key]['secured'] += 1

    # Formatting Output
    print(f"### CCTV Stream Securitization Status Report")
    print(f"| Source | Region | Total | Secured (Direct) | Unsecured (Popup) | Rate (%) |")
    print(f"|---|---|---|---|---|---|")

    # Sort logic: Source (NTIC first, then UTIC), then Total Count desc
    sorted_keys = sorted(stats.keys(), key=lambda k: (k[0], -stats[k]['total']))
    
    grand_total = 0
    grand_secured = 0
    
    # Subtotals
    utic_total = 0
    utic_secured = 0
    ntic_total = 0
    ntic_secured = 0

    for source, region in sorted_keys:
        s = stats[(source, region)]
        total = s['total']
        secured = s['secured']
        unsecured = total - secured
        rate = (secured / total * 100) if total > 0 else 0
        
        grand_total += total
        grand_secured += secured
        
        if source == 'UTIC':
            utic_total += total
            utic_secured += secured
        elif source == 'NTIC':  # In our data, source might be 'NTIC' or 'ITS'?? Code uses 'NTIC'
             ntic_total += total
             ntic_secured += secured
        
        # Only print significant rows or consolidate? 
        # User asked for regions. UTIC has many municipalities.
        # Let's print top 20 and group the rest? Or print all if not too huge.
        # UTIC has ~50 regions. It fits in a long table.
        
        print(f"| {source} | {region} | {total} | {secured} | {unsecured} | {rate:.1f}% |")

    # Summary Rows
    print(f"|---|---|---|---|---|---|")
    print(f"| **NTIC Total** | | **{ntic_total}** | **{ntic_secured}** | **{ntic_total - ntic_secured}** | **{(ntic_secured/ntic_total*100 if ntic_total else 0):.1f}%** |")
    print(f"| **UTIC Total** | | **{utic_total}** | **{utic_secured}** | **{utic_total - utic_secured}** | **{(utic_secured/utic_total*100 if utic_total else 0):.1f}%** |")
    print(f"| **GRAND TOTAL** | | **{grand_total}** | **{grand_secured}** | **{grand_total - grand_secured}** | **{(grand_secured/grand_total*100 if grand_total else 0):.1f}%** |")

if __name__ == "__main__":
    main()
