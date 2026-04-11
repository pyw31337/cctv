import json
import requests
import concurrent.futures
import random
import time
from collections import Counter
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_stream(item):
    name = item.get('name', 'Unknown')
    url = item.get('url', '')
    source = item.get('source', 'Unknown')
    
    if not url:
        return source, False
    
    try:
        # Check for M3U8 or MP4 reachability
        # Use stream=True to avoid downloading the whole body
        resp = requests.get(url, timeout=5, verify=False, stream=True)
        if resp.status_code == 200:
            return source, True
        else:
            return source, False
    except Exception:
        return source, False

def run_audit(sample_size=1000):
    print(f"Loading CCTV data...")
    with open('cctv_data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_count = len(data)
    print(f"Total CCTVs: {total_count}")
    
    if sample_size > total_count:
        sample_size = total_count
        
    sample = random.sample(data, sample_size)
    print(f"Starting audit for {sample_size} random samples...")
    
    results = []
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
        future_to_item = {executor.submit(check_stream, item): item for item in sample}
        for future in concurrent.futures.as_completed(future_to_item):
            results.append(future.result())
            if len(results) % 100 == 0:
                print(f"Checked {len(results)}/ {sample_size}...")

    end_time = time.time()
    duration = end_time - start_time
    
    # Analyze results
    source_stats = {} # {source: [success, total]}
    for source, success in results:
        if source not in source_stats:
            source_stats[source] = [0, 0]
        source_stats[source][1] += 1
        if success:
            source_stats[source][0] += 1
            
    print("\n" + "="*50)
    print(f"Audit Summary (Sample Size: {sample_size})")
    print(f"Duration: {duration:.2f} seconds")
    print("="*50)
    print(f"{'Source':<15} | {'Total':<6} | {'Success':<7} | {'Rate':<6}")
    print("-" * 50)
    
    total_success = 0
    for source, (success, total) in sorted(source_stats.items(), key=lambda x: x[1][1], reverse=True):
        rate = (success / total) * 100
        total_success += success
        print(f"{source:<15} | {total:<6} | {success:<7} | {rate:>5.1f}%")
        
    overall_rate = (total_success / sample_size) * 100
    print("-" * 50)
    print(f"{'OVERALL':<15} | {sample_size:<6} | {total_success:<7} | {overall_rate:>5.1f}%")
    print("="*50)

if __name__ == "__main__":
    import sys
    size = 1000
    if len(sys.argv) > 1:
        size = int(sys.argv[1])
    run_audit(size)
