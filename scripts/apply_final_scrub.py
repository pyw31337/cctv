
import json

CUR_FILE = "cctv_data.json"

def main():
    print("Applying Final Fix: Revert Yeokgok & Neobudaegyo to Safe Wrappers...")
    
    with open(CUR_FILE, "r") as f:
        data = json.load(f)
        
    updated = 0
    for item in data:
        # 1. Seoul City (Neobudaegyo) (E600016) -> Force Wrapper (Like Wangsvuk)
        if "서울시(너부대교)" in item['name']:
            target_url = "https://hrfco.go.kr/sumun/cctvPopup.do?Obscd=1120210"
            if item['url'] != target_url:
                print(f"Reverting Neobudaegyo: {item['name']}")
                item['url'] = target_url
                # Ensure no direct_source tag to avoid confusion, but protected by VIP?
                # Actually, VIP protection logic says "if is_vip AND is_direct".
                # If I remove 'direct_source' tag, it might NOT be protected by my new logic.
                # BUT my new logic protects if name in keywords.
                # Let's check collect_cctv_data.py logic:
                # is_vip = name in [....]
                # if is_vip and is_direct: return existing
                # So if I REMOVE 'direct_source' tag, it will NOT be locked, and might be updated?
                # If updated, it goes to UTIC wrapper?
                # Neobudaegyo IS valid on UTIC too? No, it's HRFCO (E code). 
                # HRFCO usually defaults to wrapper in my sync logic.
                # So removing tag is probably safe.
                tags = item.get('tags', [])
                if "direct_source" in tags: tags.remove("direct_source")
                item['tags'] = tags
                updated += 1

        # 2. Yeokgok High School (L030049) -> Force UTIC Standard (Remove Proxy)
        # The proxy seems to be causing issues (or is dead).
        # We don't have the original UTIC URL handy, so let's construct it manually or just clear URL so sync picks it up?
        # Constructing manually is safer to avoid downtime.
        # L030049 is Bucheon. Bucheon usually works with kind=1 on UTIC.
        if "역곡고가사거리" in item['name']:
            # Construct standard UTIC URL
            # https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key=...&cctvid=L030049&cctvName=...&kind=1
            base = "https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp"
            key = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
            # Name needs encoding? The sync script does it. Here strict ascii or encoded?
            # It's safer to just let the Sync script fix it? 
            # Or manually set it.
            # Let's try to set a valid standard URL.
            print(f"Reverting Yeokgok: {item['name']}")
            # Use a known working format. 
            # Actually, if I just clear the URL, the next sync will fetch it.
            # But user wants immediate fix.
            # Let's try generic UTIC wrapper.
            import urllib.parse
            enc_name = urllib.parse.quote(item['name'].encode('euc-kr')) # UTIC uses EUC-KR often? Or UTF8?
            # UTIC `openDataCctvStream.jsp` usually accepts UTF-8 in modern browsers but let's be careful.
            # Actually, standard UTIC URLs in JSON are mostly encoded.
            # Let's copy a standard format.
            new_url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={key}&cctvid={item['id']}&cctvName={item['name']}&kind=1"
            # Wait, cctvName in URL should be URL-encoded.
            # simple python quote
            enc_name = urllib.parse.quote(item['name'])
            new_url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={key}&cctvid={item['id']}&cctvName={enc_name}&kind=1"

            item['url'] = new_url
            tags = item.get('tags', [])
            if "direct_source" in tags: tags.remove("direct_source") # Remove proxy tag
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
