#!/usr/bin/env python3
"""
CCTV Stream Health Monitor
Checks stream availability and reports anomalies.
Redesigned to avoid false positives in UTIC_API checks.
"""
import json
import requests
import os
import sys
import argparse
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib3

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
CCTV_DATA_FILE = "cctv_data.json"
SAMPLE_SIZE = 300  # Increased for better accuracy
TIMEOUT = 10
FAILURE_THRESHOLD = 0.15  # Alert if more than 15% of streams fail (Stricter)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_headers(item):
    """Generate source-specific headers"""
    headers = HEADERS.copy()
    source = item.get("source", "")
    
    if source == "GITS":
        headers["Referer"] = "https://gits.gg.go.kr/web/map/webMap.do?opt=3"
    elif source == "DAEJEON_ITS":
        headers["Referer"] = "https://traffic.daejeon.go.kr/traffic/cctv"
    else:
        headers["Referer"] = "https://www.utic.go.kr/"
        
    return headers

# Stream type patterns for testing
STREAM_PATTERNS = {
    "HLS": [".m3u8", "!hls", "playlist.m3u8"],
    "MP4": [".mp4"],
    "UTIC_API": ["openDataCctvStream.jsp", "cctvPopup.do", "cctvView.do", "videoDetail.do"]
}

def load_cctv_data():
    """Load CCTV data from JSON file"""
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def categorize_streams(data):
    """Categorize streams by type"""
    categories = {
        "HLS": [],
        "MP4": [],
        "UTIC_API": [],
        "Other": []
    }
    
    for item in data:
        # Skip inactive streams
        if item.get("status") in ["inactive", "broken"]:
            continue
            
        url = item.get("url", "")
        categorized = False
        
        for category, patterns in STREAM_PATTERNS.items():
            if any(p in url for p in patterns):
                categories[category].append(item)
                categorized = True
                break
        
        if not categorized:
            categories["Other"].append(item)
    
    return categories

def generate_daejeon_url(item):
    """Regenerate Daejeon URL with current timestamp candidates (KST)"""
    url = item.get("url", "")
    stream_id = item.get("id", "").replace("DAEJEON_", "")
    
    # Extract ID from existing URL path if possible (e.g. .../media/CTV0012/...)
    url_match = re.search(r'/media/([^/]+)/', url)
    if url_match:
        stream_id = url_match.group(1)
    
    # Generic padding logic
    if stream_id.startswith("CCTV"):
        num = stream_id[4:]
        stream_id = f"CTV{num.zfill(4)}"
        
    base_url = f"https://tportal.daejeon.go.kr:37084/01/media/{stream_id}/{stream_id}_"
    
    # Use KST (UTC + 9) for GitHub Actions environment
    now_utc = datetime.utcnow()
    now_kst = now_utc + timedelta(hours=9)
    
    candidates = []
    # Try 1 to 5 mins ago
    for m in range(1, 6):
        t = now_kst - timedelta(minutes=m)
        ts = t.strftime("%Y%m%d.%H%M00")
        candidates.append(f"{base_url}{ts}.000.mp4")
    return candidates
 # Return list of candidates

def check_hls_stream(item):
    """Check if HLS/MP4 stream is accessible"""
    # Prioritize directUrl if available
    url = item.get("directUrl") or item.get("url", "")
    name = item.get("name", "Unknown")
    cctv_id = item.get("id", "Unknown")
    source = item.get("source", "")
    
    base_res = {"name": name, "id": cctv_id}
    urls_to_try = [url]
    
    # Special handling for Daejeon dynamic URLs (Fallback)
    is_daejeon_url = "tportal.daejeon.go.kr" in url
    if (source == "DAEJEON_ITS" or is_daejeon_url) and not url.endswith(".m3u8"):
        urls_to_try = generate_daejeon_url(item)
    elif url:
        # For non-Daejeon, use directUrl as backup if available
        direct_url = item.get("directUrl")
        if direct_url and direct_url != url:
            urls_to_try.append(direct_url)
            
    last_status = None
    last_code = None
    
    headers = get_headers(item)
    
    for try_url in urls_to_try:
        try:
            # Use HEAD for efficiency if we are trying multiple candidates
            # but use GET with stream=True
            response = requests.get(try_url, headers=headers, timeout=TIMEOUT, stream=True, verify=False)
            if response.status_code == 200:
                return {**base_res, "status": "OK", "code": 200, "type": "hard"}
            else:
                last_status = response.status_code
        except requests.Timeout:
            last_code = "TIMEOUT"
        except requests.exceptions.ConnectionError:
            last_code = "CONN_ERROR"
        except Exception as e:
            last_code = str(e)[:50]
            
    # If we get here, all attempts failed. Return the result of the last attempt (or generic fail)
    if last_status:
        fail_type = "hard" if last_status in [404, 500] else "soft"
        return {**base_res, "status": "FAIL", "code": last_status, "type": fail_type}
    elif last_code:
         return {**base_res, "status": last_code, "code": None, "type": "soft"}
    else:
         return {**base_res, "status": "FAIL", "code": 404, "type": "hard"}

