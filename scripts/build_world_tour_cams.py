import concurrent.futures
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data/world_tour_cams.json'
GEOCODE_CACHE_PATH = ROOT / '.cache/world_tour_geocode_cache.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
NOMINATIM_HEADERS = {
    **HEADERS,
    'User-Agent': 'pyw31337-cctv-world-tour/1.0 (https://pyw31337.github.io/cctv/)'
}
REGION_BY_COUNTRY = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'Panama': 'North America', 'Greenland': 'North America', 'Jamaica': 'North America', 'Curaçao': 'North America',
    'France': 'Europe', 'Italy': 'Europe', 'United Kingdom': 'Europe', 'Spain': 'Europe', 'Greece': 'Europe',
    'Germany': 'Europe', 'Switzerland': 'Europe', 'Netherlands': 'Europe', 'Norway': 'Europe', 'Finland': 'Europe',
    'Denmark': 'Europe', 'Czech Republic': 'Europe', 'Austria': 'Europe', 'Hungary': 'Europe', 'Ireland': 'Europe',
    'Portugal': 'Europe', 'Belgium': 'Europe', 'Bulgaria': 'Europe', 'Croatia': 'Europe', 'Estonia': 'Europe',
    'Iceland': 'Europe', 'Latvia': 'Europe', 'Liechtenstein': 'Europe', 'Lithuania': 'Europe', 'Montenegro': 'Europe',
    'Poland': 'Europe', 'Romania': 'Europe', 'Russia': 'Europe', 'San Marino': 'Europe', 'Slovakia': 'Europe',
    'Sweden': 'Europe', 'Ukraine': 'Europe', 'Vatican': 'Europe', 'Belarus': 'Europe',
    'Turkey': 'Asia', 'Japan': 'Asia', 'South Korea': 'Asia', 'Taiwan': 'Asia', 'China': 'Asia',
    'Thailand': 'Asia', 'Indonesia': 'Asia', 'Israel': 'Asia', 'India': 'Asia', 'Malaysia': 'Asia',
    'Maldives': 'Asia', 'Philippines': 'Asia', 'Saudi Arabia': 'Asia', 'Singapore': 'Asia', 'Vietnam': 'Asia',
    'Georgia': 'Asia', 'Hong Kong': 'Asia', 'United Arab Emirates': 'Asia', 'Australia': 'Oceania', 'New Zealand': 'Oceania',
    'Brazil': 'South America', 'Chile': 'South America',
    'South Africa': 'Africa', 'Kenya': 'Africa', 'Cape Verde': 'Africa', 'Egypt': 'Africa', 'Namibia': 'Africa',
    'Mauritius': 'Africa', 'Morocco': 'Africa'
}
COUNTRY_BY_SLUG = {
    'usa': 'United States', 'japan': 'Japan', 'south-korea': 'South Korea', 'italy': 'Italy', 'france': 'France',
    'spain': 'Spain', 'greece': 'Greece', 'thailand': 'Thailand', 'australia': 'Australia', 'canada': 'Canada',
    'united-kingdom': 'United Kingdom', 'brazil': 'Brazil', 'germany': 'Germany', 'switzerland': 'Switzerland',
    'netherlands': 'Netherlands', 'china': 'China', 'taiwan': 'Taiwan', 'mexico': 'Mexico', 'norway': 'Norway',
    'finland': 'Finland', 'south-africa': 'South Africa', 'new-zealand': 'New Zealand', 'indonesia': 'Indonesia',
    'turkey': 'Turkey', 'israel': 'Israel', 'kenya': 'Kenya', 'denmark': 'Denmark', 'austria': 'Austria',
    'belarus': 'Belarus', 'belgium': 'Belgium', 'bulgaria': 'Bulgaria', 'cape-verde': 'Cape Verde',
    'chile': 'Chile', 'croatia': 'Croatia', 'czech': 'Czech Republic', 'egypt': 'Egypt', 'estonia': 'Estonia',
    'georgia': 'Georgia', 'greenland': 'Greenland', 'hungary': 'Hungary', 'iceland': 'Iceland', 'india': 'India',
    'ireland': 'Ireland', 'latvia': 'Latvia', 'liechtenstein': 'Liechtenstein', 'lithuania': 'Lithuania',
    'malaysia': 'Malaysia', 'maldives': 'Maldives', 'mauritius': 'Mauritius', 'montenegro': 'Montenegro',
    'morocco': 'Morocco', 'panama': 'Panama', 'philippines': 'Philippines', 'poland': 'Poland',
    'portugal': 'Portugal', 'romania': 'Romania', 'russia': 'Russia', 'san-marino': 'San Marino',
    'saudi-arabia': 'Saudi Arabia', 'singapore': 'Singapore', 'slovakia': 'Slovakia', 'sweden': 'Sweden',
    'ukraine': 'Ukraine', 'vatican': 'Vatican', 'vietnam': 'Vietnam'
}
HARD_NEGATIVE_TITLE = re.compile(r'(트로피컬\s*머피|바오밥\s*레스토랑|스키드\s*로우|캠핑\s*프리베|트럭\s*대기열|송골매|둥지|코끼리|Kensington|Skid Row|Sloppy|Murphy|Truck Queue|Camping Prive|Falcon|Nest|Elephant)', re.I)
NEGATIVE_TITLE = re.compile(r'(고양이|독수리|새 모이|피더|동물|야생동물|Alligator|Spoonbill|Osprey|Otter|Eagle|Cat|Feeder|Wildlife|Zoo|Bird|Animal|Penguin|카지노)', re.I)
POSITIVE_TITLE = re.compile(r'(타임|광장|해변|비치|항구|하버|공항|타워|브리지|대교|성|궁|공원|강|시티|도시|스카이라인|라이브|역|거리|마켓|파노라마|폭포|산|리조트|마리나|해안|도쿄|오사카|서울|부산|뉴욕|파리|런던|로마|베니스|교토|후지|시부야|Times|Square|Beach|Harbour|Harbor|Airport|Tower|Bridge|Castle|Park|River|Skyline|City|Panorama|Falls|Mountain|Resort|Marina)', re.I)
UNSTABLE_TITLE = re.compile(r'(private video|deleted video|video unavailable|비공개|삭제|사용할 수 없는)', re.I)
YOUTUBE_SEARCH_LIMIT = int(os.getenv('WORLD_TOUR_YOUTUBE_SEARCH_LIMIT', '420'))
YOUTUBE_SEARCH_PER_QUERY_LIMIT = int(os.getenv('WORLD_TOUR_YOUTUBE_SEARCH_PER_QUERY_LIMIT', '48'))
YOUTUBE_SEARCH_QUERIES = [
    'live cam',
    'tourist live webcam',
    'city live webcam',
    'city square live cam',
    'beach live cam',
    'harbour live webcam',
    'airport live webcam',
    'skyline live cam',
    'mountain live webcam',
    'traffic city live webcam',
]
YTDLP_BIN = shutil.which(os.getenv('YTDLP_BIN', 'yt-dlp'))
YOUTUBE_SEARCH_NEGATIVE = re.compile(
    r'(around the world|top live cams|rolling cam|camera feeds|middle east|smooth jazz|relaxing music|'
    r'timelapse|armchair travel|bus rides|walking|walk |drive |cab view|train moments|family real life|'
    r'food cooking|puppy|cat|kitten|bird|birds|eagle|panda|penguin|jelly|otter|owl|nest|wildlife|safari|zoo|'
    r'forest|feeder|animal|falcon|casino|skid row|kensington|truck queue)',
    re.I
)
SOURCE_QUALITY_BONUS = {
    'youtube': 7,
    'cctvworld': 6,
    'tabi': 4,
    'webcamera24': 2,
    'youtube-search': 0,
    'external': -8,
}
YOUTUBE_LOCATION_HINTS = [
    (('shibuya', '渋谷'), '시부야 스크램블', 'Tokyo', 'Japan', 'Asia', 35.6595, 139.7005),
    (('shinjuku', '新宿'), '신주쿠', 'Tokyo', 'Japan', 'Asia', 35.6938, 139.7034),
    (('akihabara', '秋葉原'), '아키하바라', 'Tokyo', 'Japan', 'Asia', 35.6984, 139.7730),
    (('ginza', '銀座'), '긴자', 'Tokyo', 'Japan', 'Asia', 35.6717, 139.7650),
    (('asakusa', '浅草'), '아사쿠사', 'Tokyo', 'Japan', 'Asia', 35.7148, 139.7967),
    (('tokyo tower',), '도쿄타워', 'Tokyo', 'Japan', 'Asia', 35.6586, 139.7454),
    (('dotonbori', 'dōtonbori', '道頓堀'), '오사카 도톤보리', 'Osaka', 'Japan', 'Asia', 34.6687, 135.5013),
    (('kyoto', 'gion', '祇園'), '교토 기온', 'Kyoto', 'Japan', 'Asia', 35.0037, 135.7788),
    (('sapporo', 'susukino'), '삿포로 스스키노', 'Sapporo', 'Japan', 'Asia', 43.0555, 141.3539),
    (('fukuoka', 'tenjin'), '후쿠오카 텐진', 'Fukuoka', 'Japan', 'Asia', 33.5904, 130.4017),
    (('hongdae', '홍대'), '홍대입구', 'Seoul', 'South Korea', 'Asia', 37.5563, 126.9236),
    (('myeongdong', '명동'), '명동', 'Seoul', 'South Korea', 'Asia', 37.5636, 126.9834),
    (('gangnam', '강남'), '강남대로', 'Seoul', 'South Korea', 'Asia', 37.4979, 127.0276),
    (('haeundae', '해운대'), '해운대', 'Busan', 'South Korea', 'Asia', 35.1587, 129.1604),
    (('gwangalli', '광안리'), '광안리', 'Busan', 'South Korea', 'Asia', 35.1532, 129.1187),
    (('jeju', '제주'), '제주', 'Jeju', 'South Korea', 'Asia', 33.4996, 126.5312),
    (('taipei', 'taipei 101'), '타이베이 101', 'Taipei', 'Taiwan', 'Asia', 25.0330, 121.5654),
    (('hong kong', 'victoria harbour', 'victoria harbor'), '홍콩 빅토리아 하버', 'Hong Kong', 'Hong Kong', 'Asia', 22.2940, 114.1694),
    (('singapore', 'marina bay'), '싱가포르 마리나 베이', 'Singapore', 'Singapore', 'Asia', 1.2834, 103.8607),
    (('bangkok',), '방콕', 'Bangkok', 'Thailand', 'Asia', 13.7563, 100.5018),
    (('phuket', 'patong'), '푸켓 파통', 'Phuket', 'Thailand', 'Asia', 7.8964, 98.2964),
    (('bali', 'denpasar', 'kuta'), '발리', 'Bali', 'Indonesia', 'Asia', -8.6500, 115.2167),
    (('kuala lumpur',), '쿠알라룸푸르', 'Kuala Lumpur', 'Malaysia', 'Asia', 3.1478, 101.6953),
    (('dubai', 'burj khalifa'), '두바이', 'Dubai', 'United Arab Emirates', 'Asia', 25.2048, 55.2708),
    (('jerusalem', 'western wall'), '예루살렘 통곡의 벽', 'Jerusalem', 'Israel', 'Asia', 31.7767, 35.2345),
    (('maldives', 'male '), '몰디브', 'Maldives', 'Maldives', 'Asia', 4.1755, 73.5093),
    (('davao', 'agdao', 'bankerohan'), '다바오 시티', 'Davao City', 'Philippines', 'Asia', 7.1907, 125.4553),
    (('koh samui', 'lamai', 'bophut', 'chaweng'), '코사무이', 'Koh Samui', 'Thailand', 'Asia', 9.5120, 100.0136),
    (('venice beach',), '베니스 비치', 'Los Angeles', 'United States', 'North America', 33.9850, -118.4695),
    (('venice', 'venezia', 'san marco', 'guglie'), '베네치아', 'Venice', 'Italy', 'Europe', 45.4408, 12.3155),
    (('key west', 'southernmost point', 'hogs breath'), '키웨스트', 'Key West', 'United States', 'North America', 24.5465, -81.7975),
    (('fort lauderdale', 'elbo room'), '포트로더데일', 'Fort Lauderdale', 'United States', 'North America', 26.1224, -80.1040),
    (('coney island',), '코니 아일랜드', 'New York', 'United States', 'North America', 40.5749, -73.9850),
    (('bryant park',), '브라이언트 파크', 'New York', 'United States', 'North America', 40.7536, -73.9832),
    (('times square',), '타임스퀘어', 'New York', 'United States', 'North America', 40.7580, -73.9855),
    (('statue of liberty',), '자유의 여신상', 'New York', 'United States', 'North America', 40.6892, -74.0445),
    (('niagara',), '나이아가라 폭포', 'Niagara Falls', 'Canada', 'North America', 43.0828, -79.0742),
    (('grand canyon',), '그랜드 캐니언', 'Arizona', 'United States', 'North America', 36.1069, -112.1129),
    (('yellowstone',), '옐로스톤', 'Wyoming', 'United States', 'North America', 44.4280, -110.5885),
    (('san francisco', 'golden gate'), '샌프란시스코', 'San Francisco', 'United States', 'North America', 37.8199, -122.4783),
    (('seattle', 'space needle'), '시애틀', 'Seattle', 'United States', 'North America', 47.6205, -122.3493),
    (('chicago',), '시카고', 'Chicago', 'United States', 'North America', 41.8781, -87.6298),
    (('washington dc', 'white house'), '워싱턴 DC', 'Washington', 'United States', 'North America', 38.8977, -77.0365),
    (('las vegas airport', 'vegas airport'), '라스베이거스 공항', 'Las Vegas', 'United States', 'North America', 36.0840, -115.1537),
    (('las vegas strip',), '라스베이거스 스트립', 'Las Vegas', 'United States', 'North America', 36.1147, -115.1728),
    (('hollywood beach',), '할리우드 비치', 'Hollywood', 'United States', 'North America', 26.0112, -80.1169),
    (('jacksonville beach',), '잭슨빌 비치', 'Jacksonville Beach', 'United States', 'North America', 30.2841, -81.3961),
    (('mori point', 'pacifica'), '퍼시피카 모리 포인트', 'Pacifica', 'United States', 'North America', 37.6138, -122.4869),
    (('port miami', 'miami cruise'), '마이애미 항구', 'Miami', 'United States', 'North America', 25.7781, -80.1794),
    (('vancouver', 'canada place'), '밴쿠버', 'Vancouver', 'Canada', 'North America', 49.2890, -123.1110),
    (('toronto',), '토론토', 'Toronto', 'Canada', 'North America', 43.6532, -79.3832),
    (('montreal',), '몬트리올', 'Montreal', 'Canada', 'North America', 45.5019, -73.5674),
    (('mexico city',), '멕시코시티', 'Mexico City', 'Mexico', 'North America', 19.4326, -99.1332),
    (('boston',), '보스턴', 'Boston', 'United States', 'North America', 42.3601, -71.0589),
    (('ocean city',), '오션시티', 'Ocean City', 'United States', 'North America', 38.3365, -75.0849),
    (('southampton', 'cowes', 'isle of wight'), '와이트섬 페리', 'Southampton', 'United Kingdom', 'Europe', 50.9097, -1.4044),
    (('dublin',), '더블린', 'Dublin', 'Ireland', 'Europe', 53.3498, -6.2603),
    (('london', 'abbey road'), '런던', 'London', 'United Kingdom', 'Europe', 51.5072, -0.1276),
    (('paris', 'eiffel'), '에펠탑', 'Paris', 'France', 'Europe', 48.8584, 2.2945),
    (('rome', 'roma', 'colosseum'), '로마', 'Rome', 'Italy', 'Europe', 41.8902, 12.4922),
    (('milan', 'milano'), '밀라노', 'Milan', 'Italy', 'Europe', 45.4642, 9.1900),
    (('florence', 'firenze'), '피렌체', 'Florence', 'Italy', 'Europe', 43.7696, 11.2558),
    (('barcelona',), '바르셀로나', 'Barcelona', 'Spain', 'Europe', 41.3874, 2.1686),
    (('madrid',), '마드리드', 'Madrid', 'Spain', 'Europe', 40.4168, -3.7038),
    (('lisbon', 'lisboa'), '리스본', 'Lisbon', 'Portugal', 'Europe', 38.7223, -9.1393),
    (('amsterdam',), '암스테르담', 'Amsterdam', 'Netherlands', 'Europe', 52.3676, 4.9041),
    (('prague', 'praha'), '프라하', 'Prague', 'Czech Republic', 'Europe', 50.0755, 14.4378),
    (('vienna', 'wien'), '빈', 'Vienna', 'Austria', 'Europe', 48.2082, 16.3738),
    (('budapest',), '부다페스트', 'Budapest', 'Hungary', 'Europe', 47.4979, 19.0402),
    (('zermatt', 'matterhorn'), '마테호른', 'Zermatt', 'Switzerland', 'Europe', 46.0207, 7.7491),
    (('lanzarote',), '란사로테 공항', 'Lanzarote', 'Spain', 'Europe', 28.9455, -13.6052),
    (('swiss alps', 'schweiz panorama'), '스위스 알프스', 'Zermatt', 'Switzerland', 'Europe', 46.0207, 7.7491),
    (('bad salzungen',), '바트 잘충겐', 'Bad Salzungen', 'Germany', 'Europe', 50.8130, 10.2360),
    (('maui', 'wailea', 'whale watch'), '마우이', 'Maui', 'United States', 'North America', 20.7984, -156.3319),
    (('waikiki', 'honolulu'), '와이키키', 'Honolulu', 'United States', 'North America', 21.2766, -157.8268),
    (('mauna', 'maunakea'), '마우나케아', 'Hawaii', 'United States', 'North America', 19.8207, -155.4681),
    (('sydney', 'sydney harbour', 'sydney harbor'), '시드니 하버', 'Sydney', 'Australia', 'Oceania', -33.8568, 151.2153),
    (('melbourne',), '멜버른', 'Melbourne', 'Australia', 'Oceania', -37.8136, 144.9631),
    (('perth',), '퍼스', 'Perth', 'Australia', 'Oceania', -31.9505, 115.8605),
    (('auckland',), '오클랜드', 'Auckland', 'New Zealand', 'Oceania', -36.8509, 174.7645),
    (('queenstown',), '퀸스타운', 'Queenstown', 'New Zealand', 'Oceania', -45.0312, 168.6626),
    (('rio', 'copacabana'), '리우 코파카바나', 'Rio de Janeiro', 'Brazil', 'South America', -22.9711, -43.1822),
    (('sao paulo', 'são paulo'), '상파울루', 'São Paulo', 'Brazil', 'South America', -23.5558, -46.6396),
    (('santiago',), '산티아고', 'Santiago', 'Chile', 'South America', -33.4489, -70.6693),
    (('cape town',), '케이프타운', 'Cape Town', 'South Africa', 'Africa', -33.9249, 18.4241),
    (('marrakesh', 'marrakech'), '마라케시', 'Marrakesh', 'Morocco', 'Africa', 31.6295, -7.9811),
    (('cairo', 'pyramids'), '카이로', 'Cairo', 'Egypt', 'Africa', 30.0444, 31.2357),
    (('namib', 'namibia'), '나미브 사막', 'Namib Desert', 'Namibia', 'Africa', -23.0000, 15.0000),
    (('curacao', 'curaçao', 'swinging bridge'), '퀴라소 퀸 엠마 브리지', 'Willemstad', 'Curaçao', 'North America', 12.1084, -68.9335),
    (('kingston jamaica', 'half way tree'), '킹스턴 하프웨이트리', 'Kingston', 'Jamaica', 'North America', 18.0179, -76.8099),
    (('negril', 'rick'), '네그릴', 'Negril', 'Jamaica', 'North America', 18.2683, -78.3472),
    (('bondi aussie', 'crystal bay',), '코사무이', 'Koh Samui', 'Thailand', 'Asia', 9.5120, 100.0136),
]

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


