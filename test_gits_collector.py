from collectors.gits import GitsCollector
import json

def test_gits():
    print("Testing GitsCollector...")
    collector = GitsCollector()
    data = collector.fetch_data()
    
    print(f"Collected {len(data)} items.")
    if data:
        print("Sample item:")
        print(json.dumps(data[0], indent=2, ensure_ascii=False))
        
        # Check source distribution
        sources = {}
        for item in data:
            src = item.get('source', 'Unknown')
            sources[src] = sources.get(src, 0) + 1
        print("Sources:", sources)

if __name__ == "__main__":
    test_gits()
