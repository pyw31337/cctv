class YoutubeCustomCollector:
    """
    Collector for specific user-requested YouTube live streams.
    """
    
    STREAMS = [
        {"id": "uHdl_9hsHqw", "name": "부산 해운대해수욕장", "lat": 35.1587, "lng": 129.1603, "addr": "부산광역시 해운대구 우동 해운대해수욕장"},
        {"id": "ol5_4JHHfTs", "name": "부산 광안리해수욕장 & 광안대교", "lat": 35.1531, "lng": 129.1189, "addr": "부산광역시 수영구 광안해변로 219 (광안리해수욕장)"},
        {"id": "jF8-FvIj4-E", "name": "서울 한강 (UN빌리지 조망)", "lat": 37.5345, "lng": 127.0105, "addr": "서울특별시 용산구 한남동 UN빌리지 (한강 조망)"}
    ]

    def collect(self):
        print(f"Collecting Custom YouTube data ({len(self.STREAMS)} streams)...")
        results = []
        for s in self.STREAMS:
            item = {
                "id": f"YT_CUSTOM_{s['id']}",
                "name": f"[YouTube] {s['name']}",
                "lat": s['lat'],
                "lng": s['lng'],
                "url": f"https://www.youtube.com/watch?v={s['id']}",
                "source": "YT_CUSTOM",
                "status": "active",
                "address": s['addr'],
                "backup_urls": []
            }
            results.append(item)
        
        print(f"Successfully collected {len(results)} custom YouTube streams.")
        return results
