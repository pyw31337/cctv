
import os
import requests
import json

class GangwonCollector:
    """
    Gangwon Province Collector (Gangneung ITS etc).
    API: Gangneung ITS API, SK Open API etc. 
    Requires: Service Key
    """
    def __init__(self):
        # Gangneung ITS API URL (Example)
        self.api_url = "http://openapi.gn.go.kr/cctv/list" 
        self.api_key = os.environ.get("GANGWON_API_KEY", "")

    def fetch_data(self):
        if not self.api_key:
            print("[Gangwon] No API Key provided. Skipping Gangwon collection.")
            return []

        print("[Gangwon] Fetching CCTV data...")
        params = {
            "key": self.api_key,
            "type": "json"
        }
        
        try:
            response = requests.get(self.api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                # Todo: Parse JSON response
                # data = response.json()
                print(f"[Gangwon] Response received (Length: {len(response.text)})")
                return []
            else:
                print(f"[Gangwon] Error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[Gangwon] Error fetching data: {e}")
            return []

    def normalize_data(self, raw_data):
        normalized = []
        # Mapping logic here
        return normalized
