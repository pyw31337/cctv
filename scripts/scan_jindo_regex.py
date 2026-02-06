
import requests
import re

def scan_jindo_regex():
    print("Scanning UTIC Master List for '진도터미널' via Regex...")
    
    url = "http://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
    try:
        res = requests.get(url, timeout=30)
        content = res.text
        
        # Look for the block containing "진도터미널"
        # The XML structure is <record><cctvname>...</cctvname><cctvurl>...</cctvurl>...</record>
        # We want the ID associated with it. <cctvid>ID</cctvid>
        
        print(f"Downloaded {len(content)} chars.")
        
        # Regex to find records with "진도" and "터미널"
        # We'll split by <record> tag to make it easier
        records = content.split("<record>")
        
        found_count = 0
        for r in records:
            if "진도" in r and "터미널" in r:
                # Extract details
                name_match = re.search(r"<cctvname>(.*?)</cctvname>", r)
                id_match = re.search(r"<cctvid>(.*?)</cctvid>", r)
                url_match = re.search(r"<cctvurl>(.*?)</cctvurl>", r)
                
                if name_match and id_match:
                    name = name_match.group(1)
                    cid = id_match.group(1)
                    url = url_match.group(1) if url_match else "N/A"
                    
                    print(f"MATCH: {name}")
                    print(f"  ID: {cid}")
                    print(f"  URL: {url}")
                    found_count += 1
                    
        if found_count == 0:
            print("No match found for '진도 + 터미널'.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    scan_jindo_regex()
