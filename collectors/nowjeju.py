import requests

class NowJejuCollector:
    """
    Collector for NowJejuplus (nowjejuplus.com) CCTV streams.
    Provides 16 high-quality Jeju coastal and Hallasan streams.
    """
    
    PROXY_BASE = "https://158.179.194.163.sslip.io/proxy"
    
    LOCATIONS = {
        "15": {"name": "제주국제공항", "lat": 33.5111, "lng": 126.4928, "url": "http://123.140.197.51/stream/33/play.m3u8", "addr": "제주특별자치도 제주시 공항로 2"},
        "1": {"name": "용두암 해안", "lat": 33.5169, "lng": 126.5169, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100003/0/1", "addr": "제주특별자치도 제주시 용두암길 15"},
        "2": {"name": "탑동 해안", "lat": 33.5186, "lng": 126.5230, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100001/0/1", "addr": "제주특별자치도 제주시 탑동로"},
        "3": {"name": "서귀포 항", "lat": 33.2333, "lng": 126.5667, "url": "http://123.140.197.51/stream/35/play.m3u8", "addr": "제주특별자치도 서귀포시 서귀동 758-1"},
        "4": {"name": "법환포구", "lat": 33.2361, "lng": 126.5161, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100007/0/1", "addr": "제주특별자치도 서귀포시 법환로"},
        "5": {"name": "법환 해안", "lat": 33.2355, "lng": 126.5150, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100008/0/1", "addr": "제주특별자치도 서귀포시 법환동"},
        "6": {"name": "중문 해안", "lat": 33.2422, "lng": 126.4025, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100010/0/1", "addr": "제주특별자치도 서귀포시 중문동"},
        "16": {"name": "성산일출봉", "lat": 33.4585, "lng": 126.9422, "url": "http://123.140.197.51/stream/34/play.m3u8", "addr": "제주특별자치도 서귀포시 성산읍 일출로 284-6"},
        "7": {"name": "온평 해안", "lat": 33.4072, "lng": 126.9114, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100011/0/1", "addr": "제주특별자치도 서귀포시 성산읍 온평리"},
        "8": {"name": "신창 해안", "lat": 33.3667, "lng": 126.1083, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100004/0/1", "addr": "제주특별자치도 제주시 한경면 신창리"},
        "9": {"name": "화순 해안", "lat": 33.2405, "lng": 126.3358, "url": "http://59.8.86.94:8080/media/api/v1/hls/vurix/192871/100012/0/1", "addr": "제주특별자치도 서귀포시 안덕면 화순리"},
        "10": {"name": "백록담", "lat": 33.3617, "lng": 126.5333, "url": "https://hallacctv.kr/live/cctv01.stream_360p/playlist.m3u8", "addr": "제주특별자치도 제주시 한라산 백록담"},
        "11": {"name": "왕관릉", "lat": 33.3833, "lng": 126.5500, "url": "https://hallacctv.kr/live/cctv02.stream_360p/playlist.m3u8", "addr": "제주특별자치도 제주시 한라산 왕관릉"},
        "12": {"name": "윗세오름", "lat": 33.3500, "lng": 126.5167, "url": "https://hallacctv.kr/live/cctv03.stream_360p/playlist.m3u8", "addr": "제주특별자치도 제주시 한라산 윗세오름"},
        "13": {"name": "어승생악", "lat": 33.3917, "lng": 126.4958, "url": "https://hallacctv.kr/live/cctv04.stream_360p/playlist.m3u8", "addr": "제주특별자치도 제주시 한라산 어승생악"},
        "14": {"name": "1100도로", "lat": 33.3578, "lng": 126.4625, "url": "https://hallacctv.kr/live/cctv05.stream_360p/playlist.m3u8", "addr": "제주특별자치도 제주시 1100도로 고지"}
    }

    def collect(self):
        print("Collecting NowJeju data...")
        results = []
        for val, info in self.LOCATIONS.items():
            item = {
                "id": f"NOWJEJU_{val}",
                "name": f"[NOWJEJU] {info['name']}",
                "lat": info['lat'],
                "lng": info['lng'],
                "url": info['url'],
                "source": "NOWJEJU",
                "status": "active",
                "address": info['addr'],
                "backup_urls": []
            }
            results.append(item)
        
        print(f"Successfully collected {len(results)} streams from NowJeju.")
        return results