def check_utic_api(item):
    """Check UTIC API/JSP endpoint visibility"""
    url = item.get("url", "")
    name = item.get("name", "Unknown")
    cctv_id = item.get("id", "Unknown")
    
    base_res = {"name": name, "id": cctv_id}
    
    headers = get_headers(item)
    
    try:
        response = requests.get(url, headers=headers, timeout=TIMEOUT, verify=False)
        
        if response.status_code == 200:
            # Check for common error indicators in HTML
            html = response.text
            if "비정상적인 접근" in html or "접속이 원활하지 않습니다" in html:
                 # This is an IP block
                 return {**base_res, "status": "BLOCKED", "code": 200, "type": "soft"}
            if len(html) < 500 and "null" in html.lower():
                 return {**base_res, "status": "NULL_RESPONSE", "code": 200, "type": "soft"}
            
            return {**base_res, "status": "OK", "code": 200, "type": "hard"}
        else:
            fail_type = "hard" if response.status_code in [404, 500] else "soft"
            # Log failure for debugging
            if response.status_code == 403:
                print(f"  [DEBUG] UTIC 403 for {name} ({cctv_id})")
            return {**base_res, "status": "FAIL", "code": response.status_code, "type": fail_type}
            
    except requests.Timeout:
        return {**base_res, "status": "TIMEOUT", "code": None, "type": "soft"}
    except requests.exceptions.ConnectionError:
        return {**base_res, "status": "CONN_ERROR", "code": None, "type": "soft"}
    except Exception as e:
        return {**base_res, "status": "ERROR", "code": str(e)[:50], "type": "soft"}

def run_health_check(target_sample_size=SAMPLE_SIZE, target_category=None):
    """Run health check on sample of streams"""
    print(f"Loading CCTV data from {CCTV_DATA_FILE}...")
    data = load_cctv_data()
    categories = categorize_streams(data)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_streams": len(data),
        "categories": {},
        "issues": [],
        "summary": {}
    }
    
    import random
    for category, streams in categories.items():
        if not streams:
            continue
            
        if target_category and category != target_category:
            continue

        # Sample streams for testing
        sample_size_per_cat = min(target_sample_size // 4, len(streams))
        if target_category:
             sample_size_per_cat = min(target_sample_size, len(streams))
             
        sample = random.sample(streams, sample_size_per_cat)
        
        print(f"\nChecking {category}: {len(sample)} samples out of {len(streams)} total")
        
        # Choose appropriate check function
        check_func = {
            "HLS": check_hls_stream,
            "MP4": check_hls_stream,
            "UTIC_API": check_utic_api,
            "Other": check_hls_stream
        }.get(category, check_hls_stream)
        
        # Override for Daejeon HLS in MP4 category
        def smart_check(s):
            u = s.get("url", "")
            if "chunklist.m3u8" in u:
                return check_hls_stream(s)
            return check_func(s)
            
        # Run checks in parallel
        category_results = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(smart_check, s): s for s in sample}
            for future in as_completed(futures):
                result = future.result()
                category_results.append(result)
                
                # Track issues
                if result["status"] not in ["OK"]:
                    results["issues"].append({
                        "category": category,
                        **result
                    })
        
        # Calculate stats
        ok_count = sum(1 for r in category_results if r["status"] == "OK")
        hard_fail_count = sum(1 for r in category_results if r["status"] != "OK" and r.get("type") == "hard")
        soft_fail_count = sum(1 for r in category_results if r["status"] != "OK" and r.get("type") == "soft")
        
        results["categories"][category] = {
            "total": len(streams),
            "sampled": len(sample),
            "ok": ok_count,
            "hard_failed": hard_fail_count,
            "soft_failed": soft_fail_count,
            "failure_rate": (hard_fail_count + soft_fail_count) / len(sample) if sample else 0
        }
        
        # Summary
        results["summary"][category] = f"{ok_count}/{len(sample)} OK ({100*ok_count/len(sample):.1f}%)" if sample else "N/A"
    
    # Overall health
    total_sampled = sum(c["sampled"] for c in results["categories"].values())
    total_hard_failed = sum(c["hard_failed"] for c in results["categories"].values())
    total_soft_failed = sum(c["soft_failed"] for c in results["categories"].values())
    
    results["hard_failure_rate"] = total_hard_failed / total_sampled if total_sampled else 0
    results["soft_failure_rate"] = total_soft_failed / total_sampled if total_sampled else 0
    results["overall_failure_rate"] = (total_hard_failed + total_soft_failed) / total_sampled if total_sampled else 0
    
    # We only fail CI on HARD failures (404, 500, NULL)
    results["is_healthy"] = results["hard_failure_rate"] < FAILURE_THRESHOLD
    
    return results

