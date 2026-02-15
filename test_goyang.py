from collectors.goyang import GoyangCollector
import json

collector = GoyangCollector()
streams = collector.fetch_data()

if streams:
    print(f"Fetched {len(streams)} streams.")
    print("Sample stream 0:")
    print(json.dumps(streams[0], indent=2, ensure_ascii=False))
else:
    print("Failed to fetch streams.")
