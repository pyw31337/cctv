import json
import os
import time
from collectors.icheon import IcheonCollector
from collectors.ggex import GGEXCollector
from collectors.goyang import GoyangCollector
from collectors.chungju import ChungjuCollector
from collectors.knps import KNPSCollector
from utils.geocoder import GeocodeHelper

def test_integration():
    print("Starting Batch 1 Integration Test...")
    
    # Simulate fetch
    print("Fetching Batch 1 data...")
    icheon_data = IcheonCollector().fetch_data()
    ggex_data = GGEXCollector().fetch_data()
    goyang_data = GoyangCollector().fetch_data()
    chungju_data = ChungjuCollector().fetch_data()
    knps_data = KNPSCollector().fetch_data()
    
    final_merged = []
    
    # Priority (simplified for test)
    collectors = [
        ('ICITS', icheon_data),
        ('GGEX', ggex_data),
        ('GOYANG', goyang_data),
        ('CHUNGJU', chungju_data),
        ('KNPS', knps_data),
    ]

    for source_name, data in collectors:
        print(f"Merging {source_name} ({len(data)} items)...")
        for item in data:
            # Simplified merge (just append for test)
            final_merged.append(item)
            
    # Geocoding Pass
    print(f"Geocoding pass for {len(final_merged)} items...")
    geocoder = GeocodeHelper()
    geocoded_count = 0
    # Test geocoding on KNPS only to save time/quota
    for item in final_merged:
        if item.get('source') == 'KNPS' and (item.get('lat') == 0 or not item.get('lat')):
            query = f"국립공원 {item['name']}"
            coords = geocoder.geocode(query)
            if coords:
                item['lat'], item['lng'] = coords[0], coords[1]
                geocoded_count += 1
                print(f"  [Geocoded] {item['name']} -> {coords}")
                if geocoded_count >= 3: break # Limit for test

    print(f"Test Complete. Total items: {len(final_merged)}. Geocoded: {geocoded_count}")
    
    # Preview a few items
    if final_merged:
        print("\nSample Output:")
        print(json.dumps(final_merged[0], indent=2, ensure_ascii=False))
        # Find a geocoded one
        for item in final_merged:
            if item.get('source') == 'KNPS' and item.get('lat') != 0:
                print("\nGeocoded Sample:")
                print(json.dumps(item, indent=2, ensure_ascii=False))
                break

if __name__ == "__main__":
    test_integration()
