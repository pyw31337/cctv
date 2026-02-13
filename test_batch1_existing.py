from collectors.ulsan import UlsanCollector
from collectors.busan import BusanCollector
import json

def test():
    print("Testing Ulsan...")
    ulsan = UlsanCollector().fetch_data()
    print(f"Ulsan: {len(ulsan)} items collected.")
    if ulsan: print(json.dumps(ulsan[0], indent=2, ensure_ascii=False))

    print("\nTesting Busan...")
    busan = BusanCollector().fetch_data()
    print(f"Busan: {len(busan)} items collected.")
    if busan: print(json.dumps(busan[0], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test()
