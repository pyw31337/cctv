
import requests
import xml.etree.ElementTree as ET
import time

def scan_jindo():
    print("Scanning UTIC IDs E901100 - E901150 for '진도'...")
    
    # Base URL for metadata
    base_url = "http://www.utic.go.kr/guide/cctvOpenData.do"
    
    found = False
    for i in range(1100, 1151):
        cid = f"E90{i}"
        try:
            params = {"key": "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"}
            # The openData endpoint returns a list (usually XML or JSON). 
            # But here we want query by ID? 
            # Actually UTIC API `getCctvInfoById.do` is not public/documented well?
            # The standard way is `cctvOpenData.do` gives the whole list.
            # But fetching the whole list is heavy.
            # Let's try `openDataCctvStream.jsp` and check the HTML title? No, that's video player.
            
            # Let's look at `collect_cctv_data.py`'s `fetch_cctv_details`.
            # It likely iterates XML.
            # I don't have a direct "ID -> Name" API.
            # I have to re-fetch the XML list? 
            # Or assume the ranges are in the XML list.
            
            # Use `openDataCctvStream.jsp` with `kind=1` and parsing the response?
            # The response HTML usually contains `<title>` with the CCTV Name?
            # Or just check if the ID works?
            
            # Better approach:
            # We suspect it's in the E9011xx range. 
            # Let's search the `cctv_data_pre_audit_v2.json` to see if OTHER Jindo streams shifted by a constant offset?
            # Jindo Town (E901115) -> ?
            pass

        except Exception as e:
            print(f"Error {cid}: {e}")
            
    # Actually, easiest way is to use the existing `collect_cctv_data.py` logic but specifically for this range?
    # Or just fetch the main XML list (it's one big file) and grep it?
    # XML url: http://www.utic.go.kr/guide/cctvOpenData.do?key=...
    
    res = requests.get(base_url, params={"key": "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"})
    if res.status_code != 200:
        print("Failed to fetch Master List")
        return

    root = ET.fromstring(res.content)
    # Iterate all items
    for item in root.findall("record"):
        cctvname = item.find("cctvname").text
        cctvid = item.find("cctvid").text
        
        if "진도" in cctvname and "터미널" in cctvname:
            print(f"MATCH FOUND!")
            print(f"  Name: {cctvname}")
            print(f"  ID: {cctvid}")
            print(f"  URL: {item.find('cctvurl').text}")
            return

    print("Scan complete. Not found in master list??")

if __name__ == "__main__":
    scan_jindo()
