import requests
import json
import time
import re

class GeocodeHelper:
    """
    Utility to resolve Lng/Lat from names or addresses using Naver Map search API.
    """
    def __init__(self):
        self.search_url = "https://map.naver.com/v5/api/search/instant-search"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://map.naver.com/"
        }

    def geocode(self, query):
        """
        Takes a query (name or address) and returns (lat, lng) or None.
        """
        if not query:
            return None
            
        # Try multiple query variations
        queries_to_try = [query]
        if " CCTV" in query:
            queries_to_try.append(query.replace(" CCTV", ""))
        
        # Remove suffixes like (1), (2)
        base_query = re.sub(r' \(\d+\)', '', query)
        if base_query not in queries_to_try:
            queries_to_try.append(base_query)

        for q in queries_to_try:
            try:
                print(f"[Geocoder] Searching for: {q}")
                params = {
                    "query": q,
                    "display": 5,
                    "start": 1,
                    "sort": "random"
                }
                resp = requests.get(self.search_url, params=params, headers=self.headers, timeout=10)
                if resp.status_code != 200:
                    print(f"[Geocoder] Error: {resp.status_code}")
                    continue
                    
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    continue
                    
                item = items[0]
                try:
                    raw_x = str(item.get("mapx", "0"))
                    raw_y = str(item.get("mapy", "0"))
                    
                    if len(raw_x) > 6:
                        lng = float(raw_x) / 1e7
                        lat = float(raw_y) / 1e7
                    else:
                        lng = float(raw_x)
                        lat = float(raw_y)
                except:
                    continue
                
                # Basic bounds check for South Korea
                if 33 < lat < 43 and 124 < lng < 132:
                    return (lat, lng)
                    
            except Exception as e:
                print(f"[Geocoder] Error searching {q}: {e}")
                continue
        
        return None

if __name__ == "__main__":
    # Test
    geo = GeocodeHelper()
    print(geo.geocode("인천 신포사거리"))
