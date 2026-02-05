#!/usr/bin/env python3
"""
Comprehensive Stream Diagnostic Tool
Checks ALL secured streams, identifies failures, analyzes root causes,
and suggests/applies fixes automatically.
"""
import json
import requests
import os
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

CCTV_DATA_FILE = "cctv_data.json"
TIMEOUT = 10
MAX_WORKERS = 20

# Result categories
RESULTS = {
    "ok": [],
    "http_404": [],
    "http_other": [],
    "timeout": [],
    "utic_null": [],
    "connection_error": [],
    "ssl_error": [],
    "unknown": []
}

def load_secured_streams():
    """Load only secured streams (HLS/MP4)"""
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    secured = []
    for item in data:
        url = item.get("url", "")
        if ".m3u8" in url or ".mp4" in url:
            secured.append(item)
    
    return secured

def check_stream(item):
    """Check a single stream and categorize the result"""
    url = item.get("url", "")
    name = item.get("name", "Unknown")
    stream_id = item.get("id", "")
    
    result = {
        "id": stream_id,
        "name": name,
        "url": url[:80] + "..." if len(url) > 80 else url,
        "full_url": url
    }
    
    try:
        # For HLS, just check if the m3u8 is accessible
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        
        if response.status_code == 200:
            result["status"] = "OK"
            result["code"] = 200
            return ("ok", result)
        elif response.status_code == 404:
            result["status"] = "NOT_FOUND"
            result["code"] = 404
            # Try to identify why
            if "ktict.co.kr" in url:
                result["cause"] = "Seoul TOPIS - URL expired (token-based)"
                result["fix"] = "Re-scrape Seoul streams"
            elif "tportal.daejeon" in url:
                result["cause"] = "Daejeon MP4 - Date-based URL wrong date"
                result["fix"] = "URL uses date template, may be temporarily unavailable"
            else:
                result["cause"] = "Unknown 404"
                result["fix"] = "Investigate manually"
            return ("http_404", result)
        elif response.status_code == 400:
            result["status"] = "BAD_REQUEST"
            result["code"] = 400
            result["cause"] = "URL format/token issue"
            result["fix"] = "Re-scrape to get fresh URL"
            return ("http_other", result)
        elif response.status_code == 403:
            result["status"] = "FORBIDDEN"
            result["code"] = 403
            result["cause"] = "Access denied - possible IP block or auth required"
            result["fix"] = "Check if rate limited or IP blocked"
            return ("http_other", result)
        else:
            result["status"] = f"HTTP_{response.status_code}"
            result["code"] = response.status_code
            result["cause"] = f"Unexpected HTTP {response.status_code}"
            return ("http_other", result)
            
    except requests.Timeout:
        result["status"] = "TIMEOUT"
        result["cause"] = "Server not responding within 10s"
        result["fix"] = "Server may be overloaded or down"
        return ("timeout", result)
    except requests.exceptions.SSLError as e:
        result["status"] = "SSL_ERROR"
        result["cause"] = str(e)[:100]
        result["fix"] = "SSL certificate issue"
        return ("ssl_error", result)
    except requests.exceptions.ConnectionError as e:
        result["status"] = "CONNECTION_ERROR"
        result["cause"] = str(e)[:100]
        result["fix"] = "Server unreachable"
        return ("connection_error", result)
    except Exception as e:
        result["status"] = "UNKNOWN_ERROR"
        result["cause"] = str(e)[:100]
        return ("unknown", result)

def analyze_failures(results):
    """Analyze failure patterns and suggest fixes"""
    analysis = {
        "by_domain": defaultdict(list),
        "by_cause": defaultdict(list),
        "auto_fixable": [],
        "manual_required": []
    }
    
    for category, items in results.items():
        if category == "ok":
            continue
        for item in items:
            # Group by domain
            try:
                domain = urlparse(item["full_url"]).netloc
                analysis["by_domain"][domain].append(item)
            except:
                pass
            
            # Group by cause
            cause = item.get("cause", "Unknown")
            analysis["by_cause"][cause].append(item)
            
            # Determine if auto-fixable
            if "Re-scrape" in item.get("fix", ""):
                analysis["auto_fixable"].append(item)
            else:
                analysis["manual_required"].append(item)
    
    return analysis

