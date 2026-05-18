import concurrent.futures
import html
import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data/world_tour_cams.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
REGION_BY_COUNTRY = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'France': 'Europe', 'Italy': 'Europe', 'United Kingdom': 'Europe', 'Spain': 'Europe', 'Greece': 'Europe',
    'Germany': 'Europe', 'Switzerland': 'Europe', 'Netherlands': 'Europe', 'Norway': 'Europe', 'Finland': 'Europe',
    'Denmark': 'Europe', 'Czech Republic': 'Europe', 'Austria': 'Europe', 'Hungary': 'Europe', 'Ireland': 'Europe',
    'Portugal': 'Europe', 'Turkey': 'Asia', 'Japan': 'Asia', 'South Korea': 'Asia', 'Taiwan': 'Asia', 'China': 'Asia',
    'Thailand': 'Asia', 'Indonesia': 'Asia', 'Israel': 'Asia', 'Australia': 'Oceania', 'New Zealand': 'Oceania',
    'Brazil': 'South America', 'South Africa': 'Africa', 'Kenya': 'Africa'
}
COUNTRY_BY_SLUG = {
    'usa': 'United States', 'japan': 'Japan', 'south-korea': 'South Korea', 'italy': 'Italy', 'france': 'France',
    'spain': 'Spain', 'greece': 'Greece', 'thailand': 'Thailand', 'australia': 'Australia', 'canada': 'Canada',
    'united-kingdom': 'United Kingdom', 'brazil': 'Brazil', 'germany': 'Germany', 'switzerland': 'Switzerland',
    'netherlands': 'Netherlands', 'china': 'China', 'taiwan': 'Taiwan', 'mexico': 'Mexico', 'norway': 'Norway',
    'finland': 'Finland', 'south-africa': 'South Africa', 'new-zealand': 'New Zealand', 'indonesia': 'Indonesia',
    'turkey': 'Turkey', 'israel': 'Israel', 'kenya': 'Kenya', 'denmark': 'Denmark'
}
HARD_NEGATIVE_TITLE = re.compile(r'(트로피컬\s*머피|바오밥\s*레스토랑|스키드\s*로우|캠핑\s*프리베|트럭\s*대기열|Kensington|Skid Row|Sloppy|Murphy|Truck Queue|Camping Prive)', re.I)
NEGATIVE_TITLE = re.compile(r'(고양이|독수리|새 모이|피더|동물|Alligator|Spoonbill|Osprey|Otter|Eagle|Cat|Feeder|카지노)', re.I)
POSITIVE_TITLE = re.compile(r'(타임|광장|해변|비치|항구|하버|공항|타워|브리지|대교|성|궁|공원|강|시티|도시|스카이라인|라이브|역|거리|마켓|파노라마|폭포|산|리조트|마리나|해안|도쿄|오사카|서울|부산|뉴욕|파리|런던|로마|베니스|교토|후지|시부야|Times|Square|Beach|Harbour|Harbor|Airport|Tower|Bridge|Castle|Park|River|Skyline|City|Panorama|Falls|Mountain|Resort|Marina)', re.I)

