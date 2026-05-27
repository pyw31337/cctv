import concurrent.futures
import csv
import datetime as dt
import html
import io
import json
import math
import os
import re
import signal
import ssl
import shutil
import subprocess
import time
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / 'data/world_tour_cams.json'
GEOCODE_CACHE_PATH = ROOT / '.cache/world_tour_geocode_cache.json'
HTTP_CACHE_PATH = ROOT / '.cache/world_tour_http_cache.json'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
}
NOMINATIM_HEADERS = {
    **HEADERS,
    'User-Agent': 'pyw31337-cctv-world-tour/1.0 (https://pyw31337.github.io/cctv/)'
}
UNVERIFIED_SSL_CONTEXT = ssl._create_unverified_context()
REGION_BY_COUNTRY = {
    'United States': 'North America', 'Canada': 'North America', 'Mexico': 'North America',
    'Panama': 'North America', 'Greenland': 'North America', 'Jamaica': 'North America', 'Curaçao': 'North America',
    'Sint Maarten': 'North America', 'Puerto Rico': 'North America', 'Vatican City': 'Europe',
    'Aruba': 'North America', 'Bahamas': 'North America', 'Barbados': 'North America', 'Belize': 'North America',
    'Bermuda': 'North America', 'Costa Rica': 'North America', 'Dominican Republic': 'North America',
    'El Salvador': 'North America', 'Grenada': 'North America', 'Guadeloupe': 'North America',
    'Honduras': 'North America', 'Martinique': 'North America', 'Cayman Islands': 'North America',
    'Anguilla': 'North America', 'Antigua and Barbuda': 'North America', 'British Virgin Islands': 'North America',
    'Saint Barthélemy': 'North America', 'Saint Martin': 'North America', 'Turks and Caicos Islands': 'North America',
    'U.S. Virgin Islands': 'North America', 'United States Virgin Islands': 'North America',
    'France': 'Europe', 'Italy': 'Europe', 'United Kingdom': 'Europe', 'Spain': 'Europe', 'Greece': 'Europe',
    'Germany': 'Europe', 'Switzerland': 'Europe', 'Netherlands': 'Europe', 'Norway': 'Europe', 'Finland': 'Europe',
    'Denmark': 'Europe', 'Czech Republic': 'Europe', 'Austria': 'Europe', 'Hungary': 'Europe', 'Ireland': 'Europe',
    'Portugal': 'Europe', 'Belgium': 'Europe', 'Bulgaria': 'Europe', 'Croatia': 'Europe', 'Estonia': 'Europe',
    'Iceland': 'Europe', 'Latvia': 'Europe', 'Liechtenstein': 'Europe', 'Lithuania': 'Europe', 'Montenegro': 'Europe',
    'Poland': 'Europe', 'Romania': 'Europe', 'Russia': 'Europe', 'San Marino': 'Europe', 'Slovakia': 'Europe',
    'Sweden': 'Europe', 'Ukraine': 'Europe', 'Vatican': 'Europe', 'Belarus': 'Europe',
    'Albania': 'Europe', 'Andorra': 'Europe', 'Bosnia and Herzegovina': 'Europe', 'Cyprus': 'Europe',
    'Luxembourg': 'Europe', 'Malta': 'Europe', 'Moldova': 'Europe', 'Monaco': 'Europe',
    'North Macedonia': 'Europe', 'Serbia': 'Europe', 'Slovenia': 'Europe',
    'Turkey': 'Asia', 'Japan': 'Asia', 'South Korea': 'Asia', 'Taiwan': 'Asia', 'China': 'Asia',
    'Thailand': 'Asia', 'Indonesia': 'Asia', 'Israel': 'Asia', 'India': 'Asia', 'Malaysia': 'Asia',
    'Maldives': 'Asia', 'Philippines': 'Asia', 'Saudi Arabia': 'Asia', 'Singapore': 'Asia', 'Vietnam': 'Asia',
    'Georgia': 'Asia', 'Hong Kong': 'Asia', 'United Arab Emirates': 'Asia', 'Australia': 'Oceania', 'New Zealand': 'Oceania',
    'Brazil': 'South America', 'Chile': 'South America', 'Argentina': 'South America', 'Bolivia': 'South America',
    'Colombia': 'South America', 'Ecuador': 'South America', 'Peru': 'South America', 'Uruguay': 'South America',
    'Venezuela': 'South America',
    'South Africa': 'Africa', 'Kenya': 'Africa', 'Botswana': 'Africa', 'Cape Verde': 'Africa', 'Egypt': 'Africa', 'Namibia': 'Africa',
    'Mauritius': 'Africa', 'Morocco': 'Africa', 'Senegal': 'Africa', 'Seychelles': 'Africa', 'Tanzania': 'Africa',
    'Zambia': 'Africa'
}
COUNTRY_BY_SLUG = {
    'usa': 'United States', 'japan': 'Japan', 'south-korea': 'South Korea', 'italy': 'Italy', 'france': 'France',
    'spain': 'Spain', 'greece': 'Greece', 'thailand': 'Thailand', 'australia': 'Australia', 'canada': 'Canada',
    'united-kingdom': 'United Kingdom', 'brazil': 'Brazil', 'germany': 'Germany', 'switzerland': 'Switzerland',
    'netherlands': 'Netherlands', 'china': 'China', 'taiwan': 'Taiwan', 'mexico': 'Mexico', 'norway': 'Norway',
    'finland': 'Finland', 'south-africa': 'South Africa', 'new-zealand': 'New Zealand', 'indonesia': 'Indonesia',
    'turkey': 'Turkey', 'israel': 'Israel', 'kenya': 'Kenya', 'botswana': 'Botswana', 'denmark': 'Denmark', 'austria': 'Austria',
    'belarus': 'Belarus', 'belgium': 'Belgium', 'bulgaria': 'Bulgaria', 'cape-verde': 'Cape Verde',
    'chile': 'Chile', 'croatia': 'Croatia', 'czech': 'Czech Republic', 'egypt': 'Egypt', 'estonia': 'Estonia',
    'georgia': 'Georgia', 'greenland': 'Greenland', 'hungary': 'Hungary', 'iceland': 'Iceland', 'india': 'India',
    'ireland': 'Ireland', 'latvia': 'Latvia', 'liechtenstein': 'Liechtenstein', 'lithuania': 'Lithuania',
    'malaysia': 'Malaysia', 'maldives': 'Maldives', 'mauritius': 'Mauritius', 'montenegro': 'Montenegro',
    'morocco': 'Morocco', 'panama': 'Panama', 'philippines': 'Philippines', 'poland': 'Poland',
    'portugal': 'Portugal', 'romania': 'Romania', 'russia': 'Russia', 'san-marino': 'San Marino',
    'saudi-arabia': 'Saudi Arabia', 'singapore': 'Singapore', 'slovakia': 'Slovakia', 'sweden': 'Sweden',
    'united-states': 'United States', 'vatican-city': 'Vatican City',
    'ukraine': 'Ukraine', 'vatican': 'Vatican', 'vietnam': 'Vietnam'
}
SOURCE_COUNTRY_BY_SLUG = {
    **COUNTRY_BY_SLUG,
    'australia-oceania': 'Australia',
    'brasil': 'Brazil',
    'czech-republic': 'Czech Republic',
    'deutschland': 'Germany',
    'ellada': 'Greece',
    'espana': 'Spain',
    'faroe-islands': 'Denmark',
    'hrvatska': 'Croatia',
    'italia': 'Italy',
    'malta': 'Malta',
    'norge': 'Norway',
    'repubblica-di-san-marino': 'San Marino',
    'republic-of-san-marino': 'San Marino',
    'schweiz': 'Switzerland',
    'scotland': 'United Kingdom',
    'slovenia': 'Slovenia',
    'slovenija': 'Slovenia',
    'u-k': 'United Kingdom',
    'vatican-city': 'Vatican City',
    'wales': 'United Kingdom',
    'zanzibar': 'Tanzania',
    'andorra': 'Andorra',
    'albania': 'Albania',
    'bosnia-and-herzegovina': 'Bosnia and Herzegovina',
    'bosnia-herzegovina': 'Bosnia and Herzegovina',
    'british-virgin-islands': 'British Virgin Islands',
    'antigua-and-barbuda': 'Antigua and Barbuda',
    'cyprus': 'Cyprus',
    'czechia': 'Czech Republic',
    'dominican-republic': 'Dominican Republic',
    'luxembourg': 'Luxembourg',
    'monaco': 'Monaco',
    'north-macedonia': 'North Macedonia',
    'serbia': 'Serbia',
    'turks-and-caicos': 'Turks and Caicos Islands',
    'turks-and-caicos-islands': 'Turks and Caicos Islands',
    'u-s-virgin-islands': 'U.S. Virgin Islands',
    'us-virgin-islands': 'U.S. Virgin Islands',
}
COUNTRY_NORMALIZATION = {
    'Andorra': 'Andorra',
    'Belgien': 'Belgium',
    'Czechia': 'Czech Republic',
    'Deutschland': 'Germany',
    'England': 'United Kingdom',
    'Grönland': 'Greenland',
    'Greenlandic': 'Greenland',
    'Italien': 'Italy',
    'Northern Ireland': 'United Kingdom',
    'Österreich': 'Austria',
    'Republic of San Marino': 'San Marino',
    'San Marino Republic': 'San Marino',
    'Schweiz': 'Switzerland',
    'Scotland': 'United Kingdom',
    'Slowakei': 'Slovakia',
    'Spanien': 'Spain',
    'Tschechien': 'Czech Republic',
    'U.K.': 'United Kingdom',
    'UK': 'United Kingdom',
    'USA': 'United States',
    'Usa': 'United States',
    'United States of America': 'United States',
    'US Virgin Islands': 'U.S. Virgin Islands',
    'Vatican': 'Vatican City',
    'Wales': 'United Kingdom',
}
HARD_NEGATIVE_TITLE = re.compile(r'(트로피컬\s*머피|바오밥\s*레스토랑|스키드\s*로우|캠핑\s*프리베|트럭\s*대기열|송골매|둥지|코끼리|Kensington|Skid Row|Sloppy|Murphy|Truck Queue|Camping Prive|Falcon|Nest|Elephant)', re.I)
NEGATIVE_TITLE = re.compile(r'(고양이|독수리|새 모이|피더|동물|야생동물|\b(Alligator|Spoonbill|Osprey|Otter|Eagle|Cat|Feeder|Wildlife|Zoo|Bird|Animal|Penguin|Parrot|Bear|Bison|Wolf|Tiger|Lion)\b|카지노)', re.I)
POSITIVE_TITLE = re.compile(r'(타임|광장|해변|비치|항구|하버|공항|타워|브리지|대교|성|궁|공원|강|시티|도시|스카이라인|라이브|역|거리|마켓|파노라마|폭포|산|리조트|마리나|해안|도쿄|오사카|서울|부산|뉴욕|파리|런던|로마|베니스|교토|후지|시부야|Times|Square|Beach|Harbour|Harbor|Airport|Tower|Bridge|Castle|Park|River|Skyline|City|Panorama|Falls|Mountain|Resort|Marina)', re.I)
UNSTABLE_TITLE = re.compile(r'(private video|deleted video|video unavailable|비공개|삭제|사용할 수 없는)', re.I)
YOUTUBE_SEARCH_LIMIT = int(os.getenv('WORLD_TOUR_YOUTUBE_SEARCH_LIMIT', '420'))
YOUTUBE_SEARCH_PER_QUERY_LIMIT = int(os.getenv('WORLD_TOUR_YOUTUBE_SEARCH_PER_QUERY_LIMIT', '48'))
WORLD_TOUR_EARTHCAM_LIMIT = int(os.getenv('WORLD_TOUR_EARTHCAM_LIMIT', '90'))
WORLD_TOUR_WORLDCAM_LIMIT = int(os.getenv('WORLD_TOUR_WORLDCAM_LIMIT', '130'))
WORLD_TOUR_BALTIC_LIMIT = int(os.getenv('WORLD_TOUR_BALTIC_LIMIT', '70'))
WORLD_TOUR_SKYLINE_LIMIT = int(os.getenv('WORLD_TOUR_SKYLINE_LIMIT', '70'))
WORLD_TOUR_WEBCAMERA24_LIMIT = int(os.getenv('WORLD_TOUR_WEBCAMERA24_LIMIT', '190'))
WORLD_TOUR_WINDY_LIMIT = int(os.getenv('WORLD_TOUR_WINDY_LIMIT', '0'))
WORLD_TOUR_LIVEBEACHES_LIMIT = int(os.getenv('WORLD_TOUR_LIVEBEACHES_LIMIT', '45'))
WORLD_TOUR_CAMSCAPE_LIMIT = int(os.getenv('WORLD_TOUR_CAMSCAPE_LIMIT', '45'))
WORLD_TOUR_EXPLORE_LIMIT = int(os.getenv('WORLD_TOUR_EXPLORE_LIMIT', '35'))
WORLD_TOUR_WHATSUP_LIMIT = int(os.getenv('WORLD_TOUR_WHATSUP_LIMIT', '80'))
WORLD_TOUR_BERGFEX_LIMIT = int(os.getenv('WORLD_TOUR_BERGFEX_LIMIT', '35'))
WORLD_TOUR_FERATEL_LIMIT = int(os.getenv('WORLD_TOUR_FERATEL_LIMIT', '80'))
WORLD_TOUR_HDONTAP_LIMIT = int(os.getenv('WORLD_TOUR_HDONTAP_LIMIT', '55'))
WORLD_TOUR_ROUNDSHOT_LIMIT = int(os.getenv('WORLD_TOUR_ROUNDSHOT_LIMIT', '45'))
WORLD_TOUR_TWLIVECAM_LIMIT = int(os.getenv('WORLD_TOUR_TWLIVECAM_LIMIT', '55'))
WORLD_TOUR_WORLDCAMLIVE_LIMIT = int(os.getenv('WORLD_TOUR_WORLDCAMLIVE_LIMIT', '55'))
WORLD_TOUR_ALERTCALIFORNIA_LIMIT = int(os.getenv('WORLD_TOUR_ALERTCALIFORNIA_LIMIT', '12'))
WORLD_TOUR_WETTER_LIMIT = int(os.getenv('WORLD_TOUR_WETTER_LIMIT', '35'))
WORLD_TOUR_PANORAMASK_LIMIT = int(os.getenv('WORLD_TOUR_PANORAMASK_LIMIT', '30'))
WORLD_TOUR_IDOKEP_LIMIT = int(os.getenv('WORLD_TOUR_IDOKEP_LIMIT', '35'))
WORLD_TOUR_PTZTV_LIMIT = int(os.getenv('WORLD_TOUR_PTZTV_LIMIT', '22'))
WORLD_TOUR_RAILCAM_LIMIT = int(os.getenv('WORLD_TOUR_RAILCAM_LIMIT', '4'))
WORLD_TOUR_PUBLIC_TRAFFIC_LIMIT = int(os.getenv('WORLD_TOUR_PUBLIC_TRAFFIC_LIMIT', '12'))
WORLD_TOUR_HTTP_CACHE_TTL_HOURS = float(os.getenv('WORLD_TOUR_HTTP_CACHE_TTL_HOURS', '24'))
WORLD_TOUR_STALE_CACHE_HOURS = float(os.getenv('WORLD_TOUR_STALE_CACHE_HOURS', '168'))
WORLD_TOUR_HTTP_TIMEOUT_CAP = float(os.getenv('WORLD_TOUR_HTTP_TIMEOUT_CAP', '14'))
WORLD_TOUR_SOURCE_ENRICH_LIMIT = int(os.getenv('WORLD_TOUR_SOURCE_ENRICH_LIMIT', '160'))
WORLD_TOUR_COLLECTOR_TIMEOUT_SECONDS = int(os.getenv('WORLD_TOUR_COLLECTOR_TIMEOUT_SECONDS', '150'))
WORLD_TOUR_LIVEWORLDWEBCAMS_LIMIT = int(os.getenv('WORLD_TOUR_LIVEWORLDWEBCAMS_LIMIT', '24'))
WORLD_TOUR_WEBCAMHOPPER_LIMIT = int(os.getenv('WORLD_TOUR_WEBCAMHOPPER_LIMIT', '24'))
WORLD_TOUR_WORLDCAMTV_LIMIT = int(os.getenv('WORLD_TOUR_WORLDCAMTV_LIMIT', '12'))
WORLD_TOUR_LIVECAMCROATIA_LIMIT = int(os.getenv('WORLD_TOUR_LIVECAMCROATIA_LIMIT', '18'))
WORLD_TOUR_OPENWEBCAMDB_LIMIT = int(os.getenv('WORLD_TOUR_OPENWEBCAMDB_LIMIT', '0'))
WORLD_TOUR_VIEWSURF_LIMIT = int(os.getenv('WORLD_TOUR_VIEWSURF_LIMIT', '24'))
WORLD_TOUR_AIRPORTWEBCAMS_LIMIT = int(os.getenv('WORLD_TOUR_AIRPORTWEBCAMS_LIMIT', '24'))
WORLD_TOUR_PANOMAX_LIMIT = int(os.getenv('WORLD_TOUR_PANOMAX_LIMIT', '40'))
WORLD_TOUR_WEBCAMSMEXICO_LIMIT = int(os.getenv('WORLD_TOUR_WEBCAMSMEXICO_LIMIT', '60'))
WORLD_TOUR_CLIMAAOVIVO_LIMIT = int(os.getenv('WORLD_TOUR_CLIMAAOVIVO_LIMIT', '70'))
WORLD_TOUR_HKTRAFFIC_LIMIT = int(os.getenv('WORLD_TOUR_HKTRAFFIC_LIMIT', '70'))
WORLD_TOUR_USGS_VOLCANO_LIMIT = int(os.getenv('WORLD_TOUR_USGS_VOLCANO_LIMIT', '45'))
WORLD_TOUR_AURORAINFO_LIMIT = int(os.getenv('WORLD_TOUR_AURORAINFO_LIMIT', '12'))
WORLD_TOUR_NSW_TRAFFIC_LIMIT = int(os.getenv('WORLD_TOUR_NSW_TRAFFIC_LIMIT', '28'))
WORLD_TOUR_DC_TRAFFIC_LIMIT = int(os.getenv('WORLD_TOUR_DC_TRAFFIC_LIMIT', '28'))
WORLD_TOUR_AFRICAM_LIMIT = int(os.getenv('WORLD_TOUR_AFRICAM_LIMIT', '18'))
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
    'earthcam': 7,
    'cctvworld': 6,
    'worldcam': 5,
    'tabi': 4,
    'baltic': 3,
    'skyline': 3,
    'webcamtaxi': 3,
    'windy': 6,
    'feratel': 5,
    'roundshot': 5,
    'whatsupcams': 5,
    'twlivecam': 4,
    'hdontap': 4,
    'livebeaches': 4,
    'explore': 4,
    'worldcamlive': 3,
    'alertcalifornia': 3,
    'wetter': 4,
    'panoramask': 3,
    'bergfex': 3,
    'camscape': 3,
    'idokep': 4,
    'ptztv': 4,
    'railcam': 5,
    'railcamuk': 5,
    'publictraffic': 3,
    'liveworldwebcams': 4,
    'webcamhopper': 4,
    'worldcamtv': 4,
    'livecamcroatia': 4,
    'openwebcamdb': 4,
    'airportwebcams': 4,
    'viewsurf': 5,
    'panomax': 5,
    'webcamsdemexico': 5,
    'climaaovivo': 5,
    'hktraffic': 4,
    'usgsvolcano': 5,
    'aurorainfo': 5,
    'nswtraffic': 4,
    'dctraffic': 4,
    'africam': 5,
    'weatherbug': 3,
    'surfline': 3,
    'japanwebcams': 4,
    'spacecam': 8,
    'animalcam': 8,
    'golfcam': 6,
    'webcamera24': 2,
    'youtube-search': 0,
    'external': -8,
}
WILDLIFE_SOURCE_TYPES = {'explore', 'hdontap', 'animalcam', 'africam'}
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
SOURCE_LOCATION_HINTS = [
    (('mpala research centre', 'laikipia'), 'Mpala Research Centre', 'Laikipia County', 'Kenya', 'Africa', 0.2830, 36.9000),
    (('blue spring state park', 'orange city'), 'Blue Spring State Park', 'Orange City', 'United States', 'North America', 28.9474, -81.3396),
    (('st. augustine', 'alligator farm'), "St. Augustine Alligator Farm", 'St. Augustine', 'United States', 'North America', 29.8790, -81.2870),
    (('channel islands national park', 'anacapa'), 'Anacapa Island', 'Santa Barbara County', 'United States', 'North America', 34.0150, -119.3670),
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

CCTV_WORLD_ORIGIN_META = {
    # CCTV World embeds several Korea National Park Service cameras through
    # originUrl + /api/knps-m3u8 instead of YouTube. These direct HLS streams
    # are CORS-enabled and can be played in-app, so they should not be lost.
    'ulsan-bawui': ('울산바위', '설악산 울산바위와 국립공원 전망', 'Sokcho', 'South Korea', 38.1190, 128.4650, 84, 'national-park'),
    'baekundae': ('백운대', '북한산 백운대 국립공원 전망', 'Seoul', 'South Korea', 37.6580, 126.9780, 78, 'national-park'),
    'sapaesan': ('사패산', '북한산국립공원 사패산 전망', 'Uijeongbu', 'South Korea', 37.7240, 127.0120, 74, 'national-park'),
    'duroryeong': ('두로령', '오대산 두로령 국립공원 전망', 'Pyeongchang', 'South Korea', 37.7800, 128.5900, 72, 'national-park'),
    'sangwonsa': ('상원사', '오대산 상원사 국립공원 전망', 'Pyeongchang', 'South Korea', 37.7900, 128.5630, 72, 'national-park'),
    'hakampo': ('학암포', '태안해안 학암포 해변 국립공원 전망', 'Taean', 'South Korea', 36.8970, 126.1980, 74, 'national-park'),
    'cheonjaedan': ('천제단', '태백산 천제단 국립공원 전망', 'Taebaek', 'South Korea', 37.0950, 128.9160, 74, 'national-park'),
    'cheonhwangbong': ('천황봉', '지리산 천왕봉 국립공원 전망', 'Sancheong', 'South Korea', 35.3360, 127.7310, 78, 'national-park'),
    'cheonwangbong': ('천왕봉', '지리산 천왕봉 국립공원 전망', 'Sancheong', 'South Korea', 35.3360, 127.7310, 78, 'national-park'),
    'yeonhwabong': ('연화봉', '소백산 연화봉 국립공원 전망', 'Danyang', 'South Korea', 36.9570, 128.4840, 74, 'national-park'),
    'giam': ('기암', '주왕산 기암 국립공원 전망', 'Cheongsong', 'South Korea', 36.3940, 129.1620, 72, 'national-park'),
    'jookmaktambangro': ('죽막탐방로', '변산반도 죽막탐방로 국립공원 전망', 'Buan', 'South Korea', 35.6350, 126.4700, 72, 'national-park'),
    'seolcheonbong': ('설천봉', '덕유산 설천봉 국립공원 전망', 'Muju', 'South Korea', 35.8940, 127.7460, 76, 'national-park'),
    'jangteomok': ('장터목', '지리산 장터목 국립공원 전망', 'Sancheong', 'South Korea', 35.3150, 127.7550, 74, 'national-park'),
    'gaksan': ('각산', '한려해상 각산 전망', 'Sacheon', 'South Korea', 34.9800, 128.0600, 70, 'national-park'),
    'jangbuljae': ('장불재', '무등산 장불재 국립공원 전망', 'Gwangju', 'South Korea', 35.1340, 126.9940, 73, 'national-park'),
    'jiricheongsong-beach': ('지리청송해변', '해안 국립공원 실시간 전망', 'South Korea', 'South Korea', 35.3300, 127.7300, 68, 'national-park'),
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

EARTHCAM_STATE_TARGETS = ['NY', 'CA', 'FL', 'HI', 'IL', 'DC', 'MA', 'WA', 'AZ', 'NV', 'TX', 'CO', 'TN', 'VA']
EARTHCAM_COUNTRY_TARGETS = ['Canada', 'England', 'Italy', 'South Korea', 'Spain', 'Germany', 'Netherlands', 'New Zealand', 'Taiwan', 'Jamaica']
WORLDCAM_LIST_URLS = [
    'https://worldcam.eu/webcams/asia/japan',
    'https://worldcam.eu/webcams/asia/south-korea',
    'https://worldcam.eu/webcams/asia/thailand',
    'https://worldcam.eu/webcams/europe/italy',
    'https://worldcam.eu/webcams/europe/france',
    'https://worldcam.eu/webcams/europe/spain',
    'https://worldcam.eu/webcams/europe/united-kingdom',
    'https://worldcam.eu/webcams/europe/germany',
    'https://worldcam.eu/webcams/north-america/united-states',
    'https://worldcam.eu/webcams/north-america/canada',
    'https://worldcam.eu/webcams/south-america/brazil',
    'https://worldcam.eu/webcams/australia-oceania/australia',
]
SKYLINE_LIST_URLS = [
    'https://www.skylinewebcams.com/en/webcam.html',
    'https://www.skylinewebcams.com/en/top-live-cams.html',
    'https://www.skylinewebcams.com/en/webcam/city-cams.html',
    'https://www.skylinewebcams.com/en/webcam/beach-cams.html',
    'https://www.skylinewebcams.com/en/webcam/unesco.html',
]
WEBCAMTAXI_SEEDS = [
    ('shibuya-crossing', 'Shibuya Scramble Crossing', 'Tokyo street and traffic crossing live webcam', 'Tokyo', 'Japan', 'Asia', 35.6595, 139.7005, 'https://www.webcamtaxi.com/en/japan/tokyo/shibuya-crossing.html', 72),
    ('lower-manhattan', 'Lower Manhattan New York Cam', 'Lower Manhattan skyline and river live webcam', 'New York', 'United States', 'North America', 40.7060, -74.0086, 'https://www.webcamtaxi.com/en/usa/new-york/manhattan-skyline.html', 70),
    ('st-peters-square', "St. Peter's Square", 'Vatican City square and basilica live webcam', 'Vatican City', 'Vatican City', 'Europe', 41.9022, 12.4539, 'https://www.webcamtaxi.com/en/vatican/vatican-city/st-peters-square.html', 70),
    ('sydney-harbour-webcamtaxi', 'Sydney Harbour Cam', 'Sydney Harbour and city waterfront live webcam', 'Sydney', 'Australia', 'Oceania', -33.8568, 151.2153, 'https://www.webcamtaxi.com/en/australia/new-south-wales/sydney-harbour.html', 68),
    ('london-heathrow', 'London Heathrow Airport Cam', 'London Heathrow airport runway live webcam', 'London', 'United Kingdom', 'Europe', 51.4700, -0.4543, 'https://www.webcamtaxi.com/en/england/london/london-heathrow-airport.html', 66),
    ('benidorm-playa-levante', 'Playa de Levante, Benidorm', 'Benidorm beach live webcam', 'Benidorm', 'Spain', 'Europe', 38.5382, -0.1291, 'https://www.webcamtaxi.com/en/spain/alicante/playa-de-levante-benidorm.html', 66),
    ('times-square-webcamtaxi', 'Times Square, New York', 'New York City street and square live webcam', 'New York', 'United States', 'North America', 40.7580, -73.9855, 'https://www.webcamtaxi.com/en/usa/new-york/times-square.html', 70),
    ('miami-airport-webcamtaxi', 'Miami Airport Cam', 'Miami International Airport runway live webcam', 'Miami', 'United States', 'North America', 25.7959, -80.2870, 'https://www.webcamtaxi.com/en/usa/florida/miami-airport.html', 66),
    ('amsterdam-dam-square-webcamtaxi', 'Amsterdam Dam Square', 'Amsterdam city square live webcam', 'Amsterdam', 'Netherlands', 'Europe', 52.3731, 4.8933, 'https://www.webcamtaxi.com/en/netherlands/north-holland/amsterdam-dam-square.html', 67),
    ('venice-rialto-webcamtaxi', 'Venice Rialto Bridge', 'Grand Canal and Rialto Bridge live webcam', 'Venice', 'Italy', 'Europe', 45.4380, 12.3359, 'https://www.webcamtaxi.com/en/italy/veneto/venice-rialto-bridge.html', 68),
    ('abbey-road-webcamtaxi', 'Abbey Road Crossing', 'London Abbey Road crossing live webcam', 'London', 'United Kingdom', 'Europe', 51.5321, -0.1774, 'https://www.webcamtaxi.com/en/england/london/abbey-road.html', 66),
    ('niagara-falls-webcamtaxi', 'Niagara Falls Cam', 'Niagara Falls live webcam view', 'Niagara Falls', 'Canada', 'North America', 43.0828, -79.0742, 'https://www.webcamtaxi.com/en/canada/ontario/niagara-falls.html', 67),
    ('waikiki-beach-webcamtaxi', 'Waikiki Beach Cam', 'Honolulu Waikiki Beach live webcam', 'Honolulu', 'United States', 'North America', 21.2766, -157.8268, 'https://www.webcamtaxi.com/en/usa/hawaii/waikiki-beach.html', 66),
    ('las-vegas-strip-webcamtaxi', 'Las Vegas Strip Cam', 'Las Vegas Strip street live webcam', 'Las Vegas', 'United States', 'North America', 36.1147, -115.1728, 'https://www.webcamtaxi.com/en/usa/nevada/las-vegas-strip.html', 66),
    ('dublin-port-webcamtaxi', 'Dublin Port Cam', 'Dublin harbour and ferry terminal live webcam', 'Dublin', 'Ireland', 'Europe', 53.3498, -6.1967, 'https://www.webcamtaxi.com/en/ireland/dublin/dublin-port.html', 64),
    ('lisbon-port-webcamtaxi', 'Lisbon Port Cam', 'Tagus river and port live webcam', 'Lisbon', 'Portugal', 'Europe', 38.7071, -9.1364, 'https://www.webcamtaxi.com/en/portugal/lisbon/lisbon-port.html', 64),
]
LIVEBEACHES_SOURCE_SEEDS = [
    ('webcams-ocean-city-md-boardwalk-cam', 'Ocean City, MD Boardwalk Cam', 'Ocean City boardwalk and beach live webcam', 'Ocean City', 'United States', 38.3365, -75.0849, 'https://www.livebeaches.com/webcams/ocean-city-md-boardwalk-cam/', 69, ''),
    ('webcams-watermans-webcam-on-virginia-beach-boardwalk', 'Watermans Virginia Beach Boardwalk', 'Virginia Beach boardwalk live webcam', 'Virginia Beach', 'United States', 36.8529, -75.9780, 'https://www.livebeaches.com/webcams/watermans-webcam-on-virginia-beach-boardwalk/', 69, ''),
    ('webcams-rehoboth-beach-boardwalk-webcam', 'Rehoboth Beach Boardwalk', 'Delaware beach boardwalk live webcam', 'Rehoboth Beach', 'United States', 38.7209, -75.0760, 'https://www.livebeaches.com/webcams/rehoboth-beach-boardwalk-webcam/', 68, ''),
    ('webcams-southernmost-point-webcam-key-west', 'Southernmost Point, Key West', 'Key West Southernmost Point live webcam', 'Key West', 'United States', 24.5465, -81.7975, 'https://www.livebeaches.com/webcams/southernmost-point-webcam-key-west/', 70, 'HDlmUp4JBLg'),
    ('webcams-huntington-beach-pier-live-cam', 'Huntington Beach Pier', 'California surf beach and pier live webcam', 'Huntington Beach', 'United States', 33.6553, -118.0038, 'https://www.livebeaches.com/webcams/huntington-beach-pier-live-cam/', 69, 'mhQjsLBfOoY'),
    ('webcams-kauai-marriott-resort-webcam-kalapaki-beach', 'Kalapaki Beach, Kauai', 'Kauai Kalapaki Beach resort live webcam', 'Lihue', 'United States', 21.9637, -159.3510, 'https://www.livebeaches.com/webcams/kauai-marriott-resort-webcam-kalapaki-beach/', 74, ''),
    ('webcams-maui-sea-shell-condo-beach-cam', 'Maui Sea Shell Condo Beach Cam', 'Maui beach live webcam', 'Maui', 'United States', 20.7310, -156.4500, 'https://www.livebeaches.com/webcams/maui-sea-shell-condo-beach-cam/', 68, ''),
    ('webcams-elvis-beach-bar-live-cam-anguilla', 'Elvis Beach Bar, Anguilla', 'Sandy Ground beach live webcam', 'Sandy Ground', 'Anguilla', 18.2010, -63.0890, 'https://www.livebeaches.com/webcams/elvis-beach-bar-live-cam-anguilla/', 67, ''),
    ('webcams-semiahmoo-marina-live-webcam', 'Semiahmoo Marina Live Webcam', 'Blaine marina and harbor live webcam', 'Blaine', 'United States', 48.9881, -122.7705, 'https://www.livebeaches.com/webcams/semiahmoo-marina-live-webcam/', 67, ''),
    ('webcams-four-seasons-resort-lanai-hawaii', 'Four Seasons Resort Lanai', 'Lanai beach resort live webcam', 'Lanai City', 'United States', 20.7416, -156.8964, 'https://www.livebeaches.com/webcams/four-seasons-resort-lanai-hawaii/', 67, ''),
]
ROUNDSHOT_ROOTS = [
    ('https://zuerichtourismus.roundshot.com/', 'Zürich', 'Switzerland'),
    ('https://glacier3000.roundshot.com/', 'Gstaad', 'Switzerland'),
    ('https://zermatt.roundshot.com/glacierparadise/', 'Zermatt', 'Switzerland'),
    ('https://weggis.roundshot.com/', 'Weggis', 'Switzerland'),
    ('https://jungfrau.roundshot.com/interlaken-harderkulm/', 'Interlaken', 'Switzerland'),
]
TWLIVECAM_SCENIC_PATTERN = re.compile(
    r'(觀光|景點|國家公園|風景區|海|港|山|潭|湖|機場|老街|瀑布|溫泉|公園|夜市|'
    r'台北101|淡水|九份|平溪|日月潭|阿里山|墾丁|七星潭|小琉球|澎湖|陽明山|擎天崗|合歡山|貓空|高雄港|桃園國際機場)',
    re.I,
)
TWLIVECAM_TRAFFIC_PATTERN = re.compile(r'(國道|快速公路|台\d+線|省道|交流道|匝道|隧道|路口|交叉口|往東|往西|往南|往北)')
WORLDCAMLIVE_POSITIVE = re.compile(
    r'(airport|beach|city|harbour|harbor|lake|live|market|molo|panorama|plac|plaza|port|rynek|'
    r'square|street|ul\.|view|widok|zamek|na żywo|lotnisko|jezioro)',
    re.I,
)
WORLDCAMLIVE_NEGATIVE = re.compile(r'(bocian|church|gniazdo|kościo|parafia|sanktuarium|stork|woliery)', re.I)
WETTER_LIST_URLS = [
    ('https://www.wetter.com/hd-live-webcams/', 'Germany'),
    ('https://www.wetter.com/hd-live-webcams/deutschland/', 'Germany'),
    ('https://www.wetter.com/hd-live-webcams/oesterreich/', 'Austria'),
    ('https://www.wetter.com/hd-live-webcams/schweiz/', 'Switzerland'),
    ('https://www.wetter.com/hd-live-webcams/italien/', 'Italy'),
]
PANORAMASK_START_URL = 'https://www.panorama.sk/en/slovakia/webcams'
VIEWSURF_LIST_URLS = [
    ('https://www.viewsurf.com/univers/ville', 'city'),
    ('https://www.viewsurf.com/univers/plage', 'beach'),
    ('https://www.viewsurf.com/univers/montagne', 'mountain'),
    ('https://www.viewsurf.com/univers/trafic', 'traffic'),
]
AIRPORTWEBCAMS_CATEGORY_URLS = [
    'https://airportwebcams.net/category/usa/',
    'https://airportwebcams.net/category/united-kingdom/',
    'https://airportwebcams.net/category/europe/',
    'https://airportwebcams.net/category/international/',
    'https://airportwebcams.net/category/australia/',
    'https://airportwebcams.net/category/canada/',
    'https://airportwebcams.net/category/germany/',
    'https://airportwebcams.net/category/france/',
    'https://airportwebcams.net/category/spain/',
    'https://airportwebcams.net/category/japan/',
]
MEXICO_LOCATION_OVERRIDES = {
    'acapulco': ('Acapulco', 'Mexico', 16.8531, -99.8237),
    'altzomoni': ('Altzomoni', 'Mexico', 19.1182, -98.6546),
    'amealco': ('Amealco', 'Mexico', 20.1877, -100.1446),
    'amecameca': ('Amecameca', 'Mexico', 19.1238, -98.7663),
    'bacalar': ('Bacalar', 'Mexico', 18.6781, -88.3936),
    'cabo san lucas': ('Cabo San Lucas', 'Mexico', 22.8905, -109.9167),
    'cancun': ('Cancun', 'Mexico', 21.1619, -86.8515),
    'ciudad de mexico': ('Mexico City', 'Mexico', 19.4326, -99.1332),
    'cdmx': ('Mexico City', 'Mexico', 19.4326, -99.1332),
    'cozumel': ('Cozumel', 'Mexico', 20.4229, -86.9223),
    'durango': ('Durango', 'Mexico', 24.0277, -104.6532),
    'guadalajara': ('Guadalajara', 'Mexico', 20.6597, -103.3496),
    'guanajuato': ('Guanajuato', 'Mexico', 21.019, -101.2574),
    'hermosillo': ('Hermosillo', 'Mexico', 29.0729, -110.9559),
    'huatulco': ('Huatulco', 'Mexico', 15.7753, -96.2626),
    'isla mujeres': ('Isla Mujeres', 'Mexico', 21.2322, -86.7341),
    'ixtapa zihuatanejo': ('Ixtapa Zihuatanejo', 'Mexico', 17.6615, -101.6046),
    'iztapalapa': ('Mexico City', 'Mexico', 19.3574, -99.0671),
    'leon': ('Leon', 'Mexico', 21.125, -101.686),
    'loreto': ('Loreto', 'Mexico', 26.0118, -111.3438),
    'los cabos': ('Los Cabos', 'Mexico', 22.8905, -109.9167),
    'mazatlan': ('Mazatlan', 'Mexico', 23.2494, -106.4111),
    'monterrey': ('Monterrey', 'Mexico', 25.6866, -100.3161),
    'nuevo vallarta': ('Nuevo Vallarta', 'Mexico', 20.7017, -105.2942),
    'pachuca': ('Pachuca', 'Mexico', 20.1011, -98.7591),
    'patzcuaro': ('Patzcuaro', 'Mexico', 19.5159, -101.6092),
    'playa del carmen': ('Playa del Carmen', 'Mexico', 20.6296, -87.0739),
    'puerto escondido': ('Puerto Escondido', 'Mexico', 15.8719, -97.0767),
    'puerto vallarta': ('Puerto Vallarta', 'Mexico', 20.6534, -105.2253),
    'queretaro': ('Queretaro', 'Mexico', 20.5888, -100.3899),
    'real de catorce': ('Real de Catorce', 'Mexico', 23.6891, -100.8861),
    'san carlos': ('San Carlos', 'Mexico', 27.9586, -111.043),
    'san joaquin': ('San Joaquin', 'Mexico', 20.9157, -99.5681),
    'sisal': ('Sisal', 'Mexico', 21.1667, -90.0333),
    'teotihuacan': ('Teotihuacan', 'Mexico', 19.6925, -98.8438),
    'tequisquiapan': ('Tequisquiapan', 'Mexico', 20.5225, -99.8912),
    'tianguismanalco': ('Tianguismanalco', 'Mexico', 18.9765, -98.4481),
    'tijuana': ('Tijuana', 'Mexico', 32.5149, -117.0382),
    'tlamacas': ('Tlamacas', 'Mexico', 19.0665, -98.6279),
    'tlaxiaco': ('Tlaxiaco', 'Mexico', 17.2692, -97.6805),
    'uruapan': ('Uruapan', 'Mexico', 19.4208, -102.0628),
    'villa de alvarez': ('Villa de Alvarez', 'Mexico', 19.2672, -103.7378),
    'volcan de colima': ('Volcan de Colima', 'Mexico', 19.5141, -103.617),
    'volcan popocatepetl': ('Popocatepetl', 'Mexico', 19.023, -98.622),
}
THEMATIC_SOURCE_SEEDS = [
    ('spacecam', 'nasa-live', 'NASA Live', 'Official NASA live programming and mission streams', 'Kennedy Space Center', 'United States', 28.572872, -80.64898, 'https://www.nasa.gov/live/', 72, 'NASA'),
    ('spacecam', 'iss-earth-views', 'ISS Earth Views', 'NASA external camera views and ISS live video resources', 'Johnson Space Center', 'United States', 29.559684, -95.083097, 'https://eol.jsc.nasa.gov/ESRS/HDEV/', 70, 'NASA'),
    ('animalcam', 'san-diego-zoo-panda', 'San Diego Zoo Panda Cam', 'Official San Diego Zoo Wildlife Alliance live camera', 'San Diego', 'United States', 32.735316, -117.149046, 'https://zoo.sandiegozoo.org/cams/panda-cam', 67, 'San Diego Zoo'),
    ('animalcam', 'san-diego-zoo-koala', 'San Diego Zoo Koala Cam', 'Official San Diego Zoo Wildlife Alliance live camera', 'San Diego', 'United States', 32.735316, -117.149046, 'https://zoo.sandiegozoo.org/cams/koala-cam', 66, 'San Diego Zoo'),
    ('animalcam', 'monterey-bay-kelp-forest', 'Monterey Bay Kelp Forest Cam', 'Official Monterey Bay Aquarium live camera', 'Monterey', 'United States', 36.618259, -121.901394, 'https://www.montereybayaquarium.org/animals/live-cams/kelp-forest-cam', 67, 'Monterey Bay Aquarium'),
    ('animalcam', 'monterey-bay-cam', 'Monterey Bay Cam', 'Official Monterey Bay Aquarium ocean-view live camera', 'Monterey', 'United States', 36.618259, -121.901394, 'https://www.montereybayaquarium.org/animals/live-cams/monterey-bay-cam/', 66, 'Monterey Bay Aquarium'),
    ('golfcam', 'pebble-beach-golf-links', 'Pebble Beach Golf Links', 'Official live golf course cameras from Pebble Beach Golf Links', 'Pebble Beach', 'United States', 36.568918, -121.950625, 'https://www.pebblebeach.com/golf/pebble-beach-golf-links/live-golf-cams/', 66, 'Pebble Beach'),
    ('airportwebcams', 'london-heathrow', 'London Heathrow Airport', 'AirportWebcams.net airport runway and apron camera directory page', 'London', 'United Kingdom', 51.4700, -0.4543, 'https://airportwebcams.net/london-heathrow-airport-webcam/', 66, 'AirportWebcams.net'),
    ('airportwebcams', 'los-angeles-lax', 'Los Angeles LAX Airport', 'AirportWebcams.net airport camera directory page', 'Los Angeles', 'United States', 33.9416, -118.4085, 'https://airportwebcams.net/los-angeles-lax-airport-webcam/', 66, 'AirportWebcams.net'),
    ('airportwebcams', 'princess-juliana', 'St Maarten Princess Juliana Airport', 'AirportWebcams.net airport beach approach camera directory page', 'Simpson Bay', 'Sint Maarten', 18.0410, -63.1089, 'https://airportwebcams.net/st-maarten-princess-juliana-airport-webcam/', 66, 'AirportWebcams.net'),
    ('airportwebcams', 'new-york-jfk', 'New York JFK International Airport', 'AirportWebcams.net airport camera directory page', 'New York', 'United States', 40.6413, -73.7781, 'https://airportwebcams.net/new-york-jfk-airport-webcam/', 65, 'AirportWebcams.net'),
    ('airportwebcams', 'zurich-airport', 'Zurich Airport', 'AirportWebcams.net airport camera directory page', 'Zurich', 'Switzerland', 47.4581, 8.5555, 'https://airportwebcams.net/zurich-airport-webcam/', 66, 'AirportWebcams.net'),
    ('airportwebcams', 'naha-airport', 'Naha Airport', 'AirportWebcams.net airport camera directory page', 'Naha', 'Japan', 26.1958, 127.6458, 'https://airportwebcams.net/naha-airport-webcam/', 65, 'AirportWebcams.net'),
    ('airportwebcams', 'prague-vaclav-havel', 'Prague Vaclav Havel Airport', 'AirportWebcams.net airport camera directory page', 'Prague', 'Czech Republic', 50.1008, 14.2632, 'https://airportwebcams.net/prague-vaclav-havel-airport-webcam/', 65, 'AirportWebcams.net'),
    ('airportwebcams', 'faro-airport', 'Faro International Airport', 'AirportWebcams.net airport camera directory page', 'Faro', 'Portugal', 37.0144, -7.9659, 'https://airportwebcams.net/faro-international-airport-webcam/', 64, 'AirportWebcams.net'),
    ('weatherbug', 'weatherbug-new-york', 'New York Weather Cameras', 'WeatherBug local weather camera page for New York City', 'New York', 'United States', 40.7128, -74.0060, 'https://www.weatherbug.com/weather-camera/new-york-ny-10001/', 63, 'WeatherBug'),
    ('weatherbug', 'weatherbug-atlanta', 'Atlanta Weather Cameras', 'WeatherBug local weather camera page for Atlanta including Mercedes-Benz Stadium', 'Atlanta', 'United States', 33.7490, -84.3880, 'https://www.weatherbug.com/weather-camera/atlanta-ga-30303', 63, 'WeatherBug'),
    ('weatherbug', 'weatherbug-naples', 'Naples Weather Cameras', 'WeatherBug local weather camera page for Naples and Kalea Bay', 'Naples', 'United States', 26.1420, -81.7948, 'https://www.weatherbug.com/weather-camera/naples-fl-34102', 62, 'WeatherBug'),
    ('weatherbug', 'weatherbug-sedona', 'Sedona Weather Cameras', 'WeatherBug local weather camera page for Sedona airport and red rock weather views', 'Sedona', 'United States', 34.8697, -111.7610, 'https://www.weatherbug.com/weather-camera/sedona-az-86336', 62, 'WeatherBug'),
    ('surfline', 'pipeline-oahu', 'Pipeline Surf Cam', 'Surfline surf report and webcam page for Pipeline on Oahu', 'Oahu', 'United States', 21.6651, -158.0534, 'https://www.surfline.com/surf-report/pipeline/5842041f4e65fad6a7708df3', 62, 'Surfline'),
    ('surfline', 'huntington-beach', 'Huntington Beach Pier Surf Cam', 'Surfline surf report and webcam page for Huntington Beach Pier', 'Huntington Beach', 'United States', 33.6553, -118.0030, 'https://www.surfline.com/surf-report/huntington-pier/5842041f4e65fad6a7708827', 62, 'Surfline'),
    ('surfline', 'bondi-beach', 'Bondi Beach Surf Cam', 'Surfline surf report and webcam page for Bondi Beach', 'Sydney', 'Australia', -33.8915, 151.2767, 'https://www.surfline.com/surf-report/bondi-beach/5842041f4e65fad6a7708993', 62, 'Surfline'),
    ('surfline', 'uluwatu', 'Uluwatu Surf Cam', 'Surfline surf report and webcam page for Uluwatu, Bali', 'Bali', 'Indonesia', -8.8154, 115.0873, 'https://www.surfline.com/surf-report/uluwatu/5842041f4e65fad6a7708b1a', 62, 'Surfline'),
    ('railcamuk', 'crewe', 'Railcam UK - Crewe', 'Railcam UK main-line railway camera network location', 'Crewe', 'United Kingdom', 53.0890, -2.4320, 'https://www.railcam.uk/caminfo.php', 64, 'Railcam UK'),
    ('railcamuk', 'peterborough', 'Railcam UK - Peterborough', 'Railcam UK main-line railway camera network location', 'Peterborough', 'United Kingdom', 52.5740, -0.2500, 'https://www.railcam.uk/caminfo.php', 64, 'Railcam UK'),
    ('railcamuk', 'settle-carlisle', 'Railcam UK - Settle & Carlisle Line', 'Railcam UK scenic railway camera network location', 'Settle', 'United Kingdom', 54.0680, -2.2770, 'https://www.railcam.uk/caminfo.php', 63, 'Railcam UK'),
    ('japanwebcams', 'sakuralivecams-tokyo', 'Tokyo Live Webcams', 'Sakura Live Cams Tokyo directory with Shibuya, Shinjuku and Tokyo Tower cameras', 'Tokyo', 'Japan', 35.6762, 139.6503, 'https://sakuralivecams.com/', 65, 'Sakura Live Cams'),
    ('japanwebcams', 'sakuralivecams-osaka', 'Osaka Live Webcams', 'Sakura Live Cams Osaka directory with Dotonbori, airport and skyline cameras', 'Osaka', 'Japan', 34.6937, 135.5023, 'https://sakuralivecams.com/', 64, 'Sakura Live Cams'),
    ('japanwebcams', 'sakuralivecams-mount-fuji', 'Mount Fuji Live Webcams', 'Sakura Live Cams Mount Fuji directory with multiple Fuji viewpoints', 'Fujikawaguchiko', 'Japan', 35.5013, 138.7657, 'https://sakuralivecams.com/', 65, 'Sakura Live Cams'),
]
EXPLORE_SOURCE_SEEDS = [
    ('northern-lights-cam', 'Northern Lights Cam', 'Aurora borealis live camera from Churchill, Manitoba', 'Churchill', 'Canada', 58.7684, -94.16496, 'https://explore.org/livecams/aurora-borealis-northern-lights/northern-lights-cam', 70),
    ('waikiki-aquarium-cam', 'Waikiki Aquarium Cam', 'Ocean-view live camera near Waikiki Beach', 'Honolulu', 'United States', 21.2659, -157.8212, 'https://explore.org/livecams/hawaii/waikiki-aquarium-cam', 68),
    ('bracken-bat-cave', 'Bracken Bat Cave Viewing Area', 'Live nature camera near Bracken Cave Preserve', 'San Antonio', 'United States', 29.692, -98.354, 'https://explore.org/livecams/bats/bracken-bat-cave', 64),
    ('brooks-falls-brown-bears', 'Brooks Falls Brown Bears', 'Katmai National Park river live camera', 'Katmai National Park', 'United States', 58.5540, -155.7750, 'https://explore.org/livecams/brown-bears/brown-bear-salmon-cam-brooks-falls', 66),
    ('shark-lagoon-cam', 'Shark Lagoon Cam', 'Aquarium of the Pacific live lagoon camera', 'Long Beach', 'United States', 33.7633, -118.1968, 'https://explore.org/livecams/aquarium-of-the-pacific/shark-lagoon-cam', 65),
    ('african-watering-hole', 'African Watering Hole', 'Mpala Research Centre watering hole live camera', 'Laikipia County', 'Kenya', 0.2830, 36.9000, 'https://explore.org/livecams/african-wildlife/african-watering-hole-animal-camera', 65),
    ('tembe-elephant-park', 'Tembe Elephant Park', 'KwaZulu-Natal reserve live camera', 'Tembe Elephant Park', 'South Africa', -27.0330, 32.4200, 'https://explore.org/livecams/african-wildlife/tembe-elephant-park', 64),
    ('channel-islands-ocean', 'Channel Islands Ocean Cam', 'Channel Islands National Park ocean live camera', 'Channel Islands National Park', 'United States', 34.0150, -119.3670, 'https://explore.org/livecams/oceans/channel-islands-national-park', 64),
    ('blue-spring-state-park', 'Blue Spring State Park', 'Florida spring and river live camera', 'Orange City', 'United States', 28.9474, -81.3396, 'https://explore.org/livecams/manatees/blue-spring-state-park-manatee-cam', 64),
    ('bella-hummingbird-nest', 'Bella Hummingbird Nest', 'Southern California garden live camera', 'La Verne', 'United States', 34.1008, -117.7678, 'https://explore.org/livecams/hummingbirds/bella-hummingbird-nest', 62),
]
AFRICAM_SOURCE_SEEDS = [
    ('africam-live-streams', 'Africam Live Streams', 'Official Africam live safari camera directory', 'Greater Kruger', 'South Africa', -24.0000, 31.5000, 'https://live.africam.com/wildlife/live-african-wildlife-safari-streams', 70),
    ('kwa-maritane-live', 'Kwa Maritane Waterhole', 'Pilanesberg Game Reserve waterhole live camera', 'Pilanesberg National Park', 'South Africa', -25.2600, 27.0800, 'https://www.africam.com/wildlife/stream/kwa-maritane-live', 68),
    ('nkorho-pan', 'Nkorho Pan Waterhole', 'Sabi Sand Game Reserve waterhole live camera', 'Sabi Sand Game Reserve', 'South Africa', -24.8040, 31.4660, 'https://www.africam.com/wildlife/stream/nkorho-pan', 68),
    ('tau-waterhole', 'Tau Waterhole', 'Madikwe Game Reserve waterhole live camera', 'Madikwe Game Reserve', 'South Africa', -24.7560, 26.2430, 'https://www.africam.com/wildlife/stream/tau', 67),
    ('tembe-waterhole', 'Tembe Waterhole', 'Tembe Elephant Park waterhole live camera', 'Tembe Elephant Park', 'South Africa', -27.0330, 32.4200, 'https://www.africam.com/wildlife/stream/tembe', 66),
    ('naledi-cat-eye', 'Naledi Cat-Eye', 'Balule Game Reserve low-angle waterhole live camera', 'Balule Game Reserve', 'South Africa', -24.1800, 31.1350, 'https://www.africam.com/wildlife/stream/naledi-cat-eye', 66),
    ('ol-donyo-lodge', 'ol Donyo Lodge Wildlife Cam', 'Chyulu Hills wildlife waterhole live camera', 'Chyulu Hills', 'Kenya', -2.6330, 37.9000, 'https://www.africam.com/wildlife/stream/ol-donyo', 66),
    ('hyena-pan', 'Hyena Pan', 'Khwai Private Reserve waterhole live camera', 'Khwai Private Reserve', 'Botswana', -19.1500, 23.9000, 'https://www.africam.com/wildlife/stream/hyena-pan', 65),
    ('okaukuejo-waterhole', 'Okaukuejo Waterhole', 'Etosha National Park waterhole live camera', 'Etosha National Park', 'Namibia', -19.1810, 15.9160, 'https://www.africam.com/wildlife/stream/okaukuejo', 65),
    ('finch-hattons', 'Finch Hattons Tsavo', 'Tsavo West National Park safari camp live camera', 'Tsavo West National Park', 'Kenya', -2.9800, 37.8500, 'https://www.africam.com/new-camera-alert-finch-hattons/', 65),
    ('kruger-shalati', 'Kruger Shalati Live Camera', 'Sabie River bridge safari live camera', 'Kruger National Park', 'South Africa', -24.9940, 31.5920, 'https://www.krugershelati.com/live-camera/', 65),
]
WHATSUPCAM_SOURCE_SEEDS = [
    ('moscenicka-draga-center', 'Moscenicka Draga Center', 'Town center live view from the Istrian coast', 'Moscenicka Draga', 'Croatia', 45.2376, 14.2521, 'https://www.whatsupcams.com/en/webcams/croatia/istria/moscenicka-draga/webcam-moscenicka-draga-center/', 66),
    ('piscina-rei-costa-rei', 'Piscina Rei, Costa Rei', 'Sardinia beach live camera from Muravera', 'Muravera', 'Italy', 39.2517, 9.5744, 'https://www.whatsupcams.com/en/webcams/italy/sardinia/muravera/webcam-piscina-rei/', 66),
    ('isole-dello-stagnone', 'Isole dello Stagnone', 'Live lagoon and watersports view near Trapani', 'Trapani', 'Italy', 37.8672, 12.4782, 'https://www.whatsupcams.com/en/webcams/italy/sicily/trapani/webcam-isole-dello-stagnone/', 65),
    ('terza-spiaggia-golfo-aranci', 'Terza Spiaggia Golfo Aranci', 'Sardinia beach live view from Golfo Aranci', 'Golfo Aranci', 'Italy', 40.997, 9.6238, 'https://www.whatsupcams.com/en/webcams/italy/sardinia/golfo-aranci/webcam-terza-spiaggia-golfo-aranci/', 65),
    ('kronplatz-bruneck', 'Kronplatz Peak', 'Dolomites ski and mountain live view', 'Bruneck', 'Italy', 46.738, 11.961, 'https://www.whatsupcams.com/en/webcams/italy/trentino-alto-adige/bruneck/kronplatz-peak-2275m/', 65),
    ('kranjska-gora-ski', 'Kranjska Gora Ski Resort', 'Slovenian alpine resort live camera', 'Kranjska Gora', 'Slovenia', 46.4845, 13.7857, 'https://www.whatsupcams.com/en/webcams/slovenia/upper-carniola/kranjska-gora/webcam-ski-resort-kranjska-gora-slovenia/', 64),
    ('nova-gorica-square', 'Nova Gorica Edvard Kardelj Square', 'City square live camera from Nova Gorica', 'Nova Gorica', 'Slovenia', 45.956, 13.6487, 'https://www.whatsupcams.com/en/webcams/slovenia/goriska/nova-gorica/live-webcam-nova-gorica-edvard-kardelj-square/', 64),
    ('lloret-de-mar-main-beach', 'Lloret de Mar Main Beach', 'Costa Brava beach live camera', 'Lloret de Mar', 'Spain', 41.699, 2.846, 'https://www.whatsupcams.com/en/webcams/spain/catalonia/lloret-de-mar/webcam-lloret-de-mar-main-beach/', 65),
]
BERGFEX_SOURCE_SEEDS = [
    ('soelden', 'Sölden Ski Resort', 'Alpine resort webcams from Ötztal, Tirol', 'Sölden', 'Austria', 46.9695, 11.0104, 'https://www.bergfex.com/soelden/webcams/', 64),
    ('st-anton-am-arlberg', 'St. Anton am Arlberg', 'Arlberg ski resort webcams and mountain views', 'St. Anton am Arlberg', 'Austria', 47.1296, 10.2682, 'https://www.bergfex.com/st-anton-am-arlberg/webcams/', 64),
    ('ischgl', 'Ischgl Silvretta Arena', 'Tyrol ski area webcams and alpine panoramas', 'Ischgl', 'Austria', 47.0125, 10.2918, 'https://www.bergfex.com/ischgl/webcams/', 64),
    ('kitzbuehel', 'Kitzbühel', 'Kitzbühel ski resort webcams and mountain views', 'Kitzbühel', 'Austria', 47.4464, 12.3922, 'https://www.bergfex.com/kitzbuehel/webcams/', 63),
    ('zermatt', 'Zermatt Matterhorn', 'Swiss alpine resort webcams near the Matterhorn', 'Zermatt', 'Switzerland', 46.0207, 7.7491, 'https://www.bergfex.com/zermatt/webcams/', 65),
    ('davos', 'Davos Klosters', 'Graubünden ski resort webcams and mountain views', 'Davos', 'Switzerland', 46.8027, 9.8359, 'https://www.bergfex.com/davos/webcams/', 63),
    ('chamonix', 'Chamonix Mont-Blanc', 'Mont-Blanc valley mountain webcams', 'Chamonix-Mont-Blanc', 'France', 45.9237, 6.8694, 'https://www.bergfex.com/chamonix-mont-blanc/webcams/', 64),
    ('val-gardena', 'Val Gardena', 'Dolomites ski resort webcams around Gröden', 'Selva di Val Gardena', 'Italy', 46.5547, 11.7607, 'https://www.bergfex.com/groeden-val-gardena/webcams/', 63),
]
PTZTV_CAMERA_META = {
    'portevergladeswebcam.com': ('Port Everglades Webcam', 'Port and cruise terminal live camera', 'Fort Lauderdale', 'United States', 26.0933, -80.1169),
    'ftlauderdalewebcam.com': ('Fort Lauderdale Webcam', 'Fort Lauderdale beach and city live camera', 'Fort Lauderdale', 'United States', 26.1224, -80.104),
    'portcanaveralwebcam.com': ('Port Canaveral Webcam', 'Cruise port live camera', 'Port Canaveral', 'United States', 28.4107, -80.6185),
    'portmiamiwebcam.com': ('Port Miami Webcam', 'Cruise port and Biscayne Bay live camera', 'Miami', 'United States', 25.7781, -80.1794),
    'portnassauwebcam.com': ('Port Nassau Webcam', 'Cruise port live camera from Nassau', 'Nassau', 'Bahamas', 25.078, -77.343),
    'portbiminiwebcam.com': ('Port Bimini Webcam', 'Bimini cruise port live camera', 'Bimini', 'Bahamas', 25.7274, -79.2972),
    'portbermudawebcam.com': ('Port Bermuda Webcam', 'Royal Naval Dockyard cruise port live camera', 'Royal Naval Dockyard', 'Bermuda', 32.324, -64.833),
    'portstthomaswebcam.com': ('Port St Thomas Webcam', 'Charlotte Amalie harbor live camera', 'Charlotte Amalie', 'U.S. Virgin Islands', 18.3358, -64.926),
    'portstmaartenwebcam.com': ('Port St Maarten Webcam', 'Philipsburg cruise port live camera', 'Philipsburg', 'Sint Maarten', 18.041, -63.047),
    'portnywebcam.com': ('Port New York Webcam', 'New York Harbor and cruise traffic live camera', 'New York', 'United States', 40.7003, -74.012),
    'porttampawebcam.com': ('Port Tampa Webcam', 'Tampa cruise port live camera', 'Tampa', 'United States', 27.942, -82.445),
    'palmbeachinletwebcam.com': ('Palm Beach Inlet Webcam', 'Inlet and beach live camera', 'Palm Beach Shores', 'United States', 26.777, -80.034),
    'miamiairportcam.com': ('Miami Airport Cam', 'Miami International Airport live camera', 'Miami', 'United States', 25.7959, -80.287),
    'mahobeachcam.com': ('Maho Beach Cam', 'Maho Beach aircraft approach live camera', 'Simpson Bay', 'Sint Maarten', 18.0392, -63.1202),
    'paradiseislandcam.com': ('Paradise Island Cam', 'Paradise Island live camera', 'Nassau', 'Bahamas', 25.0844, -77.3183),
    'keywestharborwebcam.com': ('Key West Harbor Webcam', 'Key West harbor live camera', 'Key West', 'United States', 24.558, -81.807),
    'nyharborwebcam.com': ('New York Harbor Webcam', 'New York Harbor live camera', 'New York', 'United States', 40.6892, -74.0445),
    'juneauharborwebcam.com': ('Juneau Harbor Webcam', 'Alaska cruise harbor live camera', 'Juneau', 'United States', 58.298, -134.416),
    'morganhillwebcam.com': ('Morgan Hill Webcam', 'California town live camera', 'Morgan Hill', 'United States', 37.1305, -121.6544),
    'pompanoBeachcam.com'.lower(): ('Pompano Beach Cam', 'Pompano Beach live camera', 'Pompano Beach', 'United States', 26.2379, -80.1248),
}
PUBLIC_TRAFFIC_SEEDS = [
    ('plymouth-cattedown-roundabout', 'Plymouth Cattedown Roundabout', 'Official data.gov.uk CCTV location record', 'Plymouth', 'United Kingdom', 50.370026, -4.125025, 'https://www.data.gov.uk/dataset/603331e3-5505-44c1-adf4-8278c02535d6/cctv-locations-in-plymouth/datafile/4984b27f-ae96-4c7b-9102-17434408a1b3/preview', 60),
    ('plymouth-charles-church', 'Plymouth Charles Church / Ebrington Street', 'Official data.gov.uk CCTV location record', 'Plymouth', 'United Kingdom', 50.372335, -4.135915, 'https://www.data.gov.uk/dataset/603331e3-5505-44c1-adf4-8278c02535d6/cctv-locations-in-plymouth/datafile/4984b27f-ae96-4c7b-9102-17434408a1b3/preview', 60),
    ('plymouth-viaduct-north', 'Plymouth Viaduct North', 'Official data.gov.uk CCTV location record', 'Plymouth', 'United Kingdom', 50.371514, -4.136269, 'https://www.data.gov.uk/dataset/603331e3-5505-44c1-adf4-8278c02535d6/cctv-locations-in-plymouth/datafile/4984b27f-ae96-4c7b-9102-17434408a1b3/preview', 60),
    ('durham-high-bondgate', 'Durham High Bondgate Traffic Camera', 'Official Durham traffic web camera location via data.gov.uk', 'Bishop Auckland', 'United Kingdom', 54.664832, -1.676704, 'https://www.data.gov.uk/dataset/2c4818e4-3da2-4bdb-a8d9-894d700f889a/traffic-web-cameras/datafile/9215c421-6b22-469f-9669-01dc4657fa10/preview', 60),
    ('durham-newton-cap', 'Durham Newton Cap Traffic Camera', 'Official Durham traffic web camera location via data.gov.uk', 'Bishop Auckland', 'United Kingdom', 54.664296, -1.678284, 'https://www.data.gov.uk/dataset/2c4818e4-3da2-4bdb-a8d9-894d700f889a/traffic-web-cameras/datafile/9215c421-6b22-469f-9669-01dc4657fa10/preview', 60),
    ('virginia-hrbt', 'Virginia 511 Hampton Roads Bridge-Tunnel', 'Official Virginia 511 traffic camera map source', 'Norfolk', 'United States', 36.966, -76.301, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i95-richmond', 'Virginia 511 I-95 Richmond', 'Official Virginia 511 traffic camera map source', 'Richmond', 'United States', 37.5407, -77.436, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i66-arlington', 'Virginia 511 I-66 Arlington', 'Official Virginia 511 traffic camera map source', 'Arlington', 'United States', 38.8828, -77.103, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i64-richmond', 'Virginia 511 I-64 Richmond', 'Official Virginia 511 traffic camera map source', 'Richmond', 'United States', 37.5623, -77.4572, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i81-roanoke', 'Virginia 511 I-81 Roanoke', 'Official Virginia 511 traffic camera map source', 'Roanoke', 'United States', 37.2709, -79.9414, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i495-tysons', 'Virginia 511 I-495 Tysons', 'Official Virginia 511 traffic camera map source', 'Tysons', 'United States', 38.9187, -77.2311, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-i264-virginia-beach', 'Virginia 511 I-264 Virginia Beach', 'Official Virginia 511 traffic camera map source', 'Virginia Beach', 'United States', 36.8440, -76.1300, 'https://511.vdot.virginia.gov/', 59),
    ('virginia-route-29-charlottesville', 'Virginia 511 Route 29 Charlottesville', 'Official Virginia 511 traffic camera map source', 'Charlottesville', 'United States', 38.0600, -78.4900, 'https://511.vdot.virginia.gov/', 58),
    ('durham-a167-durham-road', 'Durham A167 Durham Road Traffic Camera', 'Official Durham traffic web camera location via data.gov.uk', 'Bishop Auckland', 'United Kingdom', 54.6559, -1.6770, 'https://www.data.gov.uk/dataset/2c4818e4-3da2-4bdb-a8d9-894d700f889a/traffic-web-cameras', 60),
    ('plymouth-marsh-mills', 'Plymouth Marsh Mills Roundabout', 'Official data.gov.uk CCTV location record', 'Plymouth', 'United Kingdom', 50.3943, -4.0893, 'https://www.data.gov.uk/dataset/603331e3-5505-44c1-adf4-8278c02535d6/cctv-locations-in-plymouth', 60),
    ('plymouth-royal-parade', 'Plymouth Royal Parade CCTV', 'Official data.gov.uk CCTV location record', 'Plymouth', 'United Kingdom', 50.3710, -4.1427, 'https://www.data.gov.uk/dataset/603331e3-5505-44c1-adf4-8278c02535d6/cctv-locations-in-plymouth', 60),
]
IDOKEP_LOCATION_OVERRIDES = {
    'aszod': ('Aszod', 'Hungary', 47.6514, 19.4785),
    'budajeno': ('Budajeno', 'Hungary', 47.5567, 18.8059),
    'budakalasz': ('Budakalasz', 'Hungary', 47.6167, 19.05),
    'budakeszi': ('Budakeszi', 'Hungary', 47.513, 18.927),
    'budaors': ('Budaors', 'Hungary', 47.4618, 18.9585),
    'cegled': ('Cegled', 'Hungary', 47.1727, 19.7995),
    'dunakeszi': ('Dunakeszi', 'Hungary', 47.6364, 19.1386),
    'erd': ('Erd', 'Hungary', 47.3919, 18.9045),
    'godollo': ('Godollo', 'Hungary', 47.5966, 19.3552),
    'vac': ('Vac', 'Hungary', 47.7759, 19.1361),
    'budapest': ('Budapest', 'Hungary', 47.4979, 19.0402),
    'szeged': ('Szeged', 'Hungary', 46.253, 20.1414),
    'pecs': ('Pecs', 'Hungary', 46.0727, 18.2323),
    'debrecen': ('Debrecen', 'Hungary', 47.5316, 21.6273),
    'gyor': ('Gyor', 'Hungary', 47.6875, 17.6504),
    'sopron': ('Sopron', 'Hungary', 47.6817, 16.5845),
    'esztergom': ('Esztergom', 'Hungary', 47.7928, 18.7415),
    'siofok': ('Siofok', 'Hungary', 46.9091, 18.0746),
    'balatonfured': ('Balatonfured', 'Hungary', 46.9618, 17.8719),
    'keszthely': ('Keszthely', 'Hungary', 46.7655, 17.2432),
    'eger': ('Eger', 'Hungary', 47.9025, 20.3772),
    'miskolc': ('Miskolc', 'Hungary', 48.1035, 20.7784),
    'nyiregyhaza': ('Nyiregyhaza', 'Hungary', 47.9554, 21.7167),
    'szekesfehervar': ('Szekesfehervar', 'Hungary', 47.186, 18.4221),
    'veszprem': ('Veszprem', 'Hungary', 47.1028, 17.9093),
}


HTTP_CACHE = None
HTTP_CACHE_DIRTY = False
HTTP_CACHE_STATS = {
    'hits': 0,
    'misses': 0,
    'staleFallbacks': 0,
    'errors': 0,
    'writes': 0,
}


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def parse_iso_stamp(value):
    try:
        return dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except Exception:
        return None


def load_http_cache():
    global HTTP_CACHE
    if HTTP_CACHE is not None:
        return HTTP_CACHE
    if not HTTP_CACHE_PATH.exists():
        HTTP_CACHE = {}
        return HTTP_CACHE
    try:
        payload = json.loads(HTTP_CACHE_PATH.read_text())
        HTTP_CACHE = payload if isinstance(payload, dict) else {}
    except Exception:
        HTTP_CACHE = {}
    return HTTP_CACHE


def save_http_cache():
    global HTTP_CACHE_DIRTY
    if not HTTP_CACHE_DIRTY or HTTP_CACHE is None:
        return
    HTTP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HTTP_CACHE_PATH.write_text(json.dumps(HTTP_CACHE, ensure_ascii=False, indent=2) + '\n')
    HTTP_CACHE_DIRTY = False


class CollectorTimeoutError(TimeoutError):
    pass


def run_with_collector_timeout(collector, timeout_seconds=WORLD_TOUR_COLLECTOR_TIMEOUT_SECONDS):
    if timeout_seconds <= 0 or not hasattr(signal, 'SIGALRM'):
        return collector()

    previous_handler = signal.getsignal(signal.SIGALRM)

    def timeout_handler(signum, frame):
        raise CollectorTimeoutError(f'collector exceeded {timeout_seconds}s')

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        return collector()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def cache_age_hours(entry):
    fetched_at = parse_iso_stamp(entry.get('fetchedAt') if isinstance(entry, dict) else None)
    if not fetched_at:
        return None
    return max(0, (utc_now() - fetched_at).total_seconds() / 3600)


def http_cache_key(url, headers=None):
    accept = (headers or HEADERS).get('Accept', '')
    return f'{url}||{accept}'


def effective_timeout(timeout):
    try:
        requested = float(timeout)
    except (TypeError, ValueError):
        requested = 18
    if WORLD_TOUR_HTTP_TIMEOUT_CAP <= 0:
        return requested
    return max(1, min(requested, WORLD_TOUR_HTTP_TIMEOUT_CAP))


def urlopen_with_fallback(req, timeout=18):
    timeout = effective_timeout(timeout)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except URLError as error:
        if 'CERTIFICATE_VERIFY_FAILED' not in str(error):
            raise
        return urllib.request.urlopen(req, timeout=timeout, context=UNVERIFIED_SSL_CONTEXT)


def fetch_text(url, timeout=18, headers=None, cache=True):
    global HTTP_CACHE_DIRTY
    request_headers = headers or HEADERS
    key = http_cache_key(url, request_headers)
    if cache and WORLD_TOUR_HTTP_CACHE_TTL_HOURS > 0:
        entry = load_http_cache().get(key)
        age = cache_age_hours(entry)
        if age is not None and age <= WORLD_TOUR_HTTP_CACHE_TTL_HOURS and 'text' in entry:
            HTTP_CACHE_STATS['hits'] += 1
            return entry['text']

    req = urllib.request.Request(url, headers=request_headers)
    try:
        text = urlopen_with_fallback(req, timeout=timeout).read().decode('utf-8', 'replace')
        if cache:
            load_http_cache()[key] = {
                'fetchedAt': utc_now().isoformat(),
                'text': text,
            }
            HTTP_CACHE_DIRTY = True
            HTTP_CACHE_STATS['writes'] += 1
        HTTP_CACHE_STATS['misses'] += 1
        return text
    except Exception:
        HTTP_CACHE_STATS['errors'] += 1
        if cache and WORLD_TOUR_STALE_CACHE_HOURS > 0:
            entry = load_http_cache().get(key)
            age = cache_age_hours(entry)
            if age is not None and age <= WORLD_TOUR_STALE_CACHE_HOURS and 'text' in entry:
                HTTP_CACHE_STATS['staleFallbacks'] += 1
                return entry['text']
        raise


def fetch_bytes(url, timeout=18, headers=None):
    req = urllib.request.Request(url, headers=headers or HEADERS)
    return urlopen_with_fallback(req, timeout=timeout).read()


def fetch_json(url, timeout=12):
    return json.loads(fetch_text(url, timeout=timeout))


def fetch_json_with_headers(url, timeout=12, headers=None):
    return json.loads(fetch_text(url, timeout=timeout, headers=headers or HEADERS))


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
    text = str(text or '')
    value = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return value or str(abs(hash(text)))


def normalize_country_name(country):
    country = html.unescape(str(country or '')).strip()
    return COUNTRY_NORMALIZATION.get(country, country)


def country_from_slug(slug):
    slug = re.sub(r'[^a-z0-9-]+', '-', str(slug or '').lower()).strip('-')
    country = SOURCE_COUNTRY_BY_SLUG.get(slug) or slug.replace('-', ' ').title()
    return normalize_country_name(country)


def region_for_country(country):
    return REGION_BY_COUNTRY.get(normalize_country_name(country), 'Other')


def title_from_slug(slug):
    return re.sub(r'\s+', ' ', str(slug or '').replace('-', ' ').replace('_', ' ')).strip().title()


def ascii_key(text):
    value = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^a-z0-9]+', '', value.lower())


def latin_slug(text):
    value = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return value or slugify(text)


def extract_meta_content(text, key):
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)',
        rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return html.unescape(match.group(1)).strip()
    return ''


