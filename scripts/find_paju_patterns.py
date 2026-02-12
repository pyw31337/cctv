import json
import re

def main():
    with open('cctv_data.json', 'r') as f:
        data = json.load(f)
    
    paju_cctvs = []
    # Paju IDs often start with L12 (UTIC base)
    # or have names associated with Paju
    for item in data:
        url = item.get('url', '')
        # Check if it uses the old GITS IP
        is_paju_ip = '211.57.45.101' in url
        
        # Check by ID prefix (L12 is Paju in UTIC)
        is_paju_id = item.get('id', '').startswith('L12')
        
        if is_paju_ip or is_paju_id:
            paju_cctvs.append(item)
            
    print(f"Total potential Paju CCTVs: {len(paju_cctvs)}")
    
    # Sample some
    for item in paju_cctvs[:10]:
        print(f"Name: {item['name']}, ID: {item['id']}, URL: {item['url']}")
        
    # Categorize by IP
    ips = {}
    for item in paju_cctvs:
        url = item.get('url', '')
        match = re.search(r'https?://([^/]+)', url)
        if match:
            ip = match.group(1)
            ips[ip] = ips.get(ip, 0) + 1
            
    print("\nIP Distribution:")
    for ip, count in ips.items():
        print(f"  {ip}: {count}")

if __name__ == "__main__":
    main()
