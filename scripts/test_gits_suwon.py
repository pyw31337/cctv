import sys
import os

# Add collectors to path
sys.path.append(os.path.join(os.getcwd(), 'collectors'))
from collectors.gits import GitsCollector

collector = GitsCollector()
data = collector.fetch_data()

suwon_count = 0
for item in data:
    if "수원" in item['name']:
        print(f"[{item['id']}] {item['name']} - {item['url']}")
        suwon_count += 1

print(f"Total Suwon items in GITS: {suwon_count}")