def fetch_json(url, timeout=12):
    return json.loads(fetch_text(url, timeout=timeout))


def fetch_json_with_headers(url, timeout=12, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace'))


def load_geocode_cache():
    if not GEOCODE_CACHE_PATH.exists():
        return {}
    try:
        return json.loads(GEOCODE_CACHE_PATH.read_text())
    except Exception:
        return {}


def save_geocode_cache(cache):
    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + '\n')


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


def clean_youtube_search_title(title):
    value = html.unescape(title or '')
    value = re.sub(r'[🔴🟢🟡⚫⚪🚢🌊🐳✨☕|]+', ' ', value)
    value = re.sub(r'\b(24/7|4K|HD|LIVE|Live|live|Webcam|webcam|LIVE CAM|Live Cam|Camera|camera|Stream|streaming)\b', ' ', value)
    value = re.sub(r'#\w+', ' ', value)
    value = re.sub(r'\s+', ' ', value).strip(' -–—:|')
    return value


def youtube_search_queries():
    custom = os.getenv('WORLD_TOUR_YOUTUBE_SEARCH_QUERIES', '').strip()
    if custom:
        return [query.strip() for query in custom.split('|') if query.strip()]
    return YOUTUBE_SEARCH_QUERIES


def youtube_location_hint(title):
    lowered = (title or '').lower()
    for aliases, title_ko, city, country, region, lat, lng in YOUTUBE_LOCATION_HINTS:
        if any(alias in lowered for alias in aliases):
            return {
                'title': title_ko,
                'city': city,
                'country': country,
                'region': region,
                'lat': lat,
                'lng': lng,
            }
    return None


