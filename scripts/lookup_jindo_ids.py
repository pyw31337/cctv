
import requests
import re

def lookup_ids():
    print("Looking up IDs E901114 and E901120...")
    
    url = "http://www.utic.go.kr/guide/cctvOpenData.do?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
    try:
        res = requests.get(url, timeout=30)
        content = res.text
        records = content.split("<record>")
        
        targets = ["E901114", "E901120"]
        
        for r in records:
            for t in targets:
                if f"<cctvid>{t}</cctvid>" in r:
                    name_match = re.search(r"<cctvname>(.*?)</cctvname>", r)
                    print(f"MATCH ID: {t}")
                    print(f"  Name: {name_match.group(1) if name_match else 'Unknown'}")
                    # Print raw record extract to see full details
                    print(r[:200] + "...")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    lookup_ids()