def text_from_tag(text, tag):
    match = re.search(rf'<{tag}[^>]*>(.*?)</{tag}>', text, re.I | re.S)
    if not match:
        return ''
    value = re.sub(r'<[^>]+>', ' ', match.group(1))
    return re.sub(r'\s+', ' ', html.unescape(value)).strip()


def strip_html_text(value):
    value = re.sub(r'<[^>]+>', ' ', html.unescape(str(value or '')))
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def first_localized_text(value):
    if isinstance(value, dict):
        for key in ('en', 'de', 'it', 'fr', 'es', 'title', 'name'):
            nested = value.get(key)
            if nested:
                return first_localized_text(nested)
        for nested in value.values():
            if nested:
                return first_localized_text(nested)
        return ''
    if isinstance(value, list):
        for nested in value:
            if nested:
                return first_localized_text(nested)
        return ''
    return strip_html_text(value)


def country_from_coordinates(lat, lng, fallback=''):
    if not (is_finite_number(lat) and is_finite_number(lng)):
        return normalize_country_name(fallback)
    lat = float(lat)
    lng = float(lng)
    boxes = [
        ('Slovakia', 47.6, 49.8, 16.7, 22.8),
        ('Czech Republic', 48.4, 51.2, 12.0, 18.9),
        ('Austria', 46.2, 49.2, 9.4, 17.3),
        ('Switzerland', 45.7, 47.9, 5.8, 10.7),
        ('Slovenia', 45.4, 46.9, 13.3, 16.7),
        ('Croatia', 42.1, 46.7, 13.0, 19.6),
        ('Poland', 49.0, 55.1, 14.0, 24.5),
        ('Germany', 47.0, 55.5, 5.0, 15.6),
        ('Italy', 36.0, 47.3, 6.0, 18.9),
        ('United Kingdom', 49.0, 61.0, -8.5, 2.2),
        ('France', 41.0, 51.2, -5.5, 10.0),
        ('Spain', 27.0, 44.5, -18.5, 5.0),
        ('Portugal', 36.5, 42.2, -9.8, -6.0),
        ('Netherlands', 50.7, 53.8, 3.2, 7.3),
        ('Belgium', 49.4, 51.6, 2.4, 6.5),
        ('Denmark', 54.5, 57.9, 8.0, 15.5),
        ('Finland', 59.0, 70.4, 19.0, 32.0),
        ('Sweden', 55.0, 69.5, 10.0, 24.5),
        ('Norway', 57.0, 72.0, 4.0, 32.0),
        ('Greece', 34.0, 41.9, 19.0, 29.5),
        ('Bulgaria', 41.0, 44.5, 22.0, 29.0),
        ('Romania', 43.5, 48.5, 20.0, 30.0),
        ('Ireland', 51.0, 56.0, -10.8, -5.2),
        ('Greenland', 59.0, 84.0, -74.0, -11.0),
        ('Latvia', 55.5, 58.2, 20.5, 28.5),
        ('Lithuania', 53.8, 56.6, 20.8, 26.9),
        ('Estonia', 57.4, 59.8, 21.5, 28.4),
        ('United Arab Emirates', 22.4, 26.5, 51.0, 56.6),
        ('Israel', 29.0, 34.0, 34.0, 36.0),
        ('Saudi Arabia', 16.0, 33.0, 34.0, 56.0),
        ('Iran', 24.0, 40.0, 44.0, 64.0),
        ('Turkey', 35.5, 42.5, 25.0, 45.0),
        ('Curaçao', 11.7, 12.5, -69.3, -68.5),
        ('United States', 24.0, 50.0, -125.0, -66.0),
        ('Canada', 41.0, 84.0, -141.0, -52.0),
        ('Mexico', 14.0, 33.0, -119.0, -86.0),
        ('Japan', 24.0, 46.5, 122.0, 146.5),
        ('South Korea', 33.0, 39.0, 124.0, 132.0),
        ('Taiwan', 21.5, 26.5, 119.0, 123.0),
        ('Thailand', 5.0, 21.0, 97.0, 106.0),
        ('Australia', -44.0, -10.0, 112.0, 154.0),
        ('New Zealand', -48.0, -33.0, 165.0, 180.0),
        ('Brazil', -34.0, 6.0, -74.0, -34.0),
    ]
    for country, min_lat, max_lat, min_lng, max_lng in boxes:
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return country
    return normalize_country_name(fallback)


