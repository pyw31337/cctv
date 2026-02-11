import requests
import json

LIST_API = "https://www.jejuits.go.kr/jido/getCurFeatures.do"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.jejuits.go.kr/jido/mainView.do",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}

def debug_jeju_api():
    payload = {
        "layerNm": "CCTV",
        "searchWord": "",
        "swLat": "33.1",
        "swLng": "126.1",
        "neLat": "33.6",
        "neLng": "127.0",
        "maplevel": "11",
        "DEVICE_KIND": "CCTV"
    }

    try:
        resp = requests.post(LIST_API, data=payload, headers=HEADERS, timeout=10, verify=False)
        items = resp.json()
        if items:
            print(json.dumps(items[0], indent=4, ensure_ascii=False))
            print(f"Total items: {len(items)}")
        else:
            print("No items found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_jeju_api()