def youtube_geocode_candidates(title):
    cleaned = clean_youtube_search_title(title)
    parts = re.split(r'\s[-–—:]\s|,|\(|\)|/', cleaned)
    candidates = []
    for part in parts:
        part = re.sub(r'\b(official|channel|with|from|view|views|real time|tonight|now|cam)\b', ' ', part, flags=re.I)
        part = re.sub(r'\s+', ' ', part).strip()
        if len(part) < 4 or len(part) > 70:
            continue
        if YOUTUBE_SEARCH_NEGATIVE.search(part):
            continue
        candidates.append(part)
    if cleaned and len(cleaned) <= 70:
        candidates.append(cleaned)
    return list(dict.fromkeys(candidates))[:4]


def geocode_location(query, cache):
    if not query:
        return None
    key = query.lower().strip()
    if key in cache:
        return cache[key]
    url = (
        'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&addressdetails=1&q='
        + quote(query)
    )
    try:
        results = fetch_json_with_headers(url, timeout=12, headers=NOMINATIM_HEADERS)
        time.sleep(1.05)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        cache[key] = None
        return None
    if not results:
        cache[key] = None
        return None
    result = results[0]
    address = result.get('address') or {}
    country = address.get('country')
    if not country:
        cache[key] = None
        return None
    city = (
        address.get('city') or address.get('town') or address.get('village') or
        address.get('municipality') or address.get('county') or country
    )
    item = {
        'city': city,
        'country': country,
        'region': REGION_BY_COUNTRY.get(country, 'Other'),
        'lat': round(float(result['lat']), 6),
        'lng': round(float(result['lon']), 6),
    }
    if item['region'] == 'Other':
        cache[key] = None
        return None
    cache[key] = item
    return item