def country_hint_from_title(title):
    value = str(title or '').lower()
    hints = [
        (r'\b(germany|deutschland|deutsch|berlin|munich|hamburg|selb)\b', 'Germany'),
        (r'\b(czech|czechia|praha|prague|brno|ostrava|karlovy vary)\b', 'Czech Republic'),
        (r'\b(ireland|dublin|galway|cork)\b', 'Ireland'),
        (r'\b(united kingdom|england|london|scotland|wales|cornwall|boscastle)\b', 'United Kingdom'),
        (r'\b(austria|wien|vienna|innsbruck|salzburg|gasteinertal)\b', 'Austria'),
        (r'\b(switzerland|swiss|zermatt|davos|basel|zurich|zürich)\b', 'Switzerland'),
        (r'\b(sweden|stockholm|gothenburg|malmo|malmö)\b', 'Sweden'),
        (r'\b(finland|finnish|hankasalmi|rovaniemi|lapland)\b', 'Finland'),
        (r'\b(norway|norwegian|skibotn|tromso|tromsø|svalbard|alta)\b', 'Norway'),
        (r'\b(iceland|reykjavik|akureyri)\b', 'Iceland'),
        (r'\b(spain|lanzarote|canary|granada|formigal)\b', 'Spain'),
        (r'\b(italy|venice|venezia|bozen|livigno)\b', 'Italy'),
        (r'\b(poland|zakopane|gniezno|krakow|kraków|łukow|łuków)\b', 'Poland'),
        (r'\b(slovakia|tatras|bratislava|poprad|strbske|tatranska)\b', 'Slovakia'),
        (r'\b(united states|new york|manhattan|brooklyn|california|alaska)\b', 'United States'),
        (r'\b(canada|yellowknife|whitehorse|churchill|alberta|ontario|british columbia)\b', 'Canada'),
        (r'\b(dubai|united arab emirates|uae)\b', 'United Arab Emirates'),
        (r'\b(saudi arabia|medina|mecca|riyadh|jeddah)\b', 'Saudi Arabia'),
        (r'\b(curacao|curaçao|klein curaçao|willemstad)\b', 'Curaçao'),
        (r'\b(greenland|kulusuk|nuuk)\b', 'Greenland'),
        (r'\b(israel|eilat|tel aviv|jerusalem)\b', 'Israel'),
        (r'\b(iran|tehran)\b', 'Iran'),
        (r'\b(croatia|hrvatska|zagreb|split|dubrovnik|zlatni rat|brac|brač)\b', 'Croatia'),
    ]
    for pattern, country in hints:
        if re.search(pattern, value, re.I):
            return country
    return ''


