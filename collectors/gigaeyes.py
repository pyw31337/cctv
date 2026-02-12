class GigaEyesCollector:
    """
    Collector for GiGAeyes Live TV (YouTube) streams.
    Provides 20 high-quality nationwide live cams.
    """
    
    STREAMS = [
        {"id": "gAr0P3SFLBo", "name": "서울 DDP (동대문디자인플라자)", "lat": 37.5672, "lng": 127.0105, "addr": "서울특별시 중구 을지로 281"},
        {"id": "jTQjbPOwv24", "name": "포항 호미곶 광장", "lat": 36.0764, "lng": 129.5750, "addr": "경상북도 포항시 남구 호미곶면 해맞이로 150번길 20"},
        {"id": "DSgn-lTHJzM", "name": "서울역 광장", "lat": 37.5547, "lng": 126.9706, "addr": "서울특별시 중구 한강대로 405"},
        {"id": "1_DTr0zhNOc", "name": "한강 서강대교", "lat": 37.5458, "lng": 126.9317, "addr": "서울특별시 영등포구 여의도동 서강대교"},
        {"id": "hWyByX9fY2g", "name": "서울 마포대교", "lat": 37.5348, "lng": 126.9367, "addr": "서울특별시 마포구 마포동 마포대교"},
        {"id": "6TRAOJJZrl0", "name": "부산 해운대 송정해수욕장", "lat": 35.1781, "lng": 129.1983, "addr": "부산광역시 해운대구 송정해변로"},
        {"id": "1AUCJbyKoMo", "name": "제주 성산일출봉", "lat": 33.4585, "lng": 126.9422, "addr": "제주특별자치도 서귀포시 성산읍 일출로 284-6"},
        {"id": "_c4D1i3mtps", "name": "분당 KT사옥", "lat": 37.3639, "lng": 127.1084, "addr": "경기도 성남시 분당구 불정로 90"},
        {"id": "3Io7PxtEHAA", "name": "부산 광안대교", "lat": 35.1554, "lng": 129.1378, "addr": "부산광역시 해운대구 재송동 광안대교"},
        {"id": "16Z1AnS4nvs", "name": "서울 지하철 2호선 대림역", "lat": 37.4851, "lng": 126.8953, "addr": "서울특별시 구로구 도림로 지하 230"},
        {"id": "VBlN0MGqyz4", "name": "서울 경복궁", "lat": 37.5759, "lng": 126.9768, "addr": "서울특별시 종로구 사직로 161"},
        {"id": "8NdFS7Dpfzg", "name": "강릉 강문해변", "lat": 37.7925, "lng": 128.9482, "addr": "강원특별자치도 강릉시 강문동"},
        {"id": "bKcdTWp6akg", "name": "대전 엑스포 한빛광장", "lat": 36.3745, "lng": 127.3879, "addr": "대전광역시 유성구 대덕대로 480"},
        {"id": "6913uqN0Bkw", "name": "서울 롯데월드타워", "lat": 37.5112, "lng": 127.0980, "addr": "서울특별시 송파구 올림픽로 300"},
        {"id": "QmqJKE9uYXU", "name": "속초 해수욕장", "lat": 37.9551, "lng": 128.7716, "addr": "강원특별자치도 속초시 조양동"},
        {"id": "UYziFFSzzMo", "name": "서울 석촌호수", "lat": 37.5098, "lng": 127.1038, "addr": "서울특별시 송파구 잠실동 석촌호수"},
        {"id": "JIQPCfb9Qs0", "name": "서울 롯데월드", "lat": 37.5111, "lng": 127.0960, "addr": "서울특별시 송파구 올림픽로 240"},
        {"id": "IhO0ICVe4KQ", "name": "수원 광교호수공원", "lat": 37.2831, "lng": 127.0659, "addr": "경기도 수원시 영통구 광교호수로 165"},
        {"id": "zuWxsbV-mlA", "name": "서울 광화문대로", "lat": 37.5759, "lng": 126.9769, "addr": "서울특별시 종로구 세종로 광화문광장"},
        {"id": "ZopiySgQjsc", "name": "한강 잠실대교", "lat": 37.5218, "lng": 127.1009, "addr": "서울특별시 송파구 신천동 잠실대교"}
    ]

    def collect(self):
        print(f"Collecting GiGAeyes YouTube data ({len(self.STREAMS)} streams)...")
        results = []
        for s in self.STREAMS:
            item = {
                "id": f"GIGAEYES_{s['id']}",
                "name": f"[YouTube] {s['name']}",
                "lat": s['lat'],
                "lng": s['lng'],
                "url": f"https://www.youtube.com/watch?v={s['id']}",
                "source": "GIGAEYES",
                "status": "active",
                "address": s['addr'],
                "backup_urls": []
            }
            results.append(item)
        
        print(f"Successfully collected {len(results)} YouTube streams from GiGAeyes.")
        return results