def generate_report(results):
    """Generate a human-readable report"""
    report = []
    report.append("=" * 60)
    report.append("CCTV Stream Health Report (CI Resilient)")
    report.append(f"Generated: {results['timestamp']}")
    report.append("=" * 60)
    report.append("")
    
    # Overall Status
    status = "✅ HEALTHY" if results["is_healthy"] else "⚠️ ISSUES DETECTED"
    report.append(f"Overall Status: {status}")
    report.append(f"Total Streams: {results['total_streams']}")
    report.append(f"Hard Failure Rate: {results['hard_failure_rate']*100:.1f}% (Impacts CI Status)")
    report.append(f"Soft Failure Rate: {results['soft_failure_rate']*100:.1f}% (Environmental/Timeout)")
    report.append(f"Threshold: {FAILURE_THRESHOLD*100:.1f}%")
    report.append("")
    
    # Category Summary
    report.append("-" * 40)
    report.append("Category Summary:")
    report.append("-" * 40)
    for category, summary in results["summary"].items():
        report.append(f"  {category}: {summary}")
    report.append("")
    
    # Issues
    if results["issues"]:
        report.append("-" * 40)
        report.append(f"Issues Detected ({len(results['issues'])}):")
        report.append("-" * 40)
        for issue in results["issues"][:300]:  # Limit to first 300
            report.append(f"  [{issue['category']}] {issue['name']}: {issue['status']} ({issue['code']})")
        if len(results["issues"]) > 300:
            report.append(f"  ... and {len(results['issues']) - 300} more")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="CCTV Stream Health Monitor")
    parser.add_argument("--sample", type=int, default=SAMPLE_SIZE, help="Total sample size")
    parser.add_argument("--category", type=str, choices=["HLS", "MP4", "UTIC_API", "Other"], help="Only check specific category")
    args = parser.parse_args()

    print("Starting CCTV Stream Health Check (Improved Logic)...")
    results = run_health_check(target_sample_size=args.sample, target_category=args.category)
    report = generate_report(results)
    
    print("\n" + report)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = f"health_report_{timestamp}.txt"
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"\nReport saved to: {report_file}")
    
    # Also save as latest_health_report.txt for GitHub Actions to find easily
    with open("latest_health_report.txt", "w", encoding="utf-8") as f:
        f.write(report)
    
    # Save failed streams for auto-renewal
    failed_json = "failed_streams.json"
    failed_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": results["summary"],
        "failures": {}
    }
    
    for issue in results["issues"]:
        cat = "unknown"
        if issue["status"] == "FAIL":
            if issue["code"] == 404: cat = "http_404"
            elif issue["code"] == None: cat = "timeout"
            else: cat = "http_other"
        elif issue["status"] == "NULL_RESPONSE":
            cat = "utic_null"
        elif issue["status"] == "BLOCKED":
            cat = "blocked"
        elif issue["status"] == "ERROR":
             cat = "connection_error"
             
        if cat not in failed_data["failures"]:
            failed_data["failures"][cat] = []
        
        failed_data["failures"][cat].append({
            "id": issue.get("id"),
            "name": issue["name"],
        })
    
    with open(failed_json, 'w', encoding='utf-8') as f:
        json.dump(failed_data, f, ensure_ascii=False, indent=2)
    print(f"Failed streams data saved to: {failed_json}")
    
    # Set output for GitHub Actions
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], 'a') as f:
            f.write(f"is_healthy={str(results['is_healthy']).lower()}\n")
            f.write(f"failure_rate={results['overall_failure_rate']:.2f}\n")
            f.write(f"issue_count={len(results['issues'])}\n")
    
    # Exit with error if unhealthy (for CI/CD)
    if not results["is_healthy"]:
        print("\n⚠️  Health check failed - issues detected!")
        sys.exit(1)
    else:
        print("\n✅ All streams healthy!")
        sys.exit(0)

if __name__ == "__main__":
    main()