CCTV_WORLD_META = {
    'gyeongbokgung': ('경복궁', '서울 대표 고궁과 광화문 일대', 'Seoul', 'South Korea', 37.5796, 126.9770, 86),
    'ddp': ('동대문 DDP', '동대문디자인플라자와 도심 야경', 'Seoul', 'South Korea', 37.5665, 127.0094, 84),
    'namsan-tower': ('남산타워', '서울 남산과 도심 전망', 'Seoul', 'South Korea', 37.5512, 126.9882, 88),
    'lotte-tower': ('롯데월드타워', '잠실 롯데월드타워와 한강 남동권', 'Seoul', 'South Korea', 37.5125, 127.1025, 87),
    'seoul-sicheong-plaza1': ('서울 시청 광장', '서울시청과 광장 주변', 'Seoul', 'South Korea', 37.5663, 126.9780, 84),
    'seoul-hangang': ('서울 한강', '한강과 서울 도심 전망', 'Seoul', 'South Korea', 37.5338, 127.0082, 86),
    'seokchon-lake': ('석촌호수', '잠실 석촌호수와 주변 도심', 'Seoul', 'South Korea', 37.5080, 127.1018, 82),
    'hongdae-entrance': ('홍대입구', '홍대입구역과 상권 거리', 'Seoul', 'South Korea', 37.5572, 126.9254, 82),
    'lotte-world': ('롯데월드', '잠실 롯데월드 일대', 'Seoul', 'South Korea', 37.5112, 127.0982, 83),
    'sokcho-beach': ('속초해수욕장', '강원 동해안 속초해변', 'Sokcho', 'South Korea', 38.1906, 128.6031, 79),
    'songjeong': ('송정해수욕장', '부산 송정해변', 'Busan', 'South Korea', 35.1784, 129.1994, 78),
    'haeundae': ('해운대 해수욕장', '부산 대표 해변', 'Busan', 'South Korea', 35.1587, 129.1604, 88),
    'gwangandaegyo': ('광안대교', '부산 광안대교와 바다 전망', 'Busan', 'South Korea', 35.1532, 129.1212, 86),
    'banpodaegyo': ('반포대교', '한강 반포대교와 세빛섬 주변', 'Seoul', 'South Korea', 37.5134, 126.9961, 82),
    'jamsugyo': ('잠수교', '한강 잠수교와 반포 일대', 'Seoul', 'South Korea', 37.5134, 126.9961, 80),
    'jamsildaegyo': ('잠실대교', '잠실대교와 한강 동부권', 'Seoul', 'South Korea', 37.5209, 127.0890, 80),
    'mapodaegyo': ('마포대교', '여의도와 마포대교 일대', 'Seoul', 'South Korea', 37.5388, 126.9407, 80),
    'seogangdeagyo': ('서강대교', '서강대교와 한강 서부권', 'Seoul', 'South Korea', 37.5375, 126.9295, 80),
    'gwangandaegyo-traffic': ('광안대교 교통', '부산 광안대교 교통 흐름', 'Busan', 'South Korea', 35.1532, 129.1212, 76),
    'nagoya-station': ('나고야역', '일본 나고야역 도심', 'Nagoya', 'Japan', 35.1709, 136.8815, 78),
    'hisayaodori-park': ('히사야오도리 공원', '나고야 도심 공원과 거리', 'Nagoya', 'Japan', 35.1737, 136.9087, 76),
    'tokyo-station': ('도쿄역', '도쿄역 마루노우치 일대', 'Tokyo', 'Japan', 35.6812, 139.7671, 84),
    'shinjuku-kabukicho': ('신주쿠 가부키초', '도쿄 신주쿠 번화가', 'Tokyo', 'Japan', 35.6940, 139.7034, 84),
    'shibuya-scramble-crossing': ('시부야 스크램블', '도쿄 대표 교차로 실시간 풍경', 'Tokyo', 'Japan', 35.6595, 139.7005, 90),
    'osaka-station': ('오사카역', '오사카역과 우메다 도심', 'Osaka', 'Japan', 34.7025, 135.4959, 80),
    'osaka-dotonbori': ('오사카 도톤보리', '도톤보리 강변과 번화가', 'Osaka', 'Japan', 34.6687, 135.5013, 84),
}

