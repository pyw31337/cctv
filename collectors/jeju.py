
import os
import requests
import json

class JejuCollector:
    """
    Jeju Special Self-Governing Province Collector.
    API: Public Data Portal (Traffic Facility Information)
    Requires: Service Key
    """
    def __init__(self):
        # Placeholder endpoint - needs verification from data.go.kr documentation
        self.api_url = "http://api.jeju.go.kr/rest/JejuCctvInfoService/getCctvInfo" 
        self.api_key = os.environ.get("JEJU_API_KEY", "")

    def fetch_data(self):
        if not self.api_key:
            print("[Jeju] No API Key provided. Skipping Jeju collection.")
            return []

        print("[Jeju] Fetching CCTV data...")
        params = {
            "serviceKey": self.api_key,
            "type": "json"
        }
        
        try:
            response = requests.get(self.api_url, params=params, timeout=30)
            
            if response.status_code == 200:
                # Todo: Parse JSON response
                # data = response.json()
                print(f"[Jeju] Response received (Length: {len(response.text)})")
                return []
            else:
                print(f"[Jeju] Error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[Jeju] Error fetching data: {e}")
            return []

    def normalize_data(self, raw_data):
        normalized = []
        # Mapping logic here
        return normalized
