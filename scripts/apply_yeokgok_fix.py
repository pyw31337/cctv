
import json

CUR_FILE = "cctv_data.json"
# Original User URL:
# https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI&cctvid=L030049&cctvName=%25EC%2597%25AD%25EA%25B3%25A1%25EA%25B3%25A0%25EA%25B0%2580%25EC%2582%25AC%25EA%25B1%25B0%25EB%25A6%25AC&kind=O&cctvip=TM098TC07P&cctvch=6&id=undefined&cctvpasswd=undefined&cctvport=undefined
# We need to ensure we use this EXACT parameter set.

def main():
    print("Applying User-Provided URL for Yeokgok...")
    
    with open(CUR_FILE, "r") as f:
        data = json.load(f)
        
    updated = 0
    for item in data:
        if "역곡고가사거리" in item['name']:
            target_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI&cctvid=L030049&cctvName=%25EC%2597%25AD%25EA%25B3%25A1%25EA%25B3%25A0%25EA%25B0%2580%25EC%2582%25AC%25EA%25B1%25B0%25EB%25A6%25AC&kind=O&cctvip=TM098TC07P&cctvch=6&id=undefined&cctvpasswd=undefined&cctvport=undefined"
            
            if item['url'] != target_url:
                print(f"Updating: {item['name']}")
                print(f"  WAS: {item['url']}")
                print(f"  NOW: {target_url}")
                item['url'] = target_url
                
                # Protect it
                tags = item.get('tags', [])
                if "direct_source" not in tags: tags.append("direct_source")
                item['tags'] = tags
                updated += 1
            else:
                print("URL already correct.")

    if updated > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Applied {updated} fixes.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    main()