TABI_SEEDS = [
    ('sydney-harbour', '시드니 하버', '시드니 오페라하우스와 하버브리지', 'Sydney', 'Australia', 'Oceania', -33.8568, 151.2153, 'https://tabi.cam/ko/australia/sydney-harbour-86450/', 83),
    ('perth-city-view', '퍼스 시티뷰', '서호주 퍼스 도심 전망', 'Perth', 'Australia', 'Oceania', -31.9505, 115.8605, 'https://tabi.cam/ko/australia/perth-city-view-329175/', 70),
    ('melbourne-skyline', '멜버른 스카이라인', '멜버른 도심 스카이라인', 'Melbourne', 'Australia', 'Oceania', -37.8136, 144.9631, 'https://tabi.cam/ko/australia/melbourne-skyline-345268/', 72),
    ('rainbow-beach', '레인보우 비치', '퀸즐랜드 해변 풍경', 'Rainbow Beach', 'Australia', 'Oceania', -25.9043, 153.0912, 'https://tabi.cam/ko/australia/rainbow-beach-408975/', 68),
    ('mount-fuji-tabi', '후지산', '일본 후지산 전망', 'Yamanashi', 'Japan', 'Asia', 35.3606, 138.7274, 'https://tabi.cam/ko/japan/mount-fuji-325185/', 82),
    ('new-chitose-airport', '신치토세 공항', '홋카이도 신치토세 공항', 'Chitose', 'Japan', 'Asia', 42.7752, 141.6923, 'https://tabi.cam/ko/japan/new-chitose-airport-25935/', 63),
    ('fukuoka-airport', '후쿠오카 공항', '후쿠오카 공항 활주로', 'Fukuoka', 'Japan', 'Asia', 33.5859, 130.4507, 'https://tabi.cam/ko/japan/fukuoka-airport-355509/', 63),
    ('fukuoka-cityscapes', '후쿠오카 도심', '후쿠오카 시내 풍경', 'Fukuoka', 'Japan', 'Asia', 33.5902, 130.4017, 'https://tabi.cam/ko/japan/fukuoka-cityscapes-414827/', 70),
    ('hamamatsu-cityscapes', '하마마츠 도심', '하마마츠 시내 풍경', 'Hamamatsu', 'Japan', 'Asia', 34.7108, 137.7261, 'https://tabi.cam/ko/japan/hamamatsu-cityscapes-309092/', 64),
    ('han-river-tabi', '한강', '서울 한강 도심 전망', 'Seoul', 'South Korea', 'Asia', 37.5338, 127.0082, 'https://tabi.cam/ko/south-korea/han-river-213598/', 78),
    ('songjeong-beach-tabi', '송정해변', '부산 송정해수욕장', 'Busan', 'South Korea', 'Asia', 35.1784, 129.1994, 'https://tabi.cam/ko/south-korea/songjeong-beach-202160/', 70),
    ('gwangandaegyo-tabi', '광안대교', '부산 광안대교 야경과 해안', 'Busan', 'South Korea', 'Asia', 35.1532, 129.1212, 'https://tabi.cam/ko/south-korea/gwangandaegyo-bridge-569506/', 78),
    ('seoul-cityscapes-tabi', '서울 도심', '서울 도심 스카이라인', 'Seoul', 'South Korea', 'Asia', 37.5665, 126.9780, 'https://tabi.cam/ko/south-korea/seoul-cityscapes-79534/', 72),
    ('yeouido-cityscapes', '여의도', '서울 여의도 도심 전망', 'Seoul', 'South Korea', 'Asia', 37.5219, 126.9245, 'https://tabi.cam/ko/south-korea/yeouido-cityscapes-281827/', 72),
    ('trieste-waterfront', '트리에스테 워터프론트', '아드리아해 항구 도시 전망', 'Trieste', 'Italy', 'Europe', 45.6495, 13.7768, 'https://tabi.cam/ko/italy/trieste-waterfront-82992/', 70),
    ('venice-lagoon-tabi', '베네치아 라군', '베네치아 라군과 수상 도시', 'Venice', 'Italy', 'Europe', 45.4408, 12.3155, 'https://tabi.cam/ko/italy/venice-lagoon-418019/', 76),
    ('oro-beach-tabi', '오로 비치', '이탈리아 예솔로 해변', 'Jesolo', 'Italy', 'Europe', 45.5104, 12.6611, 'https://tabi.cam/ko/italy/oro-beach-396473/', 66),
    ('assisi-main-square', '아시시 중앙광장', '아시시 역사 도심 광장', 'Assisi', 'Italy', 'Europe', 43.0707, 12.6196, 'https://tabi.cam/ko/italy/assisi-main-square-145103/', 68),
    ('eastbourne-pier', '이스트본 피어', '영국 남부 해안 피어', 'Eastbourne', 'United Kingdom', 'Europe', 50.7660, 0.2905, 'https://tabi.cam/ko/united-kingdom/eastbourne-pier-521759/', 68),
    ('york-railway-station', '요크역', '영국 요크 철도역', 'York', 'United Kingdom', 'Europe', 53.9584, -1.0930, 'https://tabi.cam/ko/united-kingdom/york-railway-station-294861/', 62),
    ('weymouth-beach', '웨이머스 해변', '영국 남부 해변', 'Weymouth', 'United Kingdom', 'Europe', 50.6110, -2.4530, 'https://tabi.cam/ko/united-kingdom/weymouth-beach-62111/', 66),
    ('hastings-pier', '헤이스팅스 피어', '헤이스팅스 구시가지와 피어', 'Hastings', 'United Kingdom', 'Europe', 50.8552, 0.5890, 'https://tabi.cam/ko/united-kingdom/hastings-old-town-and-pier-347529/', 66),
    ('boston-harbor', '보스턴 하버', '보스턴 항만과 도심', 'Boston', 'United States', 'North America', 42.3601, -71.0495, 'https://tabi.cam/ko/united-states/boston-harbor-595574/', 70),
    ('los-angeles-airport', 'LA 공항', '로스앤젤레스 국제공항', 'Los Angeles', 'United States', 'North America', 33.9416, -118.4085, 'https://tabi.cam/ko/united-states/los-angeles-airport-50008/', 62),
]


