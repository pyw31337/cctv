
import os
import requests
import json

class TopisCollector:
    """
    Seoul TOPIS (Transport Operation & Information Service) Collector.
    API: http://openapi.seoul.go.kr:8088/{KEY}/json/CCTVImgInfo/1/1000/
    Requires: Service Key
    """
    def __init__(self):
        # Default base URL, key will be inserted
        self.base_url = "http://openapi.seoul.go.kr:8088"
        self.api_key = os.environ.get("TOPIS_API_KEY", "4f78524242707977373765496c4d45")

    def fetch_data(self):
        if not self.api_key:
            print("[TOPIS] No API Key provided. Skipping TOPIS collection.")
            return []

        print("[TOPIS] Fetching CCTV data...")
        # Example: http://openapi.seoul.go.kr:8088/(key)/json/CCTVImgInfo/1/1000/
        url = f"{self.base_url}/{self.api_key}/json/CCTVImgInfo/1/1000/"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if "CCTVImgInfo" in data and "row" in data["CCTVImgInfo"]:
                    print(f"[TOPIS] Fetched {len(data['CCTVImgInfo']['row'])} items.")
                    return data["CCTVImgInfo"]["row"]
                else:
                    print("[TOPIS] No data in response or invalid format.")
                    return []
            else:
                print(f"[TOPIS] Error: {response.status_code}")
                return []
        except Exception as e:
            print(f"[TOPIS] Error fetching data: {e}")
            return []

    def normalize_data(self, raw_data):
        normalized = []
        for item in raw_data:
            # item keys: CCTVNAME, XCOORD, YCOORD, CCTVURL (check actual keys)
            # Need to verify actual response structure
            pass
        return normalized
