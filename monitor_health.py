#!/usr/bin/env python3
"""
CCTV Stream Health Monitor
Checks stream availability and reports anomalies via email.
"""
import json
import requests
import os
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
CCTV_DATA_FILE = "cctv_data.json"
SAMPLE_SIZE = 100  # Check a sample of streams to avoid rate limiting
TIMEOUT = 10
FAILURE_THRESHOLD = 0.30  # Alert if more than 30% of streams fail (HLS-focused)

# Note: MP4 streams are date-based and may 404 during off-hours
# UTIC_API may show null during maintenance windows

# Stream type patterns for testing
STREAM_PATTERNS = {
    "HLS": [".m3u8"],
    "MP4": [".mp4"],
    "UTIC_API": ["openDataCctvStream.jsp"]
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

def check_hls_stream(item):
    """Check if HLS stream is accessible"""
    url = item.get("url", "")
    name = item.get("name", "Unknown")
    
    try:
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code == 200:
            return {"name": name, "status": "OK", "code": 200}
        else:
            return {"name": name, "status": "FAIL", "code": response.status_code}
    except requests.Timeout:
        return {"name": name, "status": "TIMEOUT", "code": None}
    except Exception as e:
        return {"name": name, "status": "ERROR", "code": str(e)[:50]}

def check_mp4_stream(item):
    """Check if MP4 stream is accessible"""
    return check_hls_stream(item)  # Same logic

def check_utic_api(item):
    """Check UTIC API endpoint"""
    url = item.get("url", "")
    name = item.get("name", "Unknown")
    
    try:
        # Extract cctvip from URL
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        cctvip = params.get("cctvip", [""])[0]
        kind = params.get("kind", [""])[0]
        
        if kind == "Z3" and cctvip:
            # Test the API endpoint
            api_url = f"https://www.utic.go.kr/map/getGyeonggiCctvUrlFromIts.do?cctvIp={cctvip}"
            response = requests.get(api_url, timeout=TIMEOUT)
            
            if response.status_code == 200:
                if response.text.strip() == "null":
                    return {"name": name, "status": "NULL_RESPONSE", "code": 200}
                else:
                    return {"name": name, "status": "OK", "code": 200}
            else:
                return {"name": name, "status": "FAIL", "code": response.status_code}
        else:
            # Just check if the page loads
            response = requests.get(url, timeout=TIMEOUT)
            return {"name": name, "status": "OK" if response.status_code == 200 else "FAIL", "code": response.status_code}
            
    except requests.Timeout:
        return {"name": name, "status": "TIMEOUT", "code": None}
    except Exception as e:
        return {"name": name, "status": "ERROR", "code": str(e)[:50]}

def run_health_check():
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
    
    for category, streams in categories.items():
        if not streams:
            continue
            
        # Sample streams for testing
        import random
        sample = random.sample(streams, min(SAMPLE_SIZE // 4, len(streams)))
        
        print(f"\nChecking {category}: {len(sample)} samples out of {len(streams)} total")
        
        # Choose appropriate check function
        check_func = {
            "HLS": check_hls_stream,
            "MP4": check_mp4_stream,
            "UTIC_API": check_utic_api,
            "Other": check_hls_stream
        }.get(category, check_hls_stream)
        
        # Run checks in parallel
        category_results = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(check_func, s): s for s in sample}
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
        fail_count = len(category_results) - ok_count
        
        results["categories"][category] = {
            "total": len(streams),
            "sampled": len(sample),
            "ok": ok_count,
            "failed": fail_count,
            "failure_rate": fail_count / len(sample) if sample else 0
        }
        
        # Summary
        results["summary"][category] = f"{ok_count}/{len(sample)} OK ({100*ok_count/len(sample):.1f}%)" if sample else "N/A"
    
    # Overall health
    total_sampled = sum(c["sampled"] for c in results["categories"].values())
    total_failed = sum(c["failed"] for c in results["categories"].values())
    results["overall_failure_rate"] = total_failed / total_sampled if total_sampled else 0
    results["is_healthy"] = results["overall_failure_rate"] < FAILURE_THRESHOLD
    
    return results

def generate_report(results):
    """Generate a human-readable report"""
    report = []
    report.append("=" * 60)
    report.append("CCTV Stream Health Report")
    report.append(f"Generated: {results['timestamp']}")
    report.append("=" * 60)
    report.append("")
    
    # Overall Status
    status = "✅ HEALTHY" if results["is_healthy"] else "⚠️ ISSUES DETECTED"
    report.append(f"Overall Status: {status}")
    report.append(f"Total Streams: {results['total_streams']}")
    report.append(f"Failure Rate: {results['overall_failure_rate']*100:.1f}%")
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
        for issue in results["issues"][:20]:  # Limit to first 20
            report.append(f"  [{issue['category']}] {issue['name']}: {issue['status']} ({issue['code']})")
        if len(results["issues"]) > 20:
            report.append(f"  ... and {len(results['issues']) - 20} more")
    
    report.append("")
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """Main entry point"""
    print("Starting CCTV Stream Health Check...")
    results = run_health_check()
    report = generate_report(results)
    
    print("\n" + report)
    
    # Save report
    report_file = f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {report_file}")
    
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