def fetch_text(url, timeout=18):
    req = urllib.request.Request(url, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')


def slugify(text):
    value = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return value or str(abs(hash(text)))


def clean_title(title):
    title = html.unescape(title or '').strip()
    title = re.sub(r'^온라인\s+라이브\s+캠\s+', '', title)
    title = re.sub(r'\s+웹캠\s+온라인$', '', title)
    title = re.sub(r'\s+실시간\s+라이브캠\s+CCTV$', '', title)
    return title.strip(' -') or 'Live Cam'


def extract_youtube_id(text):
    ids = []
    patterns = [
        r'youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})',
        r'youtube\.com/watch\?v=([A-Za-z0-9_-]{11})',
        r'youtu\.be/([A-Za-z0-9_-]{11})',
    ]
    for pat in patterns:
        ids.extend(re.findall(pat, text))
    for vid in ids:
        if vid != 'live_stream':
            return vid
    return None


def existing_playable_items():
    payload = json.loads(DATA_PATH.read_text())
    items = []
    for item in payload.get('items', []):
        if item.get('videoId') or item.get('embedUrl'):
            item.setdefault('sourceType', 'youtube' if item.get('videoId') else 'external')
            items.append(item)
    return items


def collect_cctv_world():
    sitemap = fetch_text('https://www.cctv-world.kr/sitemap.xml')
    urls = re.findall(r'<loc>(https://www\.cctv-world\.kr/cctv/[^<]+)</loc>', sitemap)
    urls = [url for url in urls if url.rstrip('/').split('/')[-1] in CCTV_WORLD_META]

    def parse(url):
        try:
            text = fetch_text(url, timeout=12)
            vid = extract_youtube_id(text)
            if not vid:
                return None
            slug = url.rstrip('/').split('/')[-1]
            title, subtitle, city, country, lat, lng, priority = CCTV_WORLD_META[slug]
            return {
                'id': f'cctvworld-{slug}',
                'title': title,
                'subtitle': subtitle,
                'city': city,
                'country': country,
                'region': REGION_BY_COUNTRY[country],
                'lat': lat,
                'lng': lng,
                'videoId': vid,
                'channel': 'CCTV World',
                'sourceUrl': url,
                'tags': ['tourism', 'city', 'cctvworld'],
                'priority': priority,
                'status': 'is_live',
                'sourceType': 'cctvworld'
            }
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        return [item for item in executor.map(parse, urls) if item]


def collect_tabi():
    items = []
    for seed in TABI_SEEDS:
        sid, title, subtitle, city, country, region, lat, lng, url, priority = seed
        try:
            text = fetch_text(url, timeout=12)
            vid = extract_youtube_id(text)
            if not vid:
                continue
            items.append({
                'id': f'tabi-{sid}',
                'title': title,
                'subtitle': subtitle,
                'city': city,
                'country': country,
                'region': region,
                'lat': lat,
                'lng': lng,
                'videoId': vid,
                'channel': 'TabiCam',
                'sourceUrl': url,
                'tags': ['tourism', 'tabi'],
                'priority': priority,
                'status': 'is_live',
                'sourceType': 'tabi'
            })
        except Exception:
            continue
    return items


def webcamera_links():
    list_urls = [
        'https://webcamera24.com/ko/popular/',
        'https://webcamera24.com/ko/latest/',
        *[f'https://webcamera24.com/ko/countries/{slug}/' for slug in [
            'usa', 'japan', 'south-korea', 'italy', 'france', 'spain', 'greece', 'thailand', 'australia', 'canada',
            'united-kingdom', 'brazil', 'germany', 'switzerland', 'netherlands', 'china', 'taiwan', 'mexico',
            'norway', 'finland', 'south-africa', 'new-zealand', 'indonesia', 'turkey'
        ]]
    ]
    links = []
    seen = set()
    for url in list_urls:
        try:
            text = fetch_text(url, timeout=16)
        except Exception:
            continue
        for match in re.finditer(r'href=["\'](/ko/camera/[^"\']+)["\']', text, re.I):
            link = 'https://webcamera24.com' + match.group(1)
            if link not in seen:
                seen.add(link)
                links.append(link)
    return links


def parse_webcamera24(url):
    try:
        text = fetch_text(url, timeout=14)
        vid = extract_youtube_id(text)
        if not vid:
            return None
        map_match = re.search(r'(?:"|\\")mapCenter(?:"|\\"):\{(?:"|\\")lat(?:"|\\"):([-0-9.]+),(?:"|\\")lng(?:"|\\"):([-0-9.]+)\}', text)
        if not map_match:
            return None
        title_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', text, re.I)
        desc_match = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', text, re.I)
        image_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', text, re.I)
        title = clean_title(title_match.group(1) if title_match else '')
        if HARD_NEGATIVE_TITLE.search(title):
            return None
        if NEGATIVE_TITLE.search(title) and not POSITIVE_TITLE.search(title):
            return None
        country_slug = urlparse(url).path.strip('/').split('/')[2]
        country = COUNTRY_BY_SLUG.get(country_slug, country_slug.replace('-', ' ').title())
        region = REGION_BY_COUNTRY.get(country, 'Other')
        if region == 'Other':
            return None
        city = title.split(',')[-1].strip() if ',' in title else country
        desc = html.unescape(desc_match.group(1)).strip() if desc_match else f'{city}, {country} live webcam'
        subtitle = re.sub(r'\s+', ' ', desc)[:110].rstrip(' ,')
        return {
            'id': f'webcamera24-{slugify(urlparse(url).path.strip("/").split("/")[-1])}',
            'title': title,
            'subtitle': subtitle,
            'city': city,
            'country': country,
            'region': region,
            'lat': round(float(map_match.group(1)), 6),
            'lng': round(float(map_match.group(2)), 6),
            'videoId': vid,
            'channel': 'WebCamera24',
            'sourceUrl': url,
            'thumbnailUrl': html.unescape(image_match.group(1)) if image_match else '',
            'tags': ['tourism', 'webcamera24'],
            'priority': 64,
            'status': 'is_live',
            'sourceType': 'webcamera24'
        }
    except Exception:
        return None


def collect_webcamera24(limit=95):
    links = webcamera_links()
    items = []
    country_counts = {}
    region_counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in executor.map(parse_webcamera24, links[:360]):
            if not item:
                continue
            country_cap = 10 if item['country'] in {'United States', 'Japan'} else 8
            if country_counts.get(item['country'], 0) >= country_cap:
                continue
            if region_counts.get(item['region'], 0) >= 28:
                continue
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            region_counts[item['region']] = region_counts.get(item['region'], 0) + 1
            item['priority'] = max(52, item['priority'] - country_counts[item['country']] * 0.4)
            items.append(item)
            if len(items) >= limit:
                break
    return items


def main():
    base = existing_playable_items()
    additions = collect_cctv_world() + collect_tabi() + collect_webcamera24()
    by_key = {}
    video_seen = set()
    for item in base + additions:
        vid = item.get('videoId') or item.get('embedUrl')
        if item.get('videoId') and item['videoId'] in video_seen:
            continue
        if item.get('videoId'):
            video_seen.add(item['videoId'])
        key = item.get('id') or slugify(item.get('title', ''))
        by_key[key] = item
    items = list(by_key.values())
    items.sort(key=lambda item: (-(float(item.get('priority') or 0)), item.get('region', ''), item.get('title', '')))
    payload = {
        'updated_at': '2026-05-18',
        'description': 'Curated public world tourist live/webcam directory. Only in-app playable YouTube/embed streams are included; source-site-only players are excluded.',
        'items': items
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    from collections import Counter
    print('items', len(items))
    print('sources', dict(Counter(i.get('sourceType', 'youtube') for i in items)))
    print('external_only', sum(1 for i in items if not (i.get('videoId') or i.get('embedUrl'))))

if __name__ == '__main__':
    main()
