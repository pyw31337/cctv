
import json

CUR_FILE = "cctv_data.json"

def main():
    print("Applying Mixed Fix: Restore Guri (Direct) & Revert Wangsvuk (Wrapper)...")
    
    with open(CUR_FILE, "r") as f:
        data = json.load(f)
        
    updated = 0
    for item in data:
        # 1. Guri Wangsukcheon (L933066) -> Force kind=KB (Restoration)
        if "구리 왕숙천" in item['name']:
            # The Pre-Audit URL (from debug_guri_pre.py):
            # https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?...&kind=KB&cctvip=9974
            target_url = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI&cctvid=L933067&cctvName=%EA%B5%AC%EB%A6%AC+%EC%99%95%EC%88%99%EC%B2%9C&kind=KB&cctvip=9974"
            
            if item['url'] != target_url:
                print(f"Fixing Guri: {item['name']}")
                item['url'] = target_url
                tags = item.get('tags', [])
                if "direct_source" not in tags: tags.append("direct_source")
                item['tags'] = tags
                updated += 1
                
        # 2. Namyangju Wangsvuk Bridge (E600011) -> Force Wrapper (Revert)
        # Because direct HLS (lw.hrfco.go.kr) is reported broken by user
        if "남양주시(왕숙교)" in item['name']:
            target_url = "https://hrfco.go.kr/sumun/cctvPopup.do?Obscd=111020"
            
            if item['url'] != target_url:
                print(f"Reverting Wangsvuk: {item['name']}")
                item['url'] = target_url
                # Remove direct_source tag if reverting to wrapper? 
                # Or keep it but protected? 
                # Let's keep it protected so sync doesn't mess it up again, 
                # but technically it is NOT direct. 
                # Actually, let's remove the tag so it behaves like a normal UTIC/HRFCO link?
                # No, user wants STABILITY. Protect it as is.
                tags = item.get('tags', [])
                if "direct_source" in tags: tags.remove("direct_source") 
                # Wait, if I remove tag, sync might overwrite it? 
                # But sync overwrites with UTIC wrapper... which IS this URL.
                # So removing tag is safe.
                item['tags'] = tags
                updated += 1

    if updated > 0:
        with open(CUR_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Applied {updated} fixes.")
    else:
        print("No changes needed.")

if __name__ == "__main__":
    main()
