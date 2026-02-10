import sys
import os
import json

# Add parent directory to path to import collectors
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from collectors.busan import BusanCollector
from collectors.incheon import IncheonCollector
from collectors.daejeon import DaejeonCollector
from collectors.gwangju import GwangjuCollector
from collectors.ulsan import UlsanCollector
from collectors.daegu import DaeguCollector
from collectors.sejong import SejongCollector
from collectors.jeju import JejuCollector
from collectors.gangwon import GangwonCollector

def test_collectors():
    print("=== Testing Regional Collectors ===")
    
    # 1. Busan
    try:
        busan = BusanCollector()
        busan_data = busan.fetch_data()
        print(f"Busan: {len(busan_data)} items found.")
        if busan_data:
            print(f"Sample: {busan_data[0]['name']} -> {busan_data[0]['url']}")
    except Exception as e:
        print(f"Busan Error: {e}")

    # 2. Incheon
    try:
        incheon = IncheonCollector()
        incheon_data = incheon.fetch_data()
        print(f"Incheon: {len(incheon_data)} items found.")
        if incheon_data:
            print(f"Sample: {incheon_data[0]['name']} -> {incheon_data[0]['url']}")
    except Exception as e:
        print(f"Incheon Error: {e}")

    # 3. Daejeon
    try:
        daejeon = DaejeonCollector()
        daejeon_data = daejeon.fetch_data()
        print(f"Daejeon: {len(daejeon_data)} items found.")
        if daejeon_data:
            print(f"Sample: {daejeon_data[0]['name']} -> {daejeon_data[0]['url']}")
    except Exception as e:
        print(f"Daejeon Error: {e}")

    # 4. Jeju
    try:
        jeju = JejuCollector()
        # Fetching first 5 only for speed in test
        jeju_data = jeju.fetch_data()[:5]
        print(f"Jeju: {len(jeju_data)} sample items fetched.")
        if jeju_data:
            print(f"Sample: {jeju_data[0]['name']} -> {jeju_data[0]['url']}")
    except Exception as e:
        print(f"Jeju Error: {e}")

    # 5. Gangwon
    try:
        gangwon = GangwonCollector()
        gangwon_data = gangwon.fetch_data()
        print(f"Gangwon: {len(gangwon_data)} items found.")
        if gangwon_data:
            print(f"Sample: {gangwon_data[0]['name']} -> {gangwon_data[0]['url']}")
    except Exception as e:
        print(f"Gangwon Error: {e}")

    # 6. Gwangju
    try:
        gwangju = GwangjuCollector()
        gwangju_data = gwangju.fetch_data()
        print(f"Gwangju: {len(gwangju_data)} items found.")
        if gwangju_data:
            print(f"Sample: {gwangju_data[0]['name']} -> {gwangju_data[0]['url']}")
    except Exception as e:
        print(f"Gwangju Error: {e}")

    # 7. Ulsan
    try:
        ulsan = UlsanCollector()
        ulsan_data = ulsan.fetch_data()
        print(f"Ulsan: {len(ulsan_data)} items found.")
        if ulsan_data:
            print(f"Sample: {ulsan_data[0]['name']} -> {ulsan_data[0]['url']}")
    except Exception as e:
        print(f"Ulsan Error: {e}")

    # 8. Daegu
    try:
        daegu = DaeguCollector()
        daegu_data = daegu.fetch_data()
        print(f"Daegu: {len(daegu_data)} items found.")
        if daegu_data:
            print(f"Sample: {daegu_data[0]['name']} -> {daegu_data[0]['url']}")
    except Exception as e:
        print(f"Daegu Error: {e}")

    # 9. Sejong
    try:
        sejong = SejongCollector()
        sejong_data = sejong.fetch_data()
        print(f"Sejong: {len(sejong_data)} items found.")
        if sejong_data:
            print(f"Sample: {sejong_data[0]['name']} -> {sejong_data[0]['url']}")
    except Exception as e:
        print(f"Sejong Error: {e}")

if __name__ == "__main__":
    test_collectors()
