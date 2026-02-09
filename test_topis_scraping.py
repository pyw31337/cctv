from collectors.topis import TopisCollector
import json

def test_topis():
    print("Testing TopisCollector (Scraping)...")
    collector = TopisCollector()
    data = collector.fetch_data()
    
    print(f"Collected {len(data)} items.")
    if data:
        print("Sample item:")
        print(json.dumps(data[0], indent=2, ensure_ascii=False))
        
        # Verify a specific one if possible
        found_cam = None
        for item in data:
            if "삼육" in item['name'] or "교문" in item['name']:
                 found_cam = item
                 break
        
        if found_cam:
            print(f"Found target camera: {found_cam['name']} -> {found_cam['url']}")
    else:
        print("No data collected.")

if __name__ == "__main__":
    test_topis()