def infer_youtube_location(title, cache):
    hint = youtube_location_hint(title)
    if hint:
        return hint
    for candidate in youtube_geocode_candidates(title):
        geocoded = geocode_location(candidate, cache)
        if geocoded:
            return geocoded
    return None


def yt_dlp_json(args, timeout=45):
    if not YTDLP_BIN:
        return None
    try:
        completed = subprocess.run(
            [YTDLP_BIN, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None


def existing_playable_items():
    payload = json.loads(DATA_PATH.read_text())
    items = []
    cache = load_geocode_cache()
    for item in payload.get('items', []):
        if item.get('sourceType') == 'webcamera24' and HARD_NEGATIVE_TITLE.search(item.get('title', '')):
            continue
        if item.get('sourceType') == 'webcamera24' and NEGATIVE_TITLE.search(item.get('title', '')) and not POSITIVE_TITLE.search(item.get('title', '')):
            continue
        if item.get('sourceType') == 'youtube-search':
            location = infer_youtube_location(f"{item.get('title', '')} {item.get('subtitle', '')}", cache)
            if location:
                item['title'] = location.get('title') or item.get('title')
                item['city'] = location['city']
                item['country'] = location['country']
                item['region'] = location['region']
                item['lat'] = location['lat']
                item['lng'] = location['lng']
        if item.get('videoId') or item.get('embedUrl'):
            item.setdefault('sourceType', 'youtube' if item.get('videoId') else 'external')
            items.append(item)
    save_geocode_cache(cache)
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
        'https://webcamera24.com/ko/all-webcams/',
        'https://webcamera24.com/ko/popular/',
        'https://webcamera24.com/ko/latest/',
        *[f'https://webcamera24.com/ko/countries/{slug}/' for slug in sorted(COUNTRY_BY_SLUG)]
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
    return prioritize_webcamera_links(links)


def prioritize_webcamera_links(links):
    def score(link):
        slug = urlparse(link).path.strip('/').split('/')[-1].replace('-', ' ')
        value = 0
        if POSITIVE_TITLE.search(slug):
            value -= 20
        if re.search(r'(city|town|square|beach|harbour|harbor|airport|bridge|street|traffic|panorama|skyline|river|mountain|port|bay)', slug, re.I):
            value -= 12
        if NEGATIVE_TITLE.search(slug):
            value += 80
        return value

    return sorted(links, key=score)


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


def collect_webcamera24(limit=190):
    links = webcamera_links()
    items = []
    country_counts = {}
    region_counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in executor.map(parse_webcamera24, links[:1500]):
            if not item:
                continue
            country_cap = 16 if item['country'] in {'United States', 'Japan', 'Italy', 'Spain'} else 11
            if country_counts.get(item['country'], 0) >= country_cap:
                continue
            if region_counts.get(item['region'], 0) >= 72:
                continue
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            region_counts[item['region']] = region_counts.get(item['region'], 0) + 1
            item['priority'] = max(52, item['priority'] - country_counts[item['country']] * 0.4)
            items.append(item)
            if len(items) >= limit:
                break
    return items


def collect_youtube_search(limit=YOUTUBE_SEARCH_LIMIT):
    if not YTDLP_BIN or limit <= 0:
        return []

    entries = []
    seen_entry_ids = set()
    queries = youtube_search_queries()
    per_query_limit = max(1, min(YOUTUBE_SEARCH_PER_QUERY_LIMIT, limit))
    for query in queries:
        payload = yt_dlp_json(
            ['--flat-playlist', '--dump-single-json', f'ytsearch{per_query_limit}:{query}'],
            timeout=70,
        )
        if not payload:
            continue
        for entry in payload.get('entries', []):
            video_id = entry.get('id')
            if not video_id or video_id in seen_entry_ids:
                continue
            seen_entry_ids.add(video_id)
            entry['search_query'] = query
            entries.append(entry)

    cache = load_geocode_cache()
    items = []
    seen = set()
    for entry in entries:
        video_id = entry.get('id')
        title = entry.get('title') or ''
        if not video_id or video_id in seen:
            continue
        seen.add(video_id)
        if entry.get('live_status') != 'is_live':
            continue
        if YOUTUBE_SEARCH_NEGATIVE.search(title):
            continue
        if not (POSITIVE_TITLE.search(title) or youtube_location_hint(title)):
            continue

        location = infer_youtube_location(title, cache)
        if not location:
            continue

        thumbnails = entry.get('thumbnails') or []
        thumbnail = thumbnails[-1].get('url') if thumbnails and isinstance(thumbnails[-1], dict) else ''
        display_title = location.get('title') or clean_youtube_search_title(title)
        city = location['city']
        country = location['country']
        items.append({
            'id': f'youtube-search-{slugify(video_id)}',
            'title': display_title,
            'subtitle': clean_youtube_search_title(title)[:110],
            'city': city,
            'country': country,
            'region': location['region'],
            'lat': location['lat'],
            'lng': location['lng'],
            'videoId': video_id,
            'channel': entry.get('channel') or entry.get('uploader') or 'YouTube',
            'sourceUrl': entry.get('url') or f'https://www.youtube.com/watch?v={video_id}',
            'thumbnailUrl': thumbnail,
            'tags': ['tourism', 'youtube-search', 'livecam'],
            'priority': 67,
            'status': 'is_live',
            'sourceType': 'youtube-search',
            'discoveredBy': entry.get('search_query') or 'live cam'
        })
        if len(items) >= limit:
            break

    save_geocode_cache(cache)
    return items


def validate_youtube_item(item):
    video_id = item.get('videoId')
    if not video_id:
        item['playbackStatus'] = 'verified' if item.get('embedUrl') else 'unchecked'
        return item

    oembed_url = 'https://www.youtube.com/oembed?format=json&url=' + quote(
        f'https://www.youtube.com/watch?v={video_id}',
        safe=''
    )

    try:
        meta = fetch_json(oembed_url, timeout=10)
        title = str(meta.get('title') or '')
        if UNSTABLE_TITLE.search(title):
            return None
        item['playbackStatus'] = 'verified'
        item['lastCheckedAt'] = dt.date.today().isoformat()
        item['stabilityScore'] = max(75, int(float(item.get('priority') or 60)))
        return item
    except HTTPError as error:
        if error.code in {400, 401, 403, 404}:
            return None
        item['playbackStatus'] = 'unchecked'
        item['lastCheckedAt'] = dt.date.today().isoformat()
        item['stabilityScore'] = min(65, int(float(item.get('priority') or 60)))
        return item
    except Exception:
        item['playbackStatus'] = 'unchecked'
        item['lastCheckedAt'] = dt.date.today().isoformat()
        item['stabilityScore'] = min(65, int(float(item.get('priority') or 60)))
        return item


def calculate_quality_score(item):
    score = float(item.get('priority') or 60)
    source_type = item.get('sourceType') or ('youtube' if item.get('videoId') else 'external')
    title = item.get('title', '')
    subtitle = item.get('subtitle', '')
    combined_title = f'{title} {subtitle}'

    score += SOURCE_QUALITY_BONUS.get(source_type, 0)
    if item.get('playbackStatus') == 'verified':
        score += 8
    elif item.get('playbackStatus') == 'unchecked':
        score -= 12
    if POSITIVE_TITLE.search(combined_title):
        score += 5
    if NEGATIVE_TITLE.search(combined_title):
        score -= 18
    if HARD_NEGATIVE_TITLE.search(combined_title):
        score -= 80
    if item.get('thumbnailUrl'):
        score += 2
    if is_finite_number(item.get('lat')) and is_finite_number(item.get('lng')):
        score += 2
    if item.get('sourceUrl'):
        score += 1
    if source_type == 'youtube-search':
        score -= 3

    return max(0, min(100, int(round(score))))


def is_finite_number(value):
    try:
        number = float(value)
        return number == number and number not in {float('inf'), float('-inf')}
    except (TypeError, ValueError):
        return False


def enrich_item_quality(item):
    score = calculate_quality_score(item)
    item['qualityScore'] = score
    item['stabilityScore'] = max(int(item.get('stabilityScore') or 0), min(100, score))
    item['qualityTier'] = 'excellent' if score >= 88 else 'good' if score >= 76 else 'fair' if score >= 62 else 'watch'
    return item


def validate_items(items):
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        validated = [item for item in executor.map(validate_youtube_item, items) if item]
    return [enrich_item_quality(item) for item in validated if calculate_quality_score(item) >= 52]


def dedupe_items(items):
    by_video = {}
    for item in items:
        video_key = item.get('videoId') or item.get('embedUrl')
        key = video_key or item.get('id') or slugify(item.get('title', ''))
        current = by_video.get(key)
        if current and calculate_quality_score(current) >= calculate_quality_score(item):
            continue
        by_video[key] = item

    by_identity = {}
    for item in by_video.values():
        identity_key = '|'.join([
            re.sub(r'[^a-z0-9가-힣]+', '', str(item.get('title', '')).lower()),
            str(item.get('city', '')).lower(),
            str(item.get('country', '')).lower(),
        ])
        current_identity = by_identity.get(identity_key)
        if current_identity and calculate_quality_score(current_identity) >= calculate_quality_score(item):
            continue
        by_identity[identity_key] = item

    return list(by_identity.values())


def main():
    base = existing_playable_items()
    additions = collect_cctv_world() + collect_tabi() + collect_webcamera24() + collect_youtube_search()
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
    items = dedupe_items(validate_items(list(by_key.values())))
    items.sort(key=lambda item: (
        -(float(item.get('qualityScore') or item.get('stabilityScore') or item.get('priority') or 0)),
        -(float(item.get('priority') or 0)),
        item.get('region', ''),
        item.get('title', '')
    ))
    from collections import Counter
    source_counts = Counter(i.get('sourceType', 'youtube') for i in items)
    region_counts = Counter(i.get('region', 'Other') for i in items)
    playback_counts = Counter(i.get('playbackStatus', 'unknown') for i in items)
    quality_counts = Counter(i.get('qualityTier', 'unknown') for i in items)
    payload = {
        'updated_at': dt.date.today().isoformat(),
        'description': 'Curated public world tourist live/webcam directory. Only in-app playable YouTube/embed streams are included; source-site-only players are excluded.',
        'collectionMeta': {
            'itemCount': len(items),
            'sourceCounts': dict(source_counts),
            'regionCounts': dict(region_counts),
            'playbackCounts': dict(playback_counts),
            'qualityTiers': dict(quality_counts),
            'youtubeSearchQueries': youtube_search_queries(),
            'youtubeSearchLimit': YOUTUBE_SEARCH_LIMIT,
            'youtubeSearchPerQueryLimit': YOUTUBE_SEARCH_PER_QUERY_LIMIT,
            'qualityPolicy': 'verified playback, source trust, positive tourist context, and coordinate availability are scored before ranking.'
        },
        'items': items
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print('items', len(items))
    print('sources', dict(source_counts))
    print('regions', dict(region_counts))
    print('external_only', sum(1 for i in items if not (i.get('videoId') or i.get('embedUrl'))))
    print('playback', dict(playback_counts))
    print('quality', dict(quality_counts))

if __name__ == '__main__':
    main()
