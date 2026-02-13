import json
import random
import requests
import os
import time
from collections import defaultdict
import concurrent.futures

def get_region(item):
    """Extract Si/Gun/Gu from name or address."""
    name = item.get('name', '')
    address = item.get('address', '')
    
    # Try to find common region patterns
    # Examples: "인천광역시 미추홀구", "세종특별자치시", "강원도 강릉시"
    full_text = f"{address} {name}"
    
    # Simple regex-less extraction for speed
    parts = full_text.split()
    for part in parts:
        if part.endswith(('시', '군', '구')) and len(part) > 1:
            return part
            
    # Fallback to source-based grouping if possible
    source = item.get('source', '')
    if source == 'SEJONG': return '세종시'
    if source == 'JEJU': return '제주시' # Simplified
    if source == 'ULSAN': return '울산시'
    
    return "기타"

def test_url(url):
    """Test if a URL is responsive."""
    try:
        # HEAD request to check availability without downloading stream
        resp = requests.head(url, timeout=5, verify=False)
        if resp.status_code < 400:
            return True
        # Fallback to small GET for servers that block HEAD
        resp = requests.get(url, stream=True, timeout=5, verify=False)
        return resp.status_code < 400
    except:
        return False

def run_regional_test(filepath):
    if not os.path.exists(filepath):
        return
        
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Group by region
    regions = defaultdict(list)
    for item in data:
        regions[get_region(item)].append(item)
        
    report = []
    print(f"Testing {len(regions)} regions...")
    
    results = []
    def process_region(region_name):
        items = regions[region_name]
        sample_size = min(len(items), random.randint(1, 3))
        samples = random.sample(items, sample_size)
        
        region_results = []
        for sample in samples:
            success = test_url(sample['url'])
            region_results.append({
                'name': sample['name'],
                'url': sample['url'],
                'success': success
            })
        return (region_name, region_results)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process_region, regions.keys()))
        
    # Generate Report Table
    table = "| 지역 | 테스트 결과 | 성공률 |\n"
    table += "| :--- | :--- | :--- |\n"
    
    total_success = 0
    total_tests = 0
    
    for region, res in results:
        success_count = sum(1 for r in res if r['success'])
        rate = (success_count / len(res)) * 100
        total_success += success_count
        total_tests += len(res)
        
        status_icons = "".join(["✅" if r['success'] else "❌" for r in res])
        table += f"| {region} | {status_icons} | {rate:.1f}% |\n"
        
    summary = f"\n**전체 요약**: {total_success}/{total_tests} 성공 ({ (total_success/total_tests)*100:.1f}%)"
    
    final_report = table + summary
    print(final_report)
    
    with open("regional_test_report.md", "w", encoding="utf-8") as f:
        f.write("# CCTV 지역별 연결성 테스트 리포트\n\n")
        f.write(final_report)
        
    return final_report

if __name__ == "__main__":
    run_regional_test("cctv_data.json")