def generate_detailed_report(results, analysis):
    """Generate a detailed diagnostic report"""
    report = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    report.append("=" * 70)
    report.append("CCTV Stream Comprehensive Diagnostic Report")
    report.append(f"Generated: {now}")
    report.append("=" * 70)
    
    # Summary
    total = sum(len(v) for v in results.values())
    ok_count = len(results["ok"])
    failed_count = total - ok_count
    
    report.append("")
    report.append(f"Total Secured Streams Checked: {total}")
    report.append(f"✅ Working: {ok_count} ({100*ok_count/total:.1f}%)")
    report.append(f"❌ Failed: {failed_count} ({100*failed_count/total:.1f}%)")
    report.append("")
    
    # Failure breakdown
    report.append("-" * 50)
    report.append("Failure Breakdown:")
    report.append("-" * 50)
    for category, items in results.items():
        if category != "ok" and items:
            report.append(f"  {category}: {len(items)}")
    report.append("")
    
    # By domain
    if analysis["by_domain"]:
        report.append("-" * 50)
        report.append("Failures by Domain:")
        report.append("-" * 50)
        for domain, items in sorted(analysis["by_domain"].items(), key=lambda x: -len(x[1])):
            report.append(f"  {domain}: {len(items)} failures")
        report.append("")
    
    # By cause
    if analysis["by_cause"]:
        report.append("-" * 50)
        report.append("Failures by Root Cause:")
        report.append("-" * 50)
        for cause, items in sorted(analysis["by_cause"].items(), key=lambda x: -len(x[1])):
            report.append(f"  [{len(items)}] {cause}")
        report.append("")
    
    # Detailed failure list
    report.append("-" * 50)
    report.append("All Failed Streams:")
    report.append("-" * 50)
    for category, items in results.items():
        if category != "ok" and items:
            for item in items:
                report.append(f"  [{item.get('status', 'UNKNOWN')}] {item['name']}")
                report.append(f"    ID: {item['id']}")
                report.append(f"    Cause: {item.get('cause', 'Unknown')}")
                report.append(f"    Fix: {item.get('fix', 'N/A')}")
                report.append("")
    
    # Recommendations
    report.append("=" * 70)
    report.append("RECOMMENDATIONS:")
    report.append("=" * 70)
    
    if analysis["auto_fixable"]:
        report.append(f"  🔧 Auto-fixable: {len(analysis['auto_fixable'])} streams")
        report.append("     Action: Re-run scraper to refresh expired URLs")
    
    if analysis["manual_required"]:
        report.append(f"  ⚠️ Manual review: {len(analysis['manual_required'])} streams")
    
    report.append("")
    report.append("=" * 70)
    
    return "\n".join(report)

def main():
    print("Loading secured streams...")
    streams = load_secured_streams()
    print(f"Found {len(streams)} secured streams (HLS/MP4)")
    
    print(f"\nChecking all streams with {MAX_WORKERS} parallel workers...")
    
    global RESULTS
    checked = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_stream, s): s for s in streams}
        
        for future in as_completed(futures):
            category, result = future.result()
            RESULTS[category].append(result)
            checked += 1
            
            if checked % 100 == 0:
                ok = len(RESULTS["ok"])
                print(f"  Progress: {checked}/{len(streams)} ({100*checked/len(streams):.1f}%) - {ok} OK so far")
    
    print(f"\nCheck complete. Analyzing results...")
    analysis = analyze_failures(RESULTS)
    
    report = generate_detailed_report(RESULTS, analysis)
    print("\n" + report)
    
    # Save report
    report_file = f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {report_file}")
    
    # Save failed streams JSON for programmatic use
    failed_json = "failed_streams.json"
    failed_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_checked": len(streams),
            "ok": len(RESULTS["ok"]),
            "failed": len(streams) - len(RESULTS["ok"])
        },
        "failures": {k: v for k, v in RESULTS.items() if k != "ok"}
    }
    with open(failed_json, 'w', encoding='utf-8') as f:
        json.dump(failed_data, f, ensure_ascii=False, indent=2)
    print(f"Failed streams data saved to: {failed_json}")
    
    return RESULTS, analysis

if __name__ == "__main__":
    main()
