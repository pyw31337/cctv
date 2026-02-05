
import json
from collections import Counter

DATA_FILE = 'cctv_data.json'

def main():
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        
    total = len(data)
    active = sum(1 for d in data if d.get('status') == 'active')
    inactive = sum(1 for d in data if d.get('status') == 'inactive')
    
    # Sources
    sources = Counter(d.get('source', 'Unknown') for d in data)
    
    # Active vs Inactive per Source
    source_stats = {}
    for d in data:
        s = d.get('source', 'Unknown')
        st = d.get('status', 'active')
        if s not in source_stats:
            source_stats[s] = {'active': 0, 'inactive': 0}
        source_stats[s][st] += 1
    
    print("=== Video Database Report ===")
    print(f"Total Streams: {total}")
    print(f"Active: {active} ({active/total*100:.1f}%)")
    print(f"Inactive: {inactive} ({inactive/total*100:.1f}%)")
    
    print("\n[Source Breakdown]")
    for s, count in sources.most_common():
        stats = source_stats[s]
        print(f"- {s}: {count} (Active: {stats['active']}, Inactive: {stats['inactive']})")
        
    # Check for specific recovered tags
    recovered = sum(1 for d in data if 'Recovered' in d.get('source', ''))
    print(f"\nTotal Recovered Streams: {recovered}")
    
    # Cheonan/Flood specifics
    cheonan = sum(1 for d in data if 'cheonan' in d.get('url', ''))
    flood = sum(1 for d in data if 'geumriver' in d.get('url', ''))
    print(f"- Cheonan (Wowza): {cheonan}")
    print(f"- Flood Control (Geum): {flood}")

if __name__ == "__main__":
    main()