def extract_sitemap_locs(url, timeout=18):
    try:
        text = fetch_text(url, timeout=timeout)
    except Exception:
        return []
    return [html.unescape(loc.strip()) for loc in re.findall(r'<loc>([^<]+)</loc>', text)]


def iter_nested_json(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from iter_nested_json(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from iter_nested_json(nested)


def extract_json_ld_objects(text):
    objects = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.I | re.S):
        raw = html.unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        objects.extend(iter_nested_json(payload))
    return objects


def json_type_matches(obj, value):
    obj_type = obj.get('@type') if isinstance(obj, dict) else None
    if isinstance(obj_type, list):
        return value in obj_type
    return obj_type == value


def extract_maps_coords(text):
    decoded = html.unescape(text)
    patterns = [
        r'maps\.google\.com/maps\?ll=([-0-9.]+),([-0-9.]+)',
        r'maps\.google\.com/maps\?q=([-0-9.]+)%2C([-0-9.]+)',
        r'maps\.google\.com/maps\?q=([-0-9.]+),([-0-9.]+)',
        r'"latitude"\s*:\s*([-0-9.]+)\s*,\s*"longitude"\s*:\s*([-0-9.]+)',
        r'"longitude"\s*:\s*([-0-9.]+)\s*,\s*"latitude"\s*:\s*([-0-9.]+)',
    ]
    for index, pattern in enumerate(patterns):
        match = re.search(pattern, decoded, re.I)
        if not match:
            continue
        if index == 3:
            return match.group(2), match.group(1)
        return match.group(1), match.group(2)
    return None


def clean_source_location_query(value):
    value = clean_youtube_search_title(value)
    value = re.sub(r'\b(Live|Cam|Camera|Webcam|Stream|Streaming|HD|4K|Beach Cam|Live Cam|Live Webcam)\b', ' ', value, flags=re.I)
    value = re.sub(r'\b(HDOnTap|Live Beaches|Explore.org|WhatsUpCams|Bergfex|Feratel|Camscape)\b', ' ', value, flags=re.I)
    value = re.sub(r'\s+', ' ', value).strip(' -–—:|,')
    return value


def source_location_candidates(title, subtitle='', url=''):
    combined = strip_html_text(f'{title}. {subtitle}')
    candidates = []
    for match in re.finditer(
        r'\bat\s+([A-Z][A-Za-z .\'-]+(?:Research Centre|State Park|National Park|Zoological Park|Wildlife Refuge|Conservancy|Reserve|Sanctuary|Farm|Island|Cove))(?:\s+in\s+(?:the\s+)?(?:highlands of\s+|central\s+|northern\s+|southern\s+|eastern\s+|western\s+)?([A-Z][A-Za-z .\'-]+))?',
        combined,
    ):
        place = match.group(1).strip()
        country_hint = re.split(r"'s|\.|,", (match.group(2) or '').strip())[0].strip()
        if country_hint:
            candidates.append(f'{place}, {country_hint}')
        candidates.append(place)
    for match in re.finditer(
        r"\bin\s+(?:the\s+)?(?:highlands of\s+|central\s+|northern\s+|southern\s+|eastern\s+|western\s+)?([A-Z][A-Za-z .'-]+)'s\s+([A-Z][A-Za-z .'-]+ County)",
        combined,
    ):
        candidates.append(f'{match.group(2)}, {match.group(1)}')
    for pattern in [
        r'\b(?:near|in|at|from|overlooking|located in|located at)\s+([A-Z][A-Za-z .\'-]+,\s*[A-Z][A-Za-z .\'-]+)',
        r'\b([A-Z][A-Za-z .\'-]+,\s*(?:California|Florida|Hawaii|Montana|Alaska|Oregon|Washington|Colorado|Utah|Maine|Massachusetts|New York|North Carolina|South Carolina|Texas|Arizona|Nevada|Wyoming|Canada|Italy|Spain|France|Croatia|Austria|Germany|Switzerland|Norway|Australia|New Zealand))\b',
    ]:
        for match in re.finditer(pattern, combined):
            candidates.append(match.group(1))

    for value in [title, subtitle]:
        for part in re.split(r'\s[-–—:|]\s|/|\(|\)|\[|\]', strip_html_text(value)):
            cleaned = clean_source_location_query(part)
            if 4 <= len(cleaned) <= 80 and not YOUTUBE_SEARCH_NEGATIVE.search(cleaned):
                candidates.append(cleaned)

    path_slug = urlparse(url).path.strip('/').split('/')[-1] if url else ''
    if path_slug:
        cleaned = clean_source_location_query(title_from_slug(path_slug))
        if 4 <= len(cleaned) <= 80:
            candidates.append(cleaned)
    return list(dict.fromkeys(candidates))[:5]


def clean_subtitle(value, fallback='Live webcam'):
    value = re.sub(r'<[^>]+>', ' ', html.unescape(str(value or '')))
    value = re.sub(r'\s+', ' ', value).strip()
    return (value or fallback)[:120].rstrip(' ,')


def make_source_item(source_type, sid, title, subtitle, city, country, lat, lng, source_url, priority=62, thumbnail_url='', tags=None, channel=None):
    country = normalize_country_name(country)
    region = region_for_country(country)
    if region == 'Other' or not is_finite_number(lat) or not is_finite_number(lng):
        return None
    source_label = channel or source_type.title()
    return {
        'id': f'{source_type}-{slugify(sid)}',
        'title': clean_title(title),
        'subtitle': clean_subtitle(subtitle, f'{city}, {country} live webcam'),
        'city': city,
        'country': country,
        'region': region,
        'lat': round(float(lat), 6),
        'lng': round(float(lng), 6),
        'channel': source_label,
        'sourceUrl': source_url,
        'thumbnailUrl': thumbnail_url,
        'tags': tags or ['tourism', source_type, 'source-site'],
        'priority': priority,
        'status': 'source_only',
        'sourceType': source_type,
        'playbackStatus': 'source-only',
        'lastCheckedAt': dt.date.today().isoformat(),
        'sourceOnly': True,
    }


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


def source_location_hint(text):
    lowered = str(text or '').lower()
    for aliases, title_hint, city, country, region, lat, lng in SOURCE_LOCATION_HINTS:
        if any(alias in lowered for alias in aliases):
            return {
                'title': title_hint,
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
    country = normalize_country_name(address.get('country'))
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
        'region': region_for_country(country),
        'lat': round(float(result['lat']), 6),
        'lng': round(float(result['lon']), 6),
    }
    if item['region'] == 'Other':
        cache[key] = None
        return None
    cache[key] = item
    return item


def reverse_geocode_location(lat, lng, cache):
    if not is_finite_number(lat) or not is_finite_number(lng):
        return None
    key = f'reverse:{float(lat):.5f},{float(lng):.5f}'
    if key in cache:
        return cache[key]
    url = (
        'https://nominatim.openstreetmap.org/reverse?format=jsonv2&addressdetails=1&lat='
        + quote(str(lat)) + '&lon=' + quote(str(lng))
    )
    try:
        result = fetch_json_with_headers(url, timeout=12, headers=NOMINATIM_HEADERS)
        time.sleep(1.05)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        cache[key] = None
        return None
    address = result.get('address') or {}
    country = normalize_country_name(address.get('country'))
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
        'region': region_for_country(country),
        'lat': round(float(lat), 6),
        'lng': round(float(lng), 6),
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


def infer_source_location(title, subtitle, url, cache):
    hint = source_location_hint(f'{title} {subtitle} {url}')
    if hint:
        return hint
    hint = youtube_location_hint(f'{title} {subtitle} {url}')
    if hint:
        return hint
    for candidate in source_location_candidates(title, subtitle, url):
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


def is_in_app_video_item(item):
    return bool(item.get('videoId') or item.get('embedUrl') or item.get('playUrl'))


def is_snapshot_only_item(item):
    return bool(item.get('snapshotUrl')) and not is_in_app_video_item(item)


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
        if is_snapshot_only_item(item):
            continue
        if item.get('videoId') or item.get('embedUrl') or item.get('sourceUrl'):
            item.setdefault('sourceType', 'youtube' if item.get('videoId') else 'external')
            items.append(item)
    save_geocode_cache(cache)
    return items


def collect_cctv_world():
    sitemap = fetch_text('https://www.cctv-world.kr/sitemap.xml')
    urls = re.findall(r'<loc>(https://www\.cctv-world\.kr/cctv/[^<]+)</loc>', sitemap)
    supported_slugs = set(CCTV_WORLD_META) | set(CCTV_WORLD_ORIGIN_META)
    urls = [url for url in urls if url.rstrip('/').split('/')[-1] in supported_slugs]

    def extract_origin_url(text):
        patterns = [
            r'"originUrl"\s*:\s*"([^"]+)"',
            r'originUrl\\":\\"([^\\"]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return html.unescape(match.group(1)).replace('\\/', '/')
        return ''

    def resolve_origin_stream(origin_url):
        if not origin_url:
            return ''
        if '.m3u8' in origin_url:
            return origin_url
        if 'knps.or.kr' in origin_url:
            try:
                payload = fetch_json(
                    'https://www.cctv-world.kr/api/knps-m3u8?pageUrl=' + quote(origin_url, safe=''),
                    timeout=12,
                )
                stream_url = str(payload.get('m3u8Url') or '')
                if '.m3u8' in stream_url:
                    return stream_url
            except Exception:
                return ''
        return ''

    def parse(url):
        try:
            text = fetch_text(url, timeout=12)
            slug = url.rstrip('/').split('/')[-1]
            vid = extract_youtube_id(text)
            if vid and slug in CCTV_WORLD_META:
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
            if slug not in CCTV_WORLD_ORIGIN_META:
                return None
            origin_url = extract_origin_url(text)
            stream_url = resolve_origin_stream(origin_url)
            if not stream_url:
                return None
            title, subtitle, city, country, lat, lng, priority, category = CCTV_WORLD_ORIGIN_META[slug]
            return {
                'id': f'cctvworld-{slug}',
                'title': title,
                'subtitle': subtitle,
                'city': city,
                'country': country,
                'region': REGION_BY_COUNTRY[country],
                'lat': lat,
                'lng': lng,
                'embedUrl': stream_url,
                'channel': 'CCTV World',
                'sourceUrl': url,
                'tags': ['tourism', category, 'cctvworld', 'hls'],
                'priority': priority,
                'status': 'is_live',
                'sourceType': 'cctvworld',
                'streamType': 'hls',
                'originUrl': origin_url,
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
    if limit <= 0:
        return []
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


def collect_earthcam(limit=WORLD_TOUR_EARTHCAM_LIMIT):
    if limit <= 0:
        return []

    api_headers = {**HEADERS, 'Referer': 'https://www.earthcam.com/network/'}
    raw_items = []

    def add_api_items(url, path):
        try:
            payload = fetch_json_with_headers(url, timeout=18, headers=api_headers)
        except Exception:
            return
        data = payload.get('data') or {}
        cursor = data
        for key in path:
            cursor = cursor.get(key) if isinstance(cursor, dict) else None
            if cursor is None:
                return
        if isinstance(cursor, list):
            raw_items.extend(cursor)

    add_api_items(
        'https://www.earthcam.com/api/ectv/player/playlist.php?r=playlist&a=fetch',
        ['playlist_featured', 'playlist_items'],
    )
    for state in EARTHCAM_STATE_TARGETS:
        url = 'https://www.earthcam.com/api/dotcom/network_search.php?r=ecn&a=fetch&country=United%20States&state=' + quote(state)
        add_api_items(url, ['cam_items'])
    for country in EARTHCAM_COUNTRY_TARGETS:
        url = 'https://www.earthcam.com/api/dotcom/network_search.php?r=ecn&a=fetch&country=' + quote(country) + '&state='
        add_api_items(url, ['cam_items'])

    deduped = {}
    for raw in raw_items:
        if raw.get('cam_state') not in {1, '1', None}:
            continue
        if not raw.get('url') or not raw.get('title'):
            continue
        deduped[raw.get('id') or raw.get('item_id') or raw['url']] = raw

    cache = load_geocode_cache()

    def page_coords(url):
        try:
            text = fetch_text(url, timeout=12)
        except Exception:
            return None
        lat_match = re.search(r'"map_lat"\s*:\s*"([-0-9.]+)"', text)
        lng_match = re.search(r'"map_long"\s*:\s*"([-0-9.]+)"', text)
        if lat_match and lng_match:
            return lat_match.group(1), lng_match.group(1)
        return None

    def parse(raw):
        country = normalize_country_name(raw.get('country'))
        city = html.unescape(str(raw.get('city') or country or '')).strip() or country
        lat = raw.get('latitude')
        lng = raw.get('longitude')
        if not (is_finite_number(lat) and is_finite_number(lng)):
            location = geocode_location(f'{city}, {country}', cache)
            if location:
                lat, lng = location['lat'], location['lng']
                city = location['city'] or city
                country = location['country'] or country
            else:
                coords = page_coords(raw['url'])
                if coords:
                    lat, lng = coords
        if not (is_finite_number(lat) and is_finite_number(lng)):
                return None
        title = raw.get('title') or city
        if HARD_NEGATIVE_TITLE.search(title):
            return None
        if NEGATIVE_TITLE.search(title) and not POSITIVE_TITLE.search(f'{title} {raw.get("description", "")}'):
            return None
        return make_source_item(
            'earthcam',
            raw.get('id') or raw.get('item_id') or raw['url'],
            title,
            raw.get('description') or f'{city}, {country} EarthCam live camera',
            city,
            country,
            lat,
            lng,
            raw['url'],
            priority=74,
            thumbnail_url=raw.get('thumbnail_large') or raw.get('thumbnail') or '',
            tags=['tourism', 'earthcam', 'source-site'],
            channel='EarthCam',
        )

    raw_values = list(deduped.values())
    raw_values.sort(key=lambda raw: 0 if is_finite_number(raw.get('latitude')) and is_finite_number(raw.get('longitude')) else 1)
    items = []
    for raw in raw_values:
        item = parse(raw)
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    items.sort(key=lambda item: (-item.get('priority', 0), item['title']))
    return items


def collect_worldcam(limit=WORLD_TOUR_WORLDCAM_LIMIT):
    if limit <= 0:
        return []
    detail_links = []
    seen = set()
    for list_url in WORLDCAM_LIST_URLS:
        try:
            text = fetch_text(list_url, timeout=18)
        except Exception:
            continue
        for match in re.finditer(r'href=["\']([^"\']*/webcams/[^"\']+/\d+-[^"\']+)["\']', text, re.I):
            href = html.unescape(match.group(1))
            link = urljoin('https://worldcam.eu', href)
            if link not in seen:
                seen.add(link)
                detail_links.append(link)

    def parse(url):
        try:
            text = fetch_text(url, timeout=14)
        except Exception:
            return None
        title = extract_meta_content(text, 'og:title') or text_from_tag(text, 'h1')
        lat = extract_meta_content(text, 'og:latitude')
        lng = extract_meta_content(text, 'og:longitude')
        if not title or not lat or not lng:
            return None
        parts = [part.strip() for part in re.split(r'\s+-\s+', title) if part.strip()]
        country = normalize_country_name(parts[-1] if len(parts) > 1 else urlparse(url).path.strip('/').split('/')[2])
        city = parts[0] if parts else country
        if HARD_NEGATIVE_TITLE.search(title):
            return None
        if NEGATIVE_TITLE.search(title) and not POSITIVE_TITLE.search(title):
            return None
        return make_source_item(
            'worldcam',
            urlparse(url).path.strip('/').split('/')[-1],
            title,
            extract_meta_content(text, 'description') or f'{city}, {country} WorldCam live camera',
            city,
            country,
            lat,
            lng,
            url,
            priority=65,
            thumbnail_url=extract_meta_content(text, 'og:image'),
            tags=['tourism', 'worldcam', 'source-site'],
            channel='WorldCam',
        )

    items = []
    country_counts = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for item in executor.map(parse, detail_links[:700]):
            if not item:
                continue
            if country_counts.get(item['country'], 0) >= 18:
                continue
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
            if len(items) >= limit:
                break
    return items


def collect_baltic(limit=WORLD_TOUR_BALTIC_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://balticlivecam.com/cameras/', timeout=30)
    except Exception:
        return []

    cards = []
    for match in re.finditer(
        r'background-image:\s*url\(([^)]+)\).*?<a href=["\'](https://balticlivecam\.com/cameras/[^"\']+)["\'].*?<h3>(.*?)</h3>',
        text,
        re.I | re.S,
    ):
        thumbnail, url, title = match.groups()
        path_parts = [part for part in urlparse(url).path.strip('/').split('/') if part]
        if len(path_parts) < 4:
            continue
        country = country_from_slug(path_parts[1])
        city = title_from_slug(path_parts[2])
        title = clean_title(title)
        combined = f'{title} {city} {country}'
        if HARD_NEGATIVE_TITLE.search(combined):
            continue
        if NEGATIVE_TITLE.search(combined) and not POSITIVE_TITLE.search(combined):
            continue
        cards.append((thumbnail.strip(' "\''), url, title, city, country))

    items = []
    cache = load_geocode_cache()
    country_counts = {}
    for thumbnail, url, title, city, country in cards:
        if region_for_country(country) == 'Other':
            continue
        if country_counts.get(country, 0) >= 10:
            continue
        location = geocode_location(f'{city}, {country}', cache) or geocode_location(f'{title}, {country}', cache)
        if not location:
            continue
        country_counts[country] = country_counts.get(country, 0) + 1
        item = make_source_item(
            'baltic',
            urlparse(url).path.strip('/'),
            title,
            f'{title} live webcam from Baltic Live Cam',
            location.get('city') or city,
            location.get('country') or country,
            location['lat'],
            location['lng'],
            url,
            priority=61,
            thumbnail_url=thumbnail,
            tags=['tourism', 'baltic', 'source-site'],
            channel='Baltic Live Cam',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_skyline(limit=WORLD_TOUR_SKYLINE_LIMIT):
    if limit <= 0:
        return []
    links = []
    seen = set()
    for list_url in SKYLINE_LIST_URLS:
        try:
            text = fetch_text(list_url, timeout=18)
        except Exception:
            continue
        for match in re.finditer(r'href=["\']((?:/)?en/webcam/[^"\']+\.html)["\']', text, re.I):
            href = html.unescape(match.group(1))
            path = urlparse(urljoin('https://www.skylinewebcams.com/', href)).path
            if path.count('/') < 5:
                continue
            link = urljoin('https://www.skylinewebcams.com/', href)
            if link not in seen:
                seen.add(link)
                links.append(link)

    cache = load_geocode_cache()

    def parse(url):
        try:
            text = fetch_text(url, timeout=14)
        except Exception:
            return None
        path_parts = [part for part in urlparse(url).path.strip('/').split('/') if part]
        if len(path_parts) < 5:
            return None
        country = country_from_slug(path_parts[2])
        city = title_from_slug(path_parts[-2])
        title = text_from_tag(text, 'h1').replace(' Live cam', '').strip() or city
        subtitle = text_from_tag(text, 'h2') or f'{city}, {country} SkylineWebcams live camera'
        combined = f'{title} {subtitle}'
        if HARD_NEGATIVE_TITLE.search(combined):
            return None
        if NEGATIVE_TITLE.search(combined) and not POSITIVE_TITLE.search(combined):
            return None
        location = geocode_location(f'{city}, {country}', cache) or geocode_location(f'{title}, {country}', cache)
        if not location:
            return None
        image_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*img-responsive', text, re.I)
        thumbnail = urljoin(url, html.unescape(image_match.group(1))) if image_match else ''
        return make_source_item(
            'skyline',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            location.get('city') or city,
            location.get('country') or country,
            location['lat'],
            location['lng'],
            url,
            priority=62,
            thumbnail_url=thumbnail,
            tags=['tourism', 'skyline', 'source-site'],
            channel='SkylineWebcams',
        )

    items = []
    country_counts = {}
    for link in links[:450]:
        item = parse(link)
        if not item:
            continue
        if country_counts.get(item['country'], 0) >= 12:
            continue
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_windy(limit=WORLD_TOUR_WINDY_LIMIT):
    api_key = os.getenv('WINDY_WEBCAMS_API_KEY') or os.getenv('WINDY_API_KEY')
    if limit <= 0 or not api_key:
        return []
    headers = {**HEADERS, 'Accept': 'application/json', 'x-windy-api-key': api_key}
    url = 'https://api.windy.com/webcams/api/v3/webcams?limit=' + str(limit) + '&include=location,images,urls'
    try:
        payload = fetch_json_with_headers(url, timeout=18, headers=headers)
    except Exception:
        return []
    raw_items = payload.get('webcams') or payload.get('items') or payload.get('data') or []
    if isinstance(raw_items, dict):
        raw_items = raw_items.get('webcams') or raw_items.get('items') or []

    def choose_image(images):
        if isinstance(images, str):
            return images
        if not isinstance(images, dict):
            return ''
        for key in ('current', 'daylight', 'thumbnail', 'preview'):
            value = images.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, dict):
                for nested_key in ('preview', 'thumbnail', 'url', 'image'):
                    if value.get(nested_key):
                        return value[nested_key]
        return ''

    items = []
    for raw in raw_items:
        location = raw.get('location') if isinstance(raw, dict) else {}
        if not isinstance(location, dict):
            continue
        lat = location.get('latitude') or location.get('lat')
        lng = location.get('longitude') or location.get('lng') or location.get('lon')
        country = location.get('country') or location.get('countryName') or location.get('country_name')
        if isinstance(country, dict):
            country = country.get('name') or country.get('title') or country.get('id')
        city = location.get('city') or location.get('region') or country
        urls = raw.get('urls') if isinstance(raw.get('urls'), dict) else {}
        source_url = urls.get('detail') or urls.get('web') or urls.get('webcam') or raw.get('url') or raw.get('link')
        title = raw.get('title') or raw.get('name') or city
        item = make_source_item(
            'windy',
            raw.get('webcamId') or raw.get('id') or source_url or title,
            title,
            raw.get('description') or f'{city}, {country} Windy webcam',
            city,
            country,
            lat,
            lng,
            source_url or 'https://www.windy.com/webcams',
            priority=72,
            thumbnail_url=choose_image(raw.get('images')),
            tags=['tourism', 'windy', 'source-site'],
            channel='Windy Webcams',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_camscape(limit=WORLD_TOUR_CAMSCAPE_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://www.camscape.com/webcam-map/', timeout=24)
    except Exception:
        return []
    match = re.search(
        r'var\s+camscapeWorldmap\s*=\s*(\{.*?\});\s*//# sourceURL=camscape-worldmap-js-extra',
        text,
        re.S,
    ) or re.search(r'var\s+camscapeWorldmap\s*=\s*(\{.*?\});\s*</script>', text, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    webcams = payload.get('webcams') if isinstance(payload, dict) else {}
    if not isinstance(webcams, dict):
        return []

    def city_hint(title, country):
        for pattern in [
            r'\b(?:in|near|around|at)\s+([A-ZÀ-ž][A-Za-zÀ-ž .\'-]+?)(?:\s+Webcam|\s+Webcams|\s+Cam|\s+Live|$)',
            r'^([A-ZÀ-ž][A-Za-zÀ-ž .\'-]+?)\s+(?:Live|City|Coast|Harbour|Harbor|Beach|Airport|Rail|Landscape)',
        ]:
            match = re.search(pattern, title)
            if match:
                return match.group(1).strip(' -')
        return country

    items = []
    country_counts = {}
    for sid, raw in webcams.items():
        title = clean_title(strip_html_text(raw.get('title')))
        combined = f'{title} {raw.get("link", "")}'
        if HARD_NEGATIVE_TITLE.search(combined):
            continue
        if NEGATIVE_TITLE.search(combined) and not POSITIVE_TITLE.search(combined):
            continue
        lat, lng = raw.get('lat'), raw.get('lng')
        country = country_hint_from_title(title) or country_from_coordinates(lat, lng)
        if region_for_country(country) == 'Other':
            continue
        city = city_hint(title, country)
        if country_counts.get(country, 0) >= 8:
            continue
        country_counts[country] = country_counts.get(country, 0) + 1
        item = make_source_item(
            'camscape',
            sid,
            title,
            f'{city}, {country} Camscape webcam',
            city,
            country,
            lat,
            lng,
            raw.get('link') or 'https://www.camscape.com/webcam-map/',
            priority=62,
            thumbnail_url=raw.get('img') or '',
            tags=['tourism', 'camscape', 'source-site'],
            channel='Camscape',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_livebeaches(limit=WORLD_TOUR_LIVEBEACHES_LIMIT):
    if limit <= 0:
        return []
    items = []
    country_counts = {}
    seeded_ids = set()
    for sid, title, subtitle, city, country, lat, lng, url, priority, video_id in LIVEBEACHES_SOURCE_SEEDS:
        item = make_source_item(
            'livebeaches',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['tourism', 'beach', 'livebeaches'],
            channel='Live Beaches',
        )
        if not item:
            continue
        if video_id:
            item['videoId'] = video_id
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        seeded_ids.add(item['id'])
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            return items

    sitemaps = [
        loc for loc in extract_sitemap_locs('https://www.livebeaches.com/sitemap_index.xml', timeout=18)
        if '/webcams-sitemap' in loc
    ]
    links = []
    seen = set()
    for sitemap in sitemaps:
        for loc in extract_sitemap_locs(sitemap, timeout=18):
            if '/webcams/' not in loc or loc in seen:
                continue
            seen.add(loc)
            links.append(loc)
    cache = load_geocode_cache()
    for url in links[:limit * 5]:
        try:
            text = fetch_text(url, timeout=16)
        except Exception:
            continue
        title = clean_title(extract_meta_content(text, 'og:title') or text_from_tag(text, 'h1'))
        subtitle = extract_meta_content(text, 'og:description') or f'{title} live beach webcam'
        combined = f'{title} {subtitle}'
        if HARD_NEGATIVE_TITLE.search(combined):
            continue
        if NEGATIVE_TITLE.search(combined) and not POSITIVE_TITLE.search(combined):
            continue
        location = infer_source_location(title, subtitle, url, cache)
        if not location:
            continue
        if country_counts.get(location['country'], 0) >= 14:
            continue
        country_counts[location['country']] = country_counts.get(location['country'], 0) + 1
        item = make_source_item(
            'livebeaches',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            location['city'],
            location['country'],
            location['lat'],
            location['lng'],
            url,
            priority=68,
            thumbnail_url=extract_meta_content(text, 'og:image'),
            tags=['tourism', 'beach', 'livebeaches'],
            channel='Live Beaches',
        )
        if not item:
            continue
        if item['id'] in seeded_ids:
            continue
        video_id = extract_youtube_id(text)
        if video_id:
            item['videoId'] = video_id
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_explore(limit=WORLD_TOUR_EXPLORE_LIMIT):
    if limit <= 0:
        return []
    items = []
    for sid, title, subtitle, city, country, lat, lng, url, priority in EXPLORE_SOURCE_SEEDS:
        item = make_source_item(
            'explore',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['nature', 'wildlife', 'explore', 'source-site'],
            channel='Explore.org',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_whatsupcams(limit=WORLD_TOUR_WHATSUP_LIMIT):
    if limit <= 0:
        return []
    items = []
    for sid, title, subtitle, city, country, lat, lng, url, priority in WHATSUPCAM_SOURCE_SEEDS:
        item = make_source_item(
            'whatsupcams',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['tourism', 'whatsupcams', 'source-site'],
            channel="What's Up Cam",
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_hdontap(limit=WORLD_TOUR_HDONTAP_LIMIT):
    if limit <= 0:
        return []
    links = [
        loc for loc in extract_sitemap_locs('https://hdontap.com/sitemap.xml', timeout=28)
        if '/stream/' in loc
    ]
    items = []
    country_counts = {}
    for url in links[:limit * 5]:
        try:
            text = fetch_text(url, timeout=18)
        except Exception:
            continue
        objects = extract_json_ld_objects(text)
        video = next((obj for obj in objects if json_type_matches(obj, 'VideoObject')), {})
        place = next((obj for obj in objects if json_type_matches(obj, 'Place') and obj.get('geo')), {})
        geo = place.get('geo') if isinstance(place.get('geo'), dict) else {}
        address = place.get('address') if isinstance(place.get('address'), dict) else {}
        title = clean_title(video.get('name') or extract_meta_content(text, 'og:title') or text_from_tag(text, 'h1'))
        subtitle = video.get('description') or extract_meta_content(text, 'og:description') or f'{title} HDOnTap live webcam'
        country = normalize_country_name(address.get('addressCountry'))
        city = address.get('addressLocality') or address.get('addressRegion') or country
        lat = geo.get('latitude')
        lng = geo.get('longitude')
        if not country or region_for_country(country) == 'Other':
            cache = load_geocode_cache()
            location = reverse_geocode_location(lat, lng, cache)
            save_geocode_cache(cache)
            if not location:
                continue
            city, country = location['city'], location['country']
        if country_counts.get(country, 0) >= 18:
            continue
        thumbnail = video.get('thumbnailUrl') or extract_meta_content(text, 'og:image')
        if isinstance(thumbnail, list):
            thumbnail = thumbnail[0] if thumbnail else ''
        item = make_source_item(
            'hdontap',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=66,
            thumbnail_url=thumbnail,
            tags=['nature', 'tourism', 'hdontap', 'source-site'],
            channel='HDOnTap',
        )
        if not item:
            continue
        if video.get('embedUrl'):
            item['embedUrl'] = html.unescape(video['embedUrl'])
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_feratel(limit=WORLD_TOUR_FERATEL_LIMIT):
    if limit <= 0:
        return []
    try:
        text = html.unescape(fetch_text('https://www.feratel.com/en/webcams', timeout=30))
    except Exception:
        return []

    def field(block, name):
        match = re.search(rf'"{re.escape(name)}":\[0,"([^"]*)"\]', block)
        return html.unescape(match.group(1)) if match else ''

    items = []
    country_counts = {}
    for match in re.finditer(r'"cam":\[0,\{(.*?)"uploadDate":\[0,"[^"]*"\]\}\]', text, re.S):
        block = match.group(1)
        lat_match = re.search(r'"latitude":\[0,([-0-9.]+)\]', block)
        lng_match = re.search(r'"longitude":\[0,([-0-9.]+)\]', block)
        if not lat_match or not lng_match:
            continue
        name = field(block, 'name')
        path = field(block, 'path')
        country = normalize_country_name(field(block, 'country'))
        if region_for_country(country) == 'Other' and path:
            parts = [part for part in path.strip('/').split('/') if part]
            if 'webcams' in parts and len(parts) > parts.index('webcams') + 1:
                country = country_from_slug(parts[parts.index('webcams') + 1])
        city = field(block, 'location') or (name.split('-')[0].strip() if name else country)
        if country_counts.get(country, 0) >= 16:
            continue
        source_url = urljoin('https://www.feratel.com', path or '/en/webcams')
        poster = field(block, 'poster')
        if poster.startswith('//'):
            poster = 'https:' + poster
        content_url = field(block, 'contentUrl')
        if content_url.startswith('//'):
            content_url = 'https:' + content_url
        item = make_source_item(
            'feratel',
            field(block, 'id') or field(block, 'slug') or path or name,
            name,
            f'{city}, {country} feratel panorama webcam',
            city,
            country,
            lat_match.group(1),
            lng_match.group(1),
            source_url,
            priority=67,
            thumbnail_url=poster,
            tags=['tourism', 'mountain', 'feratel', 'source-site'],
            channel='feratel',
        )
        if not item:
            continue
        if content_url:
            item['embedUrl'] = content_url
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_bergfex(limit=WORLD_TOUR_BERGFEX_LIMIT):
    if limit <= 0:
        return []
    items = []
    for sid, title, subtitle, city, country, lat, lng, url, priority in BERGFEX_SOURCE_SEEDS:
        item = make_source_item(
            'bergfex',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['tourism', 'mountain', 'bergfex', 'source-site'],
            channel='Bergfex',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            return items
    list_urls = [
        'https://www.bergfex.com/lp/webcams/',
        'https://www.bergfex.de/deutschland/webcams/',
        'https://www.bergfex.com/oesterreich/webcams/',
        'https://www.bergfex.ch/schweiz/webcams/',
        'https://www.bergfex.it/italia/webcams/',
    ]
    links = []
    seen = set()
    for list_url in list_urls:
        try:
            text = fetch_text(list_url, timeout=20)
        except HTTPError as error:
            if error.code == 429:
                continue
            continue
        except Exception:
            continue
        for match in re.finditer(r'href=["\']([^"\']*/webcams/c\d+[^"\']*)["\']', text, re.I):
            link = urljoin(list_url, html.unescape(match.group(1)))
            if link not in seen:
                seen.add(link)
                links.append(link)

    cache = load_geocode_cache()
    country_counts = {}
    for item in items:
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
    for url in links[:limit * 5]:
        try:
            text = fetch_text(url, timeout=16)
        except Exception:
            continue
        title = clean_title(extract_meta_content(text, 'og:title') or text_from_tag(text, 'h1'))
        subtitle = extract_meta_content(text, 'og:description') or f'{title} Bergfex webcam'
        if HARD_NEGATIVE_TITLE.search(f'{title} {subtitle}'):
            continue
        coords = extract_maps_coords(text)
        location = None
        if coords:
            location = reverse_geocode_location(coords[0], coords[1], cache)
        if not location:
            location = infer_source_location(title, subtitle, url, cache)
            coords = (location['lat'], location['lng']) if location else None
        if not location or not coords:
            continue
        if country_counts.get(location['country'], 0) >= 12:
            continue
        item = make_source_item(
            'bergfex',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            location['city'],
            location['country'],
            coords[0],
            coords[1],
            url,
            priority=63,
            thumbnail_url=extract_meta_content(text, 'og:image'),
            tags=['tourism', 'mountain', 'bergfex', 'source-site'],
            channel='Bergfex',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_roundshot(limit=WORLD_TOUR_ROUNDSHOT_LIMIT):
    if limit <= 0:
        return []
    items = []
    seen = set()
    for root, fallback_city, fallback_country in ROUNDSHOT_ROOTS:
        try:
            settings = fetch_json(urljoin(root, 'settings.json'), timeout=18)
        except Exception:
            continue

        root_settings = settings.get('settings') if isinstance(settings.get('settings'), dict) else {}
        root_lang = root_settings.get('en') if isinstance(root_settings.get('en'), dict) else {}
        if not root_lang and root_settings:
            root_lang = next((value for value in root_settings.values() if isinstance(value, dict)), {})
        raw_list = settings.get('list') or settings.get('cameras') or []
        if isinstance(raw_list, dict):
            cameras = list(raw_list.values())
        elif isinstance(raw_list, list):
            cameras = raw_list
        else:
            cameras = []
        if not cameras:
            cameras = [settings]

        for cam in cameras:
            if not isinstance(cam, dict):
                continue
            cam_settings = cam.get('settings') if isinstance(cam.get('settings'), dict) else {}
            cam_lang = cam_settings.get('en') if isinstance(cam_settings.get('en'), dict) else {}
            if not cam_lang and cam_settings:
                cam_lang = next((value for value in cam_settings.values() if isinstance(value, dict)), {})
            position = cam.get('position') or settings.get('position') or {}
            lat = position.get('latitude') or position.get('lat') or cam.get('latitude') or settings.get('latitude')
            lng = position.get('longitude') or position.get('lng') or cam.get('longitude') or settings.get('longitude')
            source_url = urljoin(root, html.unescape(str(cam.get('url') or settings.get('url') or root)))
            if source_url in seen:
                continue
            seen.add(source_url)
            title = (
                first_localized_text(cam.get('title')) or
                first_localized_text(cam_lang.get('title')) or
                first_localized_text(root_lang.get('title')) or
                first_localized_text(cam.get('name')) or
                first_localized_text(settings.get('name')) or
                f'{fallback_city} Roundshot'
            )
            city = first_localized_text(cam.get('location')) or first_localized_text(settings.get('location')) or fallback_city
            country = normalize_country_name(
                first_localized_text(cam.get('country')) or
                first_localized_text(settings.get('country')) or
                fallback_country
            )
            thumbnail = (
                cam.get('preview_url') or cam.get('previewUrl') or cam.get('poster') or
                settings.get('preview_url') or settings.get('previewUrl') or ''
            )
            item = make_source_item(
                'roundshot',
                cam.get('id') or settings.get('id') or source_url,
                title,
                f'{city}, {country} high-resolution panorama live camera',
                city,
                country,
                lat,
                lng,
                source_url,
                priority=69,
                thumbnail_url=thumbnail,
                tags=['tourism', 'mountain', 'panorama', 'roundshot', 'source-site'],
                channel='Roundshot',
            )
            if item:
                items.append(item)
            if len(items) >= limit:
                return items
    return items


def twlivecam_score(raw):
    combined = f"{raw.get('n', '')} {raw.get('r', '')} {raw.get('co', '')} {raw.get('di', '')}"
    score = 0
    if raw.get('st') == 'youtube':
        score += 24
    if TWLIVECAM_SCENIC_PATTERN.search(combined):
        score += 30
    if TWLIVECAM_TRAFFIC_PATTERN.search(combined):
        score -= 14
    if re.search(r'(台北|高雄|台中|台南|基隆|花蓮|宜蘭|澎湖|屏東)', combined):
        score += 5
    return score


def collect_twlivecam(limit=WORLD_TOUR_TWLIVECAM_LIMIT):
    if limit <= 0:
        return []
    try:
        data = fetch_json('https://livecam.tw/data/cameras.json', timeout=25)
    except Exception:
        return []
    candidates = []
    for raw in data if isinstance(data, list) else []:
        combined = f"{raw.get('n', '')} {raw.get('r', '')} {raw.get('co', '')} {raw.get('di', '')}"
        if raw.get('s') != 'live':
            continue
        if not (is_finite_number(raw.get('la')) and is_finite_number(raw.get('lo'))):
            continue
        score = twlivecam_score(raw)
        if score <= 0 and not TWLIVECAM_SCENIC_PATTERN.search(combined):
            continue
        candidates.append((score, raw))
    candidates.sort(key=lambda pair: (-pair[0], str(pair[1].get('id') or '')))

    items = []
    county_counts = {}
    for score, raw in candidates[:limit * 4]:
        county = strip_html_text(raw.get('co') or raw.get('r') or 'Taiwan')
        if county_counts.get(county, 0) >= 8:
            continue
        sid = raw.get('id')
        detail_url = f'https://livecam.tw/cam/{sid}/'
        video_id = ''
        thumbnail = ''
        if raw.get('st') == 'youtube':
            try:
                page = fetch_text(detail_url, timeout=10)
                video_id = extract_youtube_id(page) or ''
                thumbnail = extract_meta_content(page, 'og:image')
            except Exception:
                pass
        title = strip_html_text(raw.get('n')) or county
        district = strip_html_text(raw.get('di') or county)
        item = make_source_item(
            'twlivecam',
            sid or title,
            title,
            f'{county} {district} Taiwan public live camera',
            district or county,
            'Taiwan',
            raw.get('la'),
            raw.get('lo'),
            detail_url,
            priority=max(58, min(74, 62 + score // 5)),
            thumbnail_url=thumbnail,
            tags=['tourism', 'taiwan', 'twlivecam', 'source-site'],
            channel='TW Live CAM',
        )
        if not item:
            continue
        if video_id:
            item['videoId'] = video_id
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        county_counts[county] = county_counts.get(county, 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_worldcamlive(limit=WORLD_TOUR_WORLDCAMLIVE_LIMIT):
    if limit <= 0:
        return []
    try:
        payload = fetch_json('https://worldcam.live/api/list/map', timeout=18)
    except Exception:
        return []
    items = []
    country_counts = {}
    for raw in payload if isinstance(payload, list) else []:
        domain = str(raw.get('domain') or '').strip()
        title = clean_title(strip_html_text(raw.get('title') or domain))
        map_value = str(raw.get('map') or '')
        parts = [part.strip() for part in map_value.split(',')]
        if len(parts) != 2 or not domain:
            continue
        lat, lng = parts
        combined = f'{title} {domain}'
        if WORLDCAMLIVE_NEGATIVE.search(combined) or HARD_NEGATIVE_TITLE.search(combined):
            continue
        if not WORLDCAMLIVE_POSITIVE.search(combined):
            continue
        country = country_hint_from_title(title) or country_from_coordinates(lat, lng, fallback='Poland')
        if country_counts.get(country, 0) >= 14:
            continue
        city = re.split(r'\s+-\s+|\s+ul\.|\s+na żywo', title, flags=re.I)[0].strip() or country
        source_url = f'https://worldcam.live/webcam/{domain}'
        item = make_source_item(
            'worldcamlive',
            domain,
            title,
            f'{city}, {country} public live webcam indexed by WorldCam.Live',
            city,
            country,
            lat,
            lng,
            source_url,
            priority=62,
            thumbnail_url=f'https://worldcam.live/img/webcams/121/{domain}.jpg',
            tags=['tourism', 'worldcamlive', 'source-site'],
            channel='WorldCam.Live',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_liveworldwebcams(limit=WORLD_TOUR_LIVEWORLDWEBCAMS_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://liveworldwebcams.com/', timeout=22)
    except Exception:
        return []
    links = []
    seen = set()
    for match in re.finditer(r'href=["\'](https://liveworldwebcams\.com/[^"\']*webcam[^"\']*/)["\']', text, re.I):
        url = html.unescape(match.group(1))
        if '/category/' in url or url in seen:
            continue
        seen.add(url)
        links.append(url)

    items = []
    for url in links[:limit * 4]:
        try:
            page = fetch_text(url, timeout=16)
        except Exception:
            continue
        coords = re.search(r'id=["\']webcam-map["\'][^>]+data-lat=["\']([-0-9.]+)["\'][^>]+data-lng=["\']([-0-9.]+)', page, re.I)
        if not coords:
            continue
        lat, lng = coords.group(1), coords.group(2)
        title = clean_title(extract_meta_content(page, 'og:title') or text_from_tag(page, 'h1'))
        subtitle = extract_meta_content(page, 'og:description') or f'{title} live webcam'
        country = country_hint_from_title(title) or country_hint_from_title(subtitle) or country_from_coordinates(lat, lng)
        city = re.split(r'\s+Webcam|,|-', title)[0].strip() or country
        item = make_source_item(
            'liveworldwebcams',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=66,
            thumbnail_url=extract_meta_content(page, 'og:image'),
            tags=['tourism', 'liveworldwebcams', 'source-site'],
            channel='Live World Webcams',
        )
        if not item:
            continue
        video_id = extract_youtube_id(page)
        if video_id:
            item['videoId'] = video_id
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        else:
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', page, re.I)
            if iframe_match:
                item['embedUrl'] = html.unescape(iframe_match.group(1))
                item['status'] = 'is_live'
                item['sourceOnly'] = False
        items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_webcamhopper(limit=WORLD_TOUR_WEBCAMHOPPER_LIMIT):
    if limit <= 0:
        return []
    list_urls = [
        'https://www.webcamhopper.com/',
        'https://www.webcamhopper.com/airport.html',
        'https://www.webcamhopper.com/beach.html',
        'https://www.webcamhopper.com/europe/uk.html',
        'https://www.webcamhopper.com/asia/japan.html',
        'https://www.webcamhopper.com/asia/south_korea.html',
        'https://www.webcamhopper.com/asia/thailand.html',
        'https://www.webcamhopper.com/north_america/canada.html',
    ]
    links = []
    seen = set()
    for list_url in list_urls:
        try:
            text = fetch_text(list_url, timeout=16)
        except Exception:
            continue
        for match in re.finditer(r'href=["\']([^"\']*/map/\d+\.html(?:#[^"\']+)?)["\']', text, re.I):
            url = urljoin(list_url, html.unescape(match.group(1)))
            if url not in seen:
                seen.add(url)
                links.append(url)

    items = []
    for url in links[:limit * 4]:
        try:
            page = fetch_text(url, timeout=14)
        except Exception:
            continue
        coords = extract_maps_coords(page)
        if not coords:
            continue
        title = clean_title(extract_meta_content(page, 'og:title') or text_from_tag(page, 'title'))
        subtitle = extract_meta_content(page, 'og:description') or f'{title} webcam from Webcam Hopper'
        country_match = re.search(r'<div>Location</div><div><a[^>]+>([^<]+)</a>', page, re.I)
        country = normalize_country_name(country_match.group(1)) if country_match else ''
        if region_for_country(country) == 'Other':
            country = country_hint_from_title(f'{title} {subtitle}') or country_from_coordinates(coords[0], coords[1])
        city = re.split(r'\s+Webcam|,|-', title)[0]
        city = re.sub(r'^Live\s+(?:Webcam\s+)?(?:at|of)\s+', '', city, flags=re.I).strip() or country
        item = make_source_item(
            'webcamhopper',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            city,
            country,
            coords[0],
            coords[1],
            url,
            priority=65,
            thumbnail_url='https://www.webcamhopper.com/thumb/' + urlparse(url).path.strip('/').split('/')[-1].split('.')[0] + '.jpg',
            tags=['tourism', 'webcamhopper', 'source-site'],
            channel='Webcam Hopper',
        )
        if item:
            video_id = extract_youtube_id(page)
            if video_id:
                item['videoId'] = video_id
                item['status'] = 'is_live'
                item['sourceOnly'] = False
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_worldcamtv(limit=WORLD_TOUR_WORLDCAMTV_LIMIT):
    if limit <= 0:
        return []
    try:
        payload = fetch_json('https://lsikrghvxtbyveqqctqf.supabase.co/storage/v1/object/public/page-cache/homepage-hero.json', timeout=18)
    except Exception:
        return []
    cache = load_geocode_cache()
    items = []
    for raw in payload.get('webcams', []):
        if not raw.get('is_live'):
            continue
        location_text = raw.get('location') or raw.get('country') or ''
        location = (
            source_location_hint(f'{raw.get("title", "")} {location_text}') or
            youtube_location_hint(f'{raw.get("title", "")} {location_text}') or
            geocode_location(location_text, cache)
        )
        if not location:
            continue
        slug = raw.get('slug') or raw.get('id') or raw.get('title')
        source_url = 'https://worldcam.tv/webcam/' + str(slug)
        item = make_source_item(
            'worldcamtv',
            raw.get('id') or slug,
            raw.get('title') or location_text,
            f'{location_text} WorldCam.tv live webcam',
            location['city'],
            location['country'],
            location['lat'],
            location['lng'],
            source_url,
            priority=66,
            thumbnail_url=raw.get('thumbnail_url') or '',
            tags=['tourism', 'worldcamtv', 'source-site'],
            channel='WorldCam.tv',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_livecamcroatia(limit=WORLD_TOUR_LIVECAMCROATIA_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://www.livecamcroatia.com/', timeout=22)
    except Exception:
        return []
    links = []
    seen = set()
    for match in re.finditer(r'href=["\'](/hr/kamera/[^"\']+)["\']', text, re.I):
        url = urljoin('https://www.livecamcroatia.com/', html.unescape(match.group(1)))
        if url in seen:
            continue
        if re.search(r'(gradiliste|poslovnog|king-cross|roda|cigoc)', url, re.I):
            continue
        seen.add(url)
        links.append(url)

    items = []
    for url in links[:limit * 4]:
        try:
            page = fetch_text(url, timeout=16)
        except Exception:
            continue
        coords = re.search(r'/hr/karta\?lon=([-0-9.]+)&lat=([-0-9.]+)', page)
        if not coords:
            continue
        title = clean_title(extract_meta_content(page, 'og:title') or text_from_tag(page, 'title'))
        title = re.sub(r', \[.*$', '', title).strip()
        subtitle = extract_meta_content(page, 'og:description') or f'{title} live camera from Croatia'
        city = title.split(',')[-1].strip() if ',' in title else title_from_slug(urlparse(url).path.strip('/').split('/')[-1])
        item = make_source_item(
            'livecamcroatia',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            city,
            'Croatia',
            coords.group(2),
            coords.group(1),
            url,
            priority=65,
            thumbnail_url=extract_meta_content(page, 'og:image'),
            tags=['tourism', 'croatia', 'livecamcroatia', 'source-site'],
            channel='LiveCamCroatia',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_openwebcamdb(limit=WORLD_TOUR_OPENWEBCAMDB_LIMIT):
    api_key = os.getenv('OPENWEBCAMDB_API_KEY')
    if limit <= 0 or not api_key:
        return []
    headers = {**HEADERS, 'Accept': 'application/json', 'Authorization': f'Bearer {api_key}'}
    items = []
    page = 1
    while len(items) < limit and page <= 5:
        url = f'https://openwebcamdb.com/api/v1/webcams?per_page={min(100, limit)}&page={page}'
        try:
            payload = fetch_json_with_headers(url, timeout=18, headers=headers)
        except Exception:
            break
        raw_items = payload.get('data') or payload.get('webcams') or payload.get('items') or []
        if isinstance(raw_items, dict):
            raw_items = raw_items.get('data') or raw_items.get('webcams') or raw_items.get('items') or []
        if not isinstance(raw_items, list) or not raw_items:
            break
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            loc = raw.get('location') if isinstance(raw.get('location'), dict) else {}
            lat = raw.get('latitude') or raw.get('lat') or loc.get('latitude') or loc.get('lat')
            lng = raw.get('longitude') or raw.get('lng') or raw.get('lon') or loc.get('longitude') or loc.get('lng') or loc.get('lon')
            if not (is_finite_number(lat) and is_finite_number(lng)):
                continue
            country = raw.get('country') or loc.get('country') or country_from_coordinates(lat, lng)
            if isinstance(country, dict):
                country = country.get('name') or country.get('title') or country.get('code')
            city = raw.get('city') or loc.get('city') or loc.get('name') or country
            title = clean_title(raw.get('title') or raw.get('name') or f'{city} webcam')
            source_url = (
                raw.get('source_url') or raw.get('sourceUrl') or raw.get('page_url') or raw.get('pageUrl') or
                raw.get('url') or raw.get('webcam_url') or raw.get('webcamUrl') or 'https://openwebcamdb.com/'
            )
            item = make_source_item(
                'openwebcamdb',
                raw.get('id') or raw.get('uuid') or source_url or title,
                title,
                raw.get('description') or f'{city}, {country} OpenWebcamDB live webcam',
                city,
                country,
                lat,
                lng,
                source_url,
                priority=64,
                thumbnail_url=raw.get('thumbnail_url') or raw.get('thumbnailUrl') or raw.get('image_url') or raw.get('imageUrl') or '',
                tags=['tourism', 'openwebcamdb', 'source-site'],
                channel='OpenWebcamDB',
            )
            if not item:
                continue
            embed_url = raw.get('embed_url') or raw.get('embedUrl') or raw.get('player_url') or raw.get('playerUrl')
            if embed_url:
                item['embedUrl'] = embed_url
                item['status'] = 'is_live'
                item['sourceOnly'] = False
            items.append(item)
            if len(items) >= limit:
                break
        page += 1
    return items


def collect_viewsurf(limit=WORLD_TOUR_VIEWSURF_LIMIT):
    if limit <= 0:
        return []
    links = []
    seen = set()
    for list_url, category in VIEWSURF_LIST_URLS:
        try:
            text = fetch_text(list_url, timeout=20)
        except Exception:
            continue
        for match in re.finditer(r'href=["\'](/univers/[^"\']+/vue/\d+-[^"\']+)["\']', text, re.I):
            url = urljoin('https://www.viewsurf.com/', html.unescape(match.group(1)))
            if url in seen:
                continue
            seen.add(url)
            links.append((url, category))

    cache = load_geocode_cache()
    items = []
    country_counts = {}
    for url, category in links[:limit * 5]:
        try:
            page = fetch_text(url, timeout=16)
        except Exception:
            continue
        description = extract_meta_content(page, 'description')
        parts = [part.strip() for part in re.split(r'\s+-\s+', description) if part.strip()]
        if len(parts) >= 5 and parts[1].lower() == 'france':
            country = 'France'
            city = parts[3]
            place = ' - '.join(parts[4:])
        else:
            slug_parts = urlparse(url).path.strip('/').split('/')[-1].split('-')
            if len(slug_parts) < 5:
                continue
            country = country_from_slug(slug_parts[1])
            city = title_from_slug(slug_parts[3])
            place = title_from_slug('-'.join(slug_parts[4:]))
        combined = f'{city} {place} {description}'
        if HARD_NEGATIVE_TITLE.search(combined):
            continue
        if NEGATIVE_TITLE.search(combined) and not POSITIVE_TITLE.search(combined):
            continue
        if country_counts.get(country, 0) >= 24:
            continue
        location = (
            geocode_location(f'{place}, {city}, {country}', cache) or
            geocode_location(f'{city}, {country}', cache)
        )
        if not location:
            continue
        title = clean_title(f'{city} - {place}' if place else city)
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']*joada\.net/[^"\']+)["\']', page, re.I)
        thumb_match = re.search(r'data-source=["\']([^"\']+)["\']', page, re.I)
        item = make_source_item(
            'viewsurf',
            urlparse(url).path.strip('/'),
            title,
            description or f'{city}, {country} ViewSurf live webcam',
            location.get('city') or city,
            location.get('country') or country,
            location['lat'],
            location['lng'],
            url,
            priority=66 if category in {'city', 'beach'} else 63,
            thumbnail_url=html.unescape(thumb_match.group(1)) if thumb_match else '',
            tags=['tourism', category, 'viewsurf', 'source-site'],
            channel='ViewSurf',
        )
        if not item:
            continue
        if iframe_match:
            item['embedUrl'] = html.unescape(iframe_match.group(1))
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_airportwebcams(limit=WORLD_TOUR_AIRPORTWEBCAMS_LIMIT):
    if limit <= 0:
        return []
    links = []
    seen = set()
    for list_url in AIRPORTWEBCAMS_CATEGORY_URLS:
        try:
            text = fetch_text(list_url, timeout=20)
        except Exception:
            continue
        for match in re.finditer(r'https://airportwebcams\.net/[a-z0-9-]+-airport-webcam/', text, re.I):
            url = html.unescape(match.group(0))
            if url in seen:
                continue
            seen.add(url)
            links.append(url)

    items = []
    country_counts = {}
    for url in links[:limit * 5]:
        try:
            page = fetch_text(url, timeout=16)
        except Exception:
            continue
        coord_match = re.search(r'flightradar24\.com/([-0-9.]+),([-0-9.]+)/', page, re.I)
        if not coord_match:
            continue
        lat, lng = coord_match.group(1), coord_match.group(2)
        country = country_from_coordinates(lat, lng)
        if region_for_country(country) == 'Other':
            country = country_hint_from_title(page)
        if region_for_country(country) == 'Other':
            continue
        if country_counts.get(country, 0) >= 8:
            continue
        title = clean_title(extract_meta_content(page, 'og:title') or text_from_tag(page, 'title'))
        title = re.sub(r'\s*-\s*Airport Webcams\.net\s*$', '', title, flags=re.I)
        subtitle = extract_meta_content(page, 'og:description') or f'{title} airport webcam directory page'
        city = re.sub(r'\s+(?:International\s+)?Airport(?:\s+Webcam)?$', '', title, flags=re.I).strip() or country
        item = make_source_item(
            'airportwebcams',
            urlparse(url).path.strip('/'),
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=65,
            thumbnail_url=extract_meta_content(page, 'og:image'),
            tags=['airport', 'aviation', 'airportwebcams', 'source-site'],
            channel='AirportWebcams.net',
        )
        if not item:
            continue
        video_id = extract_youtube_id(page)
        if video_id:
            item['videoId'] = video_id
            item['status'] = 'is_live'
            item['sourceOnly'] = False
        country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
        items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_panomax(limit=WORLD_TOUR_PANOMAX_LIMIT):
    if limit <= 0:
        return []
    try:
        payload = fetch_json('https://api.panomax.com/1.0/maps/panomaxweb', timeout=24)
    except Exception:
        return []
    instances = payload.get('instances') if isinstance(payload, dict) else {}
    if not isinstance(instances, dict):
        return []
    items = []
    country_counts = {}
    for raw in instances.values():
        if not isinstance(raw, dict):
            continue
        cam = raw.get('cam') if isinstance(raw.get('cam'), dict) else {}
        lat, lng = cam.get('latitude'), cam.get('longitude')
        country = country_from_coordinates(lat, lng)
        if region_for_country(country) == 'Other':
            continue
        if country_counts.get(country, 0) >= 10:
            continue
        raw_name = first_localized_text(raw.get('name'))
        cam_name = first_localized_text(cam.get('name'))
        title = clean_title(cam_name if re.search(r'^360', raw_name or '', re.I) else (raw_name or cam_name))
        if not title or HARD_NEGATIVE_TITLE.search(title):
            continue
        city = re.split(r'\s+-\s+|,', title)[0].strip() or country
        cam_id = cam.get('id') or raw.get('id') or title
        thumbnail = f'https://panodata.panomax.com/cams/{cam_id}/preview_og.jpg' if cam_id else ''
        item = make_source_item(
            'panomax',
            raw.get('id') or cam_id,
            title,
            f'{title} Panomax high-resolution panorama webcam',
            city,
            country,
            lat,
            lng,
            'https://map.panomax.com/?id=panomaxweb',
            priority=66,
            thumbnail_url=thumbnail,
            tags=['tourism', 'panorama', 'panomax', 'source-site'],
            channel='Panomax',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


def mexico_location_override(place):
    place_key = ascii_key(place)
    for key, value in MEXICO_LOCATION_OVERRIDES.items():
        if ascii_key(key) == place_key:
            return value
    return None


def webcamsdemexico_terms():
    terms = {}
    for page in range(1, 5):
        url = f'https://webcamsdemexico.com/wp-json/wp/v2/webcam_localidad?per_page=100&page={page}&_fields=id,name'
        try:
            payload = fetch_json(url, timeout=16)
        except Exception:
            break
        if not isinstance(payload, list) or not payload:
            break
        for raw in payload:
            terms[int(raw.get('id'))] = strip_html_text(raw.get('name'))
        if len(payload) < 100:
            break
    return terms


def collect_webcamsdemexico(limit=WORLD_TOUR_WEBCAMSMEXICO_LIMIT):
    if limit <= 0:
        return []
    terms = webcamsdemexico_terms()
    cache = load_geocode_cache()
    items = []
    seen = set()
    skip_pattern = re.compile(r'(rancho-la-onza|bebedero|bordo|subacuatica|subacuática)', re.I)
    for page_number in range(1, 5):
        url = (
            'https://webcamsdemexico.com/wp-json/wp/v2/webcammx'
            f'?per_page=100&page={page_number}&_fields=id,link,title,content,webcam_localidad,yoast_head,slug'
        )
        try:
            payload = fetch_json(url, timeout=20)
        except Exception:
            break
        if not isinstance(payload, list) or not payload:
            break
        for raw in payload:
            link = raw.get('link') or ''
            slug = raw.get('slug') or urlparse(link).path.strip('/').split('/')[-1]
            if not link or slug in seen or skip_pattern.search(f'{slug} {raw.get("title", {})}'):
                continue
            seen.add(slug)
            title = clean_title(first_localized_text((raw.get('title') or {}).get('rendered')))
            subtitle = clean_subtitle(first_localized_text((raw.get('content') or {}).get('rendered')), f'{title} live webcam')
            term_ids = raw.get('webcam_localidad') if isinstance(raw.get('webcam_localidad'), list) else []
            city = ''
            for term_id in term_ids:
                if int(term_id) in terms:
                    city = terms[int(term_id)]
                    break
            yoast = raw.get('yoast_head') or ''
            seo_title = extract_meta_content(yoast, 'og:title')
            if not city and seo_title:
                match = re.search(r'en vivo,\s*([^-]+)\s+-\s*Webcams', seo_title, re.I)
                if match:
                    city = match.group(1).strip()
            if not city:
                city = re.split(r'[,|-]', title)[0].strip()
            country = 'Spain' if re.search(r'(ribera del duero|valladolid|españa)', f'{title} {subtitle}', re.I) else 'Mexico'
            override = mexico_location_override(city) if country == 'Mexico' else None
            if override:
                city, country, lat, lng = override
                location = {'city': city, 'country': country, 'lat': lat, 'lng': lng}
            else:
                location = geocode_location(f'{city}, {country}', cache)
            if not location:
                continue
            combined = f'{title} {subtitle}'
            if HARD_NEGATIVE_TITLE.search(combined):
                continue
            detail = ''
            video_id = None
            try:
                detail = fetch_text(link, timeout=14)
                video_match = re.search(r'"stream"\s*:\s*"([A-Za-z0-9_-]{11})"', detail)
                if video_match and re.search(r'"mostrar_stream"\s*:\s*"1"', detail):
                    video_id = video_match.group(1)
                else:
                    video_id = extract_youtube_id(detail)
            except Exception:
                detail = ''
            thumbnail = extract_meta_content(detail, 'og:image') or extract_meta_content(yoast, 'og:image')
            item = make_source_item(
                'webcamsdemexico',
                raw.get('id') or slug,
                title,
                subtitle,
                location.get('city') or city,
                location.get('country') or country,
                location['lat'],
                location['lng'],
                link,
                priority=66,
                thumbnail_url=thumbnail,
                tags=['tourism', 'mexico', 'webcamsdemexico', 'source-site'],
                channel='Webcams de Mexico',
            )
            if not item:
                continue
            if video_id:
                item['videoId'] = video_id
                item['status'] = 'is_live'
                item['sourceOnly'] = False
            items.append(item)
            if len(items) >= limit:
                save_geocode_cache(cache)
                return items
        if len(payload) < 100:
            break
    save_geocode_cache(cache)
    return items


CLIMAAOVIVO_AUTH = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOjE1NzEyNDU4ODB9.WBl7Iy1pvYIWzM8RYdlFdTdTgeQ/s9YnHNvXQa9lR7c='


def climaaovivo_source_url(raw):
    state = latin_slug(raw.get('dessigla') or '')
    city = latin_slug(raw.get('descidade') or '')
    slug = str(raw.get('desurl') or '').strip('/')
    if not state or not slug:
        return 'https://www.climaaovivo.com.br/cidades'
    if int(str(raw.get('totalcamerascidade') or '1') or '1') > 1 and city:
        return f'https://www.climaaovivo.com.br/{state}/{city}/{slug}'
    return f'https://www.climaaovivo.com.br/{state}/{slug}'


def collect_climaaovivo(limit=WORLD_TOUR_CLIMAAOVIVO_LIMIT):
    if limit <= 0:
        return []
    headers = {**HEADERS, 'Authorization': CLIMAAOVIVO_AUTH, 'Accept': 'application/json'}
    try:
        payload = fetch_json_with_headers('https://cmsv2.climaaovivo.com.br/api/cameras', timeout=24, headers=headers)
    except Exception:
        return []
    raw_items = payload.get('data') if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        return []
    items = []
    state_counts = {}
    for raw in raw_items:
        if not isinstance(raw, dict) or raw.get('inprivada') == '1':
            continue
        lat, lng = raw.get('deslatitude'), raw.get('deslongitude')
        if not (is_finite_number(lat) and is_finite_number(lng)):
            continue
        state = str(raw.get('dessigla') or '').upper()
        if state_counts.get(state, 0) >= 8:
            continue
        city = strip_html_text(raw.get('descidade') or 'Brazil')
        title = clean_title(f'{city} - {raw.get("destitulo") or "Clima Ao Vivo"}')
        item = make_source_item(
            'climaaovivo',
            raw.get('idcamera') or raw.get('descodigo') or title,
            title,
            f'{city}/{state} official Clima Ao Vivo weather camera',
            city,
            'Brazil',
            lat,
            lng,
            climaaovivo_source_url(raw),
            priority=64,
            tags=['weather', 'city', 'climaaovivo', 'source-site'],
            channel='Clima Ao Vivo',
        )
        if item:
            state_counts[state] = state_counts.get(state, 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


HK_TRAFFIC_LOCATION_URLS = [
    'https://static.data.gov.hk/td/traffic-snapshot-images/code/Traffic_Camera_Locations_En.xml',
    'https://static.data.gov.hk/td/traffic-snapshot-images/code/Traffic_Camera_Locations_En.csv',
]
HK_TRAFFIC_SUMMARY_PDF_URL = 'https://www.gov.hk/en/theme/psi/datasets/Summary_of_traffic_snapshot_images%28Eng%29.pdf'


def normalized_field_name(name):
    return re.sub(r'[^a-z0-9]+', '', str(name or '').lower())


def pick_field(row, *names):
    for name in names:
        key = normalized_field_name(name)
        value = row.get(key)
        if value not in (None, ''):
            return strip_html_text(value)
    return ''


def hk_grid_to_wgs84(easting, northing):
    easting = re.sub(r'[^0-9.-]+', '', str(easting or ''))
    northing = re.sub(r'[^0-9.-]+', '', str(northing or ''))
    if not (is_finite_number(easting) and is_finite_number(northing)):
        return None
    origin_lat = 22.3121333333333
    origin_lng = 114.178555555556
    false_easting = 836694.05
    false_northing = 819069.80
    meters_per_degree_lng = 111320 * math.cos(math.radians(origin_lat))
    lat = origin_lat + (float(northing) - false_northing) / 110900
    lng = origin_lng + (float(easting) - false_easting) / meters_per_degree_lng
    if not (21.9 <= lat <= 22.7 and 113.7 <= lng <= 114.6):
        return None
    return round(lat, 6), round(lng, 6)


def iter_hktraffic_csv_rows(text):
    text = text.lstrip('\ufeff')
    for delimiter in ('\t', ','):
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames or len(reader.fieldnames) < 3:
            continue
        for raw_row in reader:
            yield {normalized_field_name(key): value for key, value in raw_row.items()}
        return


def iter_hktraffic_xml_rows(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return
    for node in root.iter():
        children = list(node)
        if len(children) < 3:
            continue
        row = {}
        for child in children:
            tag = normalized_field_name(child.tag.split('}', 1)[-1])
            value = ''.join(child.itertext()).strip()
            if tag and value:
                row[tag] = value
        if row:
            yield row


def iter_hktraffic_pdf_rows():
    try:
        from pypdf import PdfReader
        raw = fetch_bytes(HK_TRAFFIC_SUMMARY_PDF_URL, timeout=30)
        reader = PdfReader(io.BytesIO(raw))
    except Exception:
        return
    text = ' '.join(page.extract_text() or '' for page in reader.pages)
    text = re.sub(r'\s+', ' ', text)
    pattern = re.compile(
        r'\b([A-Z]{1,3}\d{3,4}F\d*)\s+\1\.JPG\s+(.*?)\s+'
        r'(\d(?:\s?\d){5})\s+(\d(?:\s?\d){5})\s+'
        r'http://tdcctv\.data\.one\.gov\.hk/([A-Z0-9]+)\s*\.JPG',
        re.I,
    )
    for match in pattern.finditer(text):
        key, description, easting, northing, url_key = match.groups()
        url_key = url_key.upper()
        yield {
            'key': key.upper(),
            'description': description,
            'easting': easting,
            'northing': northing,
            'url': f'https://tdcctv.data.one.gov.hk/{url_key}.JPG',
        }


def make_hktraffic_item(row, district_counts):
    key = pick_field(row, 'key', 'cameraid', 'camera', 'cameraimagefilename')
    if key:
        key = re.sub(r'\.jpg$', '', key, flags=re.I).strip()
    description = pick_field(row, 'description', 'location', 'name') or key or 'Hong Kong traffic camera'
    district = pick_field(row, 'district', 'region', 'area') or 'Hong Kong'
    if district_counts.get(district, 0) >= 8:
        return None
    image_url = pick_field(row, 'url', 'imageurl', 'link')
    if not image_url.startswith('http') and key:
        image_url = f'https://tdcctv.data.one.gov.hk/{quote(key)}.JPG'
    lat = pick_field(row, 'latitude', 'lat')
    lng = pick_field(row, 'longitude', 'long', 'lng', 'lon')
    if not (is_finite_number(lat) and is_finite_number(lng)):
        coords = hk_grid_to_wgs84(
            pick_field(row, 'easting', 'image location easting coordinate'),
            pick_field(row, 'northing', 'image location northing coordinate'),
        )
        if not coords:
            return None
        lat, lng = coords
    if not image_url.startswith('http'):
        return None
    item = make_source_item(
        'hktraffic',
        key or description,
        f'Hong Kong Traffic - {description}',
        f'{district} official Transport Department traffic snapshot camera',
        district,
        'Hong Kong',
        lat,
        lng,
        image_url,
        priority=61,
        thumbnail_url=image_url,
        tags=['traffic', 'public-data', 'hktraffic', 'source-site'],
        channel='Hong Kong Transport Department',
    )
    if item:
        district_counts[district] = district_counts.get(district, 0) + 1
    return item


def collect_hktraffic(limit=WORLD_TOUR_HKTRAFFIC_LIMIT):
    if limit <= 0:
        return []
    row_sources = []
    for url in HK_TRAFFIC_LOCATION_URLS:
        try:
            raw = fetch_bytes(url, timeout=24)
        except Exception:
            continue
        if url.endswith('.xml'):
            text = raw.decode('utf-8', 'replace')
            row_sources.append(iter_hktraffic_xml_rows(text))
        else:
            for encoding in ('utf-16', 'utf-8-sig', 'utf-8', 'big5'):
                try:
                    text = raw.decode(encoding)
                    break
                except UnicodeError:
                    text = ''
            if text:
                row_sources.append(iter_hktraffic_csv_rows(text))
    if not row_sources:
        row_sources.append(iter_hktraffic_pdf_rows())
    items = []
    district_counts = {}
    seen = set()
    for rows in row_sources:
        for row in rows:
            key = pick_field(row, 'key', 'cameraid', 'camera', 'cameraimagefilename')
            normalized_key = ascii_key(key or pick_field(row, 'description', 'location', 'name'))
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            item = make_hktraffic_item(row, district_counts)
            if item:
                items.append(item)
            if len(items) >= limit:
                return items
        if items:
            return items
    return items


def collect_usgsvolcano(limit=WORLD_TOUR_USGS_VOLCANO_LIMIT):
    if limit <= 0:
        return []
    try:
        payload = fetch_json('https://volcview.wr.usgs.gov/ashcam-api/webcamApi/webcams', timeout=28)
    except Exception:
        return []
    raw_items = payload.get('webcams') if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        return []
    items = []
    volcano_counts = {}
    for raw in raw_items:
        if not isinstance(raw, dict) or raw.get('hasImages') != 'Y':
            continue
        lat, lng = raw.get('latitude'), raw.get('longitude')
        country = country_from_coordinates(lat, lng, fallback='United States')
        if region_for_country(country) == 'Other':
            continue
        volcano = strip_html_text(raw.get('vName') or raw.get('webcamName') or 'Volcano')
        if volcano_counts.get(volcano, 0) >= 4:
            continue
        code = raw.get('webcamCode') or raw.get('webcamName') or volcano
        title = clean_title(f'{volcano} - {raw.get("webcamName") or "USGS Volcano Cam"}')
        image_url = raw.get('currentImageUrl') or raw.get('currentMediumImageUrl') or raw.get('clearImageUrl') or ''
        thumb_url = raw.get('currentThumbImageUrl') or raw.get('currentMediumImageUrl') or image_url
        source_url = raw.get('externalUrl') or image_url or f'https://volcview.wr.usgs.gov/ashcam-api/webcamApi/webcam/{quote(str(code))}'
        item = make_source_item(
            'usgsvolcano',
            code,
            title,
            f'Official USGS/AVO volcano monitoring webcam for {volcano}',
            volcano,
            country,
            lat,
            lng,
            source_url,
            priority=67,
            thumbnail_url=thumb_url,
            tags=['volcano', 'weather', 'usgs', 'source-site'],
            channel='USGS VolcView',
        )
        if item:
            if image_url and not item.get('thumbnailUrl'):
                item['thumbnailUrl'] = image_url
            volcano_counts[volcano] = volcano_counts.get(volcano, 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


def parse_aurora_coordinate_pair(text):
    text = html.unescape(strip_html_text(text)).replace('′', "'").replace('″', '"')
    decimal = re.search(r'([-0-9.]+)\s*[°]?\s*([NS])\s*,?\s+([-0-9.]+)\s*[°]?\s*([EW])', text, re.I)
    if decimal:
        lat = float(decimal.group(1)) * (-1 if decimal.group(2).upper() == 'S' else 1)
        lng = float(decimal.group(3)) * (-1 if decimal.group(4).upper() == 'W' else 1)
        return lat, lng
    signed = re.search(r'\b([-0-9]{1,3}\.\d+)\s*,\s*([-0-9]{1,3}\.\d+)\b', text)
    if signed:
        return float(signed.group(1)), float(signed.group(2))
    dms = re.search(
        r'(\d{1,3})°\s*(\d{1,2})?\'?\s*(\d{1,2})?"?\s*([NS]).*?'
        r'(\d{1,3})°\s*(\d{1,2})?\'?\s*(\d{1,2})?"?\s*([EW])',
        text,
        re.I,
    )
    if not dms:
        return None
    lat = float(dms.group(1)) + float(dms.group(2) or 0) / 60 + float(dms.group(3) or 0) / 3600
    lng = float(dms.group(5)) + float(dms.group(6) or 0) / 60 + float(dms.group(7) or 0) / 3600
    if dms.group(4).upper() == 'S':
        lat *= -1
    if dms.group(8).upper() == 'W':
        lng *= -1
    return lat, lng


def collect_aurorainfo(limit=WORLD_TOUR_AURORAINFO_LIMIT):
    if limit <= 0:
        return []
    page_url = 'https://aurorainfo.eu/aurora-live-cameras/'
    try:
        text = fetch_text(page_url, timeout=20)
    except Exception:
        return []
    items = []
    for match in re.finditer(r'<h2[^>]*id=["\']([^"\']+)["\'][^>]*>(.*?)</h2>(.*?)(?=<h2|</article>)', text, re.I | re.S):
        sid, raw_title, block = match.groups()
        title = clean_title(strip_html_text(raw_title))
        coords = parse_aurora_coordinate_pair(block)
        if not coords:
            continue
        country = country_hint_from_title(title) or country_from_coordinates(coords[0], coords[1])
        if region_for_country(country) == 'Other':
            continue
        city = re.split(r',|-', title)[0].strip() or country
        image_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', block, re.I)
        links = [
            html.unescape(href) for href in re.findall(r'<a[^>]+href=["\']([^"\']+)["\']', block, re.I)
            if 'google.com/maps' not in href
        ]
        item = make_source_item(
            'aurorainfo',
            sid,
            title,
            f'{city}, {country} northern lights live/all-sky camera',
            city,
            country,
            coords[0],
            coords[1],
            links[0] if links else f'{page_url}#{sid}',
            priority=65,
            thumbnail_url=urljoin(page_url, html.unescape(image_match.group(1))) if image_match else '',
            tags=['aurora', 'night-sky', 'weather', 'aurorainfo', 'source-site'],
            channel='AuroraInfo',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_nswtraffic(limit=WORLD_TOUR_NSW_TRAFFIC_LIMIT):
    if limit <= 0:
        return []
    try:
        payload = fetch_json('https://data.livetraffic.com/cameras/traffic-cam.json', timeout=20)
    except Exception:
        return []
    features = payload.get('features') if isinstance(payload, dict) else []
    items = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        geometry = feature.get('geometry') or {}
        coords = geometry.get('coordinates') if isinstance(geometry, dict) else None
        if not isinstance(coords, list) or len(coords) < 2:
            continue
        lng, lat = coords[0], coords[1]
        props = feature.get('properties') or {}
        title = clean_title(props.get('title') or feature.get('id') or 'NSW Traffic Camera')
        view = props.get('view') or f'{title} official NSW traffic camera'
        region = str(props.get('region') or '')
        city = 'Sydney' if region.startswith('SYD') else 'New South Wales'
        item = make_source_item(
            'nswtraffic',
            feature.get('id') or title,
            title,
            view,
            city,
            'Australia',
            lat,
            lng,
            'https://www.livetraffic.com/traffic-cameras',
            priority=62,
            thumbnail_url=props.get('href') or '',
            tags=['traffic', 'public-data', 'nswtraffic', 'source-site'],
            channel='Transport for NSW',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_dctraffic(limit=WORLD_TOUR_DC_TRAFFIC_LIMIT):
    if limit <= 0:
        return []
    endpoints = [
        ('cctv', 'https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_Sensors_WebMercator/MapServer/11/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson'),
        ('traffic', 'https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Transportation_Sensors_WebMercator/MapServer/93/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=geojson'),
    ]
    items = []
    seen = set()
    for layer, url in endpoints:
        try:
            payload = fetch_json(url, timeout=20)
        except Exception:
            continue
        features = payload.get('features') if isinstance(payload, dict) else []
        for feature in features:
            if not isinstance(feature, dict):
                continue
            geometry = feature.get('geometry') or {}
            coords = geometry.get('coordinates') if isinstance(geometry, dict) else None
            if not isinstance(coords, list) or len(coords) < 2:
                continue
            lng, lat = coords[0], coords[1]
            props = feature.get('properties') or {}
            sid = props.get('GLOBALID') or props.get('OBJECTID') or props.get('CAMERAID') or feature.get('id')
            if not sid or sid in seen:
                continue
            seen.add(sid)
            name = props.get('NAME') or props.get('FACILITYID') or props.get('CAMERAID') or sid
            address = props.get('ADDRESS') or props.get('DESCRIPTION') or 'Washington, DC traffic camera'
            title = clean_title(f'DC {name}')
            item = make_source_item(
                'dctraffic',
                sid,
                title,
                str(address),
                'Washington',
                'United States',
                lat,
                lng,
                url,
                priority=61 if layer == 'cctv' else 59,
                tags=['traffic', 'public-data', 'dctraffic', 'source-site'],
                channel='Open Data DC',
            )
            if item:
                items.append(item)
            if len(items) >= limit:
                return items
    return items


def collect_alertcalifornia(limit=WORLD_TOUR_ALERTCALIFORNIA_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://status.alertcalifornia.org/', timeout=18)
    except Exception:
        return []
    new_section = text[text.find('new_camera_map'):] if 'new_camera_map' in text else text
    items = []
    seen = set()
    for match in re.finditer(r'L\.marker\(\[\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\],\s*\{"title":\s*"([^"]+)"', new_section):
        lat, lng, title = match.groups()
        title = clean_title(title)
        if title in seen:
            continue
        seen.add(title)
        item = make_source_item(
            'alertcalifornia',
            title,
            title,
            'ALERTCalifornia wildfire camera network site',
            'California',
            'United States',
            lat,
            lng,
            'https://status.alertcalifornia.org/',
            priority=59,
            tags=['wildfire', 'weather', 'alertcalifornia', 'source-site'],
            channel='ALERTCalifornia',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_wetter(limit=WORLD_TOUR_WETTER_LIMIT):
    if limit <= 0:
        return []
    links = []
    seen = set()
    for list_url, country in WETTER_LIST_URLS:
        try:
            text = fetch_text(list_url, timeout=18)
        except Exception:
            continue
        for match in re.finditer(r'href=["\']([^"\']*/hd-live-webcams/[^"\']+/[a-z0-9-]+/[a-f0-9]{12,}/)["\']', text, re.I):
            link = urljoin(list_url, html.unescape(match.group(1)))
            if link in seen:
                continue
            seen.add(link)
            links.append((link, country))

    skip_pattern = re.compile(r'(storch|stork|nest|horst|zoo|tierpark)', re.I)
    cache = load_geocode_cache()
    items = []
    country_counts = {}
    for url, fallback_country in links[:limit * 5]:
        try:
            text = fetch_text(url, timeout=14)
        except Exception:
            continue
        title = clean_title(extract_meta_content(text, 'og:title') or text_from_tag(text, 'h1'))
        subtitle = extract_meta_content(text, 'og:description') or f'{title} wetter.com live webcam'
        combined = f'{title} {subtitle} {url}'
        if skip_pattern.search(combined) or HARD_NEGATIVE_TITLE.search(combined):
            continue
        lat_match = re.search(r'itemprop=["\']latitude["\']\s+content=["\']([-0-9.]+)', text, re.I)
        lng_match = re.search(r'itemprop=["\']longitude["\']\s+content=["\']([-0-9.]+)', text, re.I)
        display_title = re.sub(r'\s*\|\s*wetter\.com\s*$', '', title, flags=re.I)
        display_title = re.sub(r'^HD Live Webcam\s+', '', display_title, flags=re.I).strip()
        if lat_match and lng_match:
            lat, lng = lat_match.group(1), lng_match.group(1)
            country = country_from_coordinates(lat, lng, fallback=fallback_country)
            city = re.split(r'\s+-\s+', display_title)[0].strip() or country
        else:
            path_parts = [part for part in urlparse(url).path.strip('/').split('/') if part]
            slug_city = title_from_slug(path_parts[-2]) if len(path_parts) >= 2 else ''
            location = (
                infer_source_location(display_title, subtitle, url, cache) or
                geocode_location(f'{slug_city}, {fallback_country}', cache)
            )
            if not location:
                continue
            lat, lng = location['lat'], location['lng']
            country = location['country']
            city = location['city'] or slug_city or country
        if country_counts.get(country, 0) >= 8:
            continue
        item = make_source_item(
            'wetter',
            urlparse(url).path.strip('/'),
            display_title or title,
            subtitle,
            city,
            country,
            lat_match.group(1),
            lng_match.group(1),
            url,
            priority=63,
            thumbnail_url=extract_meta_content(text, 'og:image'),
            tags=['weather', 'tourism', 'wetter', 'source-site'],
            channel='wetter.com',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    save_geocode_cache(cache)
    return items


def collect_panoramask(limit=WORLD_TOUR_PANORAMASK_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://www.panorama.sk/en/slovakia/webcams-map', timeout=24)
    except Exception:
        return []
    match = re.search(r'var\s+locations\s*=\s*(\[\[.*?\]\]);', text, re.S)
    if not match:
        return []
    row_pattern = re.compile(r"\[(\d+),'((?:\\'|[^'])*)',([-0-9.]+),([-0-9.]+),'((?:\\'|[^'])*)',\d+\]")
    positive = re.compile(r'(airport|beach|bridge|castle|city|golf|lake|marina|mountain|namestie|panorama|peak|river|ski|square|street|tatras|view|venice|waterfront)', re.I)
    negative = re.compile(r'(stork|bocian|fauna|record only|recordings|aquapark|swimming|pool|thermal|camping|restaurant)', re.I)
    items = []
    country_counts = {}
    for row in row_pattern.finditer(match.group(1)):
        sid, raw_title, lat, lng, slug = row.groups()
        title = clean_title(raw_title.replace("\\'", "'"))
        combined = f'{title} {slug}'
        if negative.search(combined) or HARD_NEGATIVE_TITLE.search(combined):
            continue
        if not positive.search(combined):
            continue
        country = country_hint_from_title(title) or country_from_coordinates(lat, lng, fallback='Slovakia')
        if country_counts.get(country, 0) >= 8:
            continue
        city = re.split(r'\s+-\s+|,\s+', title)[0].strip() or country
        source_url = f'https://www.panorama.sk/en/webcam/{slug}/{sid}'
        item = make_source_item(
            'panoramask',
            sid,
            title,
            f'{city}, {country} Panorama.sk public webcam',
            city,
            country,
            lat,
            lng,
            source_url,
            priority=62,
            thumbnail_url=f'https://oh.sk/webcams/d/{sid}.jpg',
            tags=['tourism', 'mountain', 'panoramask', 'source-site'],
            channel='Panorama.sk',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_idokep(limit=WORLD_TOUR_IDOKEP_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://www.idokep.hu/webkamera', timeout=22)
    except Exception:
        return []
    start = text.find('<ul class="ik webcam-list"')
    if start < 0:
        start = text.find('webcam-list')
    block = text[start:] if start >= 0 else text
    cache = load_geocode_cache()
    items = []
    seen = set()
    country_counts = {}
    skip_pattern = re.compile(r'(g[óo]lya|mad[aá]r|bagoly|allsky|csillag|tulsotet)', re.I)
    anchor_pattern = r'<a\b(?P<attrs>(?:"[^"]*"|\'[^\']*\'|[^>])*)>(?P<label>.*?)</a>'
    for match in re.finditer(anchor_pattern, block, re.I | re.S):
        attrs = html.unescape(match.group('attrs'))
        href_match = re.search(r'href=["\'](/webkamera/([^/"\']+))["\']', attrs, re.I)
        if not href_match:
            continue
        slug = href_match.group(2)
        if slug in seen or slug == 'tag':
            continue
        title = clean_title(strip_html_text(match.group('label')))
        if not title or skip_pattern.search(f'{title} {attrs}'):
            continue
        seen.add(slug)
        place = re.split(r'\s+-\s+|,', title)[0].strip()
        if len(place) < 3:
            continue
        override = IDOKEP_LOCATION_OVERRIDES.get(ascii_key(place))
        if not override:
            continue
        city, country, lat, lng = override
        if country_counts.get(country, 0) >= 22:
            continue
        thumbnail_match = re.search(r'src=//([^"\'\s>]+/thumbnail\.jpg)', attrs, re.I)
        thumbnail = ('https://' + thumbnail_match.group(1)) if thumbnail_match else ''
        url = 'https://www.idokep.hu/webkamera/' + slug
        item = make_source_item(
            'idokep',
            slug,
            title,
            f'{city}, {country} Idokep weather webcam',
            city,
            country,
            lat,
            lng,
            url,
            priority=62,
            thumbnail_url=thumbnail,
            tags=['weather', 'tourism', 'idokep', 'source-site'],
            channel='Idokep',
        )
        if item:
            country_counts[item['country']] = country_counts.get(item['country'], 0) + 1
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_ptztv(limit=WORLD_TOUR_PTZTV_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://www.ptztv.com/', timeout=18)
    except Exception:
        text = ''
    links = []
    seen = set()
    for match in re.finditer(r'href=["\'](https?://(?:www\.)?([^/"\']+)[^"\']*)["\']', text, re.I):
        url = html.unescape(match.group(1))
        host = match.group(2).lower()
        if host.startswith('www.'):
            host = host[4:]
        if host in PTZTV_CAMERA_META and host not in seen:
            seen.add(host)
            links.append((host, url))
    if not links:
        links = [(host, 'https://www.' + host) for host in PTZTV_CAMERA_META]

    items = []
    for host, url in links:
        title, subtitle, city, country, lat, lng = PTZTV_CAMERA_META[host]
        item = make_source_item(
            'ptztv',
            host,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=65,
            tags=['tourism', 'port', 'ptztv', 'source-site'],
            channel='PTZtv',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_railcam(limit=WORLD_TOUR_RAILCAM_LIMIT):
    if limit <= 0:
        return []
    try:
        text = fetch_text('https://railcam.nl/', timeout=20)
    except Exception:
        text = ''
    title = clean_title(extract_meta_content(text, 'og:title') or text_from_tag(text, 'title') or 'Railcam Netherlands')
    video_id = extract_youtube_id(text)
    item = make_source_item(
        'railcam',
        'mierlo-hout-helmond',
        title,
        'Railway live camera from Mierlo-Hout and Helmond',
        'Helmond',
        'Netherlands',
        51.4816,
        5.661,
        'https://railcam.nl/',
        priority=66,
        thumbnail_url=extract_meta_content(text, 'og:image'),
        tags=['rail', 'transport', 'railcam'],
        channel='Railcam Netherlands',
    )
    if not item:
        return []
    if video_id:
        item['videoId'] = video_id
        item['status'] = 'is_live'
        item['sourceOnly'] = False
    return [item]


def collect_public_traffic(limit=WORLD_TOUR_PUBLIC_TRAFFIC_LIMIT):
    if limit <= 0:
        return []
    items = []
    for sid, title, subtitle, city, country, lat, lng, url, priority in PUBLIC_TRAFFIC_SEEDS:
        item = make_source_item(
            'publictraffic',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['traffic', 'public-data', 'source-site'],
            channel='Public Traffic Data',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_africam_seeds(limit=WORLD_TOUR_AFRICAM_LIMIT):
    if limit <= 0:
        return []
    items = []
    for sid, title, subtitle, city, country, lat, lng, url, priority in AFRICAM_SOURCE_SEEDS:
        item = make_source_item(
            'africam',
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=['nature', 'wildlife', 'africam', 'source-site'],
            channel='Africam',
        )
        if item:
            items.append(item)
        if len(items) >= limit:
            break
    return items


def collect_thematic_seeds():
    tag_by_type = {
        'spacecam': ['space', 'science', 'spacecam', 'source-site'],
        'animalcam': ['wildlife', 'animalcam', 'source-site'],
        'golfcam': ['sports', 'golf', 'golfcam', 'source-site'],
        'airportwebcams': ['airport', 'aviation', 'airportwebcams', 'source-site'],
        'weatherbug': ['weather', 'weatherbug', 'source-site'],
        'surfline': ['surf', 'beach', 'surfline', 'source-site'],
        'railcamuk': ['rail', 'transport', 'railcamuk', 'source-site'],
        'japanwebcams': ['tourism', 'japan', 'japanwebcams', 'source-site'],
    }
    items = []
    for source_type, sid, title, subtitle, city, country, lat, lng, url, priority, channel in THEMATIC_SOURCE_SEEDS:
        item = make_source_item(
            source_type,
            sid,
            title,
            subtitle,
            city,
            country,
            lat,
            lng,
            url,
            priority=priority,
            tags=tag_by_type.get(source_type, ['tourism', source_type, 'source-site']),
            channel=channel,
        )
        if item:
            items.append(item)
    return items


def collect_webcamtaxi_seeds():
    items = [
        make_source_item('webcamtaxi', sid, title, subtitle, city, country, lat, lng, url, priority=priority, channel='Webcamtaxi')
        for sid, title, subtitle, city, country, region, lat, lng, url, priority in WEBCAMTAXI_SEEDS
    ]
    return [item for item in items if item]


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


def extract_iframe_embed(text):
    match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', text or '', re.I)
    if not match:
        return None
    embed_url = html.unescape(match.group(1)).strip()
    if embed_url.startswith('//'):
        embed_url = 'https:' + embed_url
    if embed_url.startswith(('http://', 'https://')):
        return embed_url
    return None


def enrich_source_only_embeds(items, limit=WORLD_TOUR_SOURCE_ENRICH_LIMIT):
    """Opportunistically convert source-site-only entries into embeddable entries.

    This is intentionally conservative: it only promotes clearly public YouTube
    and iframe players already present on the source page. It does not crawl raw
    RTSP/IP-camera URLs or bypass source-site players.
    """
    if limit <= 0:
        return {'checked': 0, 'promoted': 0}
    checked = 0
    promoted = 0
    for item in items:
        if checked >= limit:
            break
        if item.get('videoId') or item.get('embedUrl') or not item.get('sourceUrl'):
            continue
        checked += 1
        try:
            page = fetch_text(item['sourceUrl'], timeout=8)
        except Exception:
            continue
        video_id = extract_youtube_id(page)
        if video_id:
            item['videoId'] = video_id
            item['playbackStatus'] = 'unchecked'
            item['sourceOnly'] = False
            promoted += 1
            continue
        embed_url = extract_iframe_embed(page)
        if embed_url and not re.search(r'(google\.com/maps|openstreetmap|leaflet|facebook\.com/plugins)', embed_url, re.I):
            item['embedUrl'] = embed_url
            item['playbackStatus'] = 'verified'
            item['sourceOnly'] = False
            promoted += 1
    return {'checked': checked, 'promoted': promoted}


def validate_youtube_item(item):
    video_id = item.get('videoId')
    if not video_id:
        item['playbackStatus'] = 'verified' if item.get('embedUrl') else 'source-only' if item.get('sourceUrl') else 'unchecked'
        item['lastCheckedAt'] = dt.date.today().isoformat()
        item['stabilityScore'] = max(55, int(float(item.get('priority') or 60)))
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
    elif item.get('playbackStatus') == 'source-only':
        score -= 4
    elif item.get('playbackStatus') == 'unchecked':
        score -= 12
    if POSITIVE_TITLE.search(combined_title):
        score += 5
    if NEGATIVE_TITLE.search(combined_title) and source_type not in WILDLIFE_SOURCE_TYPES:
        score -= 18
    if HARD_NEGATIVE_TITLE.search(combined_title):
        if source_type in WILDLIFE_SOURCE_TYPES and not re.search(r'(Kensington|Skid Row|Sloppy|Murphy|Truck Queue|Camping Prive|카지노)', combined_title, re.I):
            score -= 4
        else:
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
    snapshot_only_removed = sum(1 for item in items if is_snapshot_only_item(item))
    if snapshot_only_removed:
        print(f'excluding snapshot-only world tour feeds: {snapshot_only_removed}', flush=True)
    candidates = [item for item in items if not is_snapshot_only_item(item)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        validated = [item for item in executor.map(validate_youtube_item, candidates) if item]
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
    collector_steps = [
        ('cctv_world', collect_cctv_world),
        ('tabi', collect_tabi),
        ('webcamera24', lambda: collect_webcamera24(WORLD_TOUR_WEBCAMERA24_LIMIT)),
        ('earthcam', collect_earthcam),
        ('worldcam', collect_worldcam),
        ('baltic', collect_baltic),
        ('skyline', collect_skyline),
        ('windy', collect_windy),
        ('livebeaches', collect_livebeaches),
        ('camscape', collect_camscape),
        ('explore', collect_explore),
        ('whatsupcams', collect_whatsupcams),
        ('hdontap', collect_hdontap),
        ('feratel', collect_feratel),
        ('bergfex', collect_bergfex),
        ('roundshot', collect_roundshot),
        ('twlivecam', collect_twlivecam),
        ('worldcamlive', collect_worldcamlive),
        ('liveworldwebcams', collect_liveworldwebcams),
        ('webcamhopper', collect_webcamhopper),
        ('worldcamtv', collect_worldcamtv),
        ('livecamcroatia', collect_livecamcroatia),
        ('openwebcamdb', collect_openwebcamdb),
        ('viewsurf', collect_viewsurf),
        ('airportwebcams', collect_airportwebcams),
        ('panomax', collect_panomax),
        ('webcamsdemexico', collect_webcamsdemexico),
        ('climaaovivo', collect_climaaovivo),
        ('hktraffic', collect_hktraffic),
        ('usgsvolcano', collect_usgsvolcano),
        ('aurorainfo', collect_aurorainfo),
        ('nswtraffic', collect_nswtraffic),
        ('dctraffic', collect_dctraffic),
        ('alertcalifornia', collect_alertcalifornia),
        ('wetter', collect_wetter),
        ('panoramask', collect_panoramask),
        ('idokep', collect_idokep),
        ('ptztv', collect_ptztv),
        ('railcam', collect_railcam),
        ('public_traffic', collect_public_traffic),
        ('africam', collect_africam_seeds),
        ('thematic_seeds', collect_thematic_seeds),
        ('webcamtaxi', collect_webcamtaxi_seeds),
        ('youtube_search', collect_youtube_search),
    ]
    additions = []
    collector_health = []
    for name, collector in collector_steps:
        print(f'collecting {name}...', flush=True)
        started = time.perf_counter()
        error_summary = None
        try:
            collected = run_with_collector_timeout(collector)
        except Exception as error:
            error_summary = f'{type(error).__name__}: {error}'
            print(f'{name} error {error_summary}', flush=True)
            collected = []
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        print(f'{name} {len(collected)}', flush=True)
        collector_health.append({
            'source': name,
            'count': len(collected),
            'elapsedMs': elapsed_ms,
            'status': 'ok' if error_summary is None else 'error',
            'error': error_summary,
        })
        additions.extend(collected)
    enrichment_stats = enrich_source_only_embeds(additions)
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
        'description': 'Curated public world tourist live/webcam directory. In-app playable YouTube/embed streams are prioritized; snapshot-only feeds are excluded because they are not continuous video.',
        'collectionMeta': {
            'itemCount': len(items),
            'sourceCounts': dict(source_counts),
            'regionCounts': dict(region_counts),
            'playbackCounts': dict(playback_counts),
            'qualityTiers': dict(quality_counts),
            'youtubeSearchQueries': youtube_search_queries(),
            'youtubeSearchLimit': YOUTUBE_SEARCH_LIMIT,
            'youtubeSearchPerQueryLimit': YOUTUBE_SEARCH_PER_QUERY_LIMIT,
            'earthCamLimit': WORLD_TOUR_EARTHCAM_LIMIT,
            'worldCamLimit': WORLD_TOUR_WORLDCAM_LIMIT,
            'balticLimit': WORLD_TOUR_BALTIC_LIMIT,
            'skylineLimit': WORLD_TOUR_SKYLINE_LIMIT,
            'webcamera24Limit': WORLD_TOUR_WEBCAMERA24_LIMIT,
            'windyLimit': WORLD_TOUR_WINDY_LIMIT,
            'livebeachesLimit': WORLD_TOUR_LIVEBEACHES_LIMIT,
            'camscapeLimit': WORLD_TOUR_CAMSCAPE_LIMIT,
            'exploreLimit': WORLD_TOUR_EXPLORE_LIMIT,
            'whatsupcamsLimit': WORLD_TOUR_WHATSUP_LIMIT,
            'bergfexLimit': WORLD_TOUR_BERGFEX_LIMIT,
            'feratelLimit': WORLD_TOUR_FERATEL_LIMIT,
            'hdontapLimit': WORLD_TOUR_HDONTAP_LIMIT,
            'roundshotLimit': WORLD_TOUR_ROUNDSHOT_LIMIT,
            'twlivecamLimit': WORLD_TOUR_TWLIVECAM_LIMIT,
            'worldCamLiveLimit': WORLD_TOUR_WORLDCAMLIVE_LIMIT,
            'liveWorldWebcamsLimit': WORLD_TOUR_LIVEWORLDWEBCAMS_LIMIT,
            'webcamHopperLimit': WORLD_TOUR_WEBCAMHOPPER_LIMIT,
            'worldCamTvLimit': WORLD_TOUR_WORLDCAMTV_LIMIT,
            'liveCamCroatiaLimit': WORLD_TOUR_LIVECAMCROATIA_LIMIT,
            'openWebcamDbLimit': WORLD_TOUR_OPENWEBCAMDB_LIMIT,
            'viewSurfLimit': WORLD_TOUR_VIEWSURF_LIMIT,
            'airportWebcamsLimit': WORLD_TOUR_AIRPORTWEBCAMS_LIMIT,
            'panomaxLimit': WORLD_TOUR_PANOMAX_LIMIT,
            'webcamsMexicoLimit': WORLD_TOUR_WEBCAMSMEXICO_LIMIT,
            'climaAoVivoLimit': WORLD_TOUR_CLIMAAOVIVO_LIMIT,
            'hkTrafficLimit': WORLD_TOUR_HKTRAFFIC_LIMIT,
            'usgsVolcanoLimit': WORLD_TOUR_USGS_VOLCANO_LIMIT,
            'auroraInfoLimit': WORLD_TOUR_AURORAINFO_LIMIT,
            'nswTrafficLimit': WORLD_TOUR_NSW_TRAFFIC_LIMIT,
            'dcTrafficLimit': WORLD_TOUR_DC_TRAFFIC_LIMIT,
            'africamLimit': WORLD_TOUR_AFRICAM_LIMIT,
            'alertCaliforniaLimit': WORLD_TOUR_ALERTCALIFORNIA_LIMIT,
            'wetterLimit': WORLD_TOUR_WETTER_LIMIT,
            'panoramaSkLimit': WORLD_TOUR_PANORAMASK_LIMIT,
            'idokepLimit': WORLD_TOUR_IDOKEP_LIMIT,
            'ptztvLimit': WORLD_TOUR_PTZTV_LIMIT,
            'railcamLimit': WORLD_TOUR_RAILCAM_LIMIT,
            'publicTrafficLimit': WORLD_TOUR_PUBLIC_TRAFFIC_LIMIT,
            'qualityPolicy': 'verified playback, source trust, positive tourist context, and coordinate availability are scored before ranking.',
            'sourcePolicy': 'Only public official/source-site or embeddable tourist webcams are retained; snapshot-only feeds, raw exposed IP camera scanners, and private RTSP feeds are excluded.',
            'snapshotPolicy': 'Static or periodically refreshed image-only feeds are removed from the user-facing global CCTV list.',
            'openWebcamDbStatus': 'API-key gated via OPENWEBCAMDB_API_KEY; default disabled until terms and attribution are configured.',
            'insecamStatus': 'Excluded: unsecured private surveillance camera directory, not suitable for this curated public tourist dataset.',
            'generationNote': 'Some source counts can include retained items from previous verified runs when a collector is disabled, API-key gated, or rate-limited during the latest run.',
            'collectorHealth': collector_health,
            'sourceOnlyEnrichment': enrichment_stats,
            'httpCache': {
                **HTTP_CACHE_STATS,
                'ttlHours': WORLD_TOUR_HTTP_CACHE_TTL_HOURS,
                'staleFallbackHours': WORLD_TOUR_STALE_CACHE_HOURS,
                'timeoutCapSeconds': WORLD_TOUR_HTTP_TIMEOUT_CAP,
            }
        },
        'items': items
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    save_http_cache()
    print('items', len(items))
    print('sources', dict(source_counts))
    print('regions', dict(region_counts))
    print('external_only', sum(1 for i in items if not (i.get('videoId') or i.get('embedUrl'))))
    print('playback', dict(playback_counts))
    print('quality', dict(quality_counts))

if __name__ == '__main__':
    main()
