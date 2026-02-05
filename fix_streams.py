#!/usr/bin/env python3
"""
Stream URL Fix Script
Automatically fixes known issues in cctv_data.json:
1. Daejeon MP4 - Date-based URLs need dynamic date
2. SSL issues - Mark as requiring SSL verification skip
3. Unknown 404 - Mark as inactive for re-scraping
"""
import json
import re
from datetime import datetime, timedelta

CCTV_DATA_FILE = "cctv_data.json"
FAILED_STREAMS_FILE = "failed_streams.json"

def load_data():
    with open(CCTV_DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_failures():
    with open(FAILED_STREAMS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def fix_daejeon_mp4_urls(data):
    """
    Daejeon MP4 URLs contain a date in the path.
    We can't fix this in static JSON - we need to generate URLs dynamically.
    Mark these streams with metadata for frontend to handle.
    """
    fixed_count = 0
    daejeon_pattern = r"tportal\.daejeon\.go\.kr.*/(\d+_\d+)/media/"
    
    for item in data:
        url = item.get("url", "")
        if "tportal.daejeon" in url and ".mp4" in url:
            # These URLs are date-based and can't be fixed statically
            # Mark them with special metadata
            if "urlPattern" not in item:
                # Extract the pattern and mark it
                # Example: /02/media/CTV0015/CTV0015_20260205.140000.000.mp4
                # Should be: /02/media/CTV0015/CTV0015_{DATE}.{TIME}.000.mp4
                item["urlType"] = "daejeon_mp4_dynamic"
                item["note"] = "This URL requires dynamic date. Use fetchDaejeonStream() in frontend."
                fixed_count += 1
    
    return fixed_count

def mark_ssl_issues(data, failures):
    """Mark streams with SSL issues for special handling"""
    ssl_failures = failures.get("failures", {}).get("ssl_error", [])
    ssl_ids = {f["id"] for f in ssl_failures}
    
    fixed_count = 0
    for item in data:
        if item.get("id") in ssl_ids:
            item["sslIssue"] = True
            item["note"] = "SSL certificate verification may fail. Requires proxy or skip SSL."
            fixed_count += 1
    
    return fixed_count

def mark_inactive_streams(data, failures):
    """Mark 404 streams as inactive"""
    http_404 = failures.get("failures", {}).get("http_404", [])
    
    # Group by domain to identify patterns
    from collections import defaultdict
    by_domain = defaultdict(list)
    
    for f in http_404:
        url = f.get("full_url", "")
        if "tportal.daejeon" in url:
            continue  # Skip Daejeon - handled separately
        
        # These are genuinely dead URLs
        by_domain[f.get("cause", "Unknown")].append(f["id"])
    
    marked_count = 0
    all_dead_ids = set()
    for cause, ids in by_domain.items():
        all_dead_ids.update(ids)
    
    for item in data:
        if item.get("id") in all_dead_ids:
            item["status"] = "inactive"
            item["lastChecked"] = datetime.now().isoformat()
            marked_count += 1
    
    return marked_count

def generate_summary(data):
    """Generate a summary of the current dataset"""
    total = len(data)
    active = sum(1 for d in data if d.get("status") != "inactive")
    inactive = total - active
    
    with_ssl_issue = sum(1 for d in data if d.get("sslIssue"))
    daejeon_dynamic = sum(1 for d in data if d.get("urlType") == "daejeon_mp4_dynamic")
    
    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "ssl_issues": with_ssl_issue,
        "daejeon_dynamic": daejeon_dynamic
    }

def main():
    print("Loading data...")
    data = load_data()
    failures = load_failures()
    
    print(f"Loaded {len(data)} streams")
    print(f"Failures to process: {failures['summary']['failed']}")
    print()
    
    print("Applying fixes...")
    
    # Fix 1: Mark Daejeon MP4 streams
    daejeon_fixed = fix_daejeon_mp4_urls(data)
    print(f"  ✅ Marked {daejeon_fixed} Daejeon dynamic MP4 streams")
    
    # Fix 2: Mark SSL issue streams
    ssl_fixed = mark_ssl_issues(data, failures)
    print(f"  ✅ Marked {ssl_fixed} streams with SSL issues")
    
    # Fix 3: Mark inactive streams (404s that aren't Daejeon)
    inactive_marked = mark_inactive_streams(data, failures)
    print(f"  ⚠️ Marked {inactive_marked} streams as inactive (404)")
    
    # Save updated data
    print()
    print("Saving updated cctv_data.json...")
    with open(CCTV_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Print summary
    summary = generate_summary(data)
    print()
    print("=" * 50)
    print("UPDATED DATASET SUMMARY:")
    print("=" * 50)
    print(f"  Total streams: {summary['total']}")
    print(f"  Active: {summary['active']}")
    print(f"  Inactive: {summary['inactive']}")
    print(f"  SSL Issue (needs proxy): {summary['ssl_issues']}")
    print(f"  Daejeon Dynamic URL: {summary['daejeon_dynamic']}")
    print("=" * 50)
    
    # Save fix report
    report = {
        "timestamp": datetime.now().isoformat(),
        "fixes_applied": {
            "daejeon_dynamic_marked": daejeon_fixed,
            "ssl_issues_marked": ssl_fixed,
            "inactive_marked": inactive_marked
        },
        "summary": summary
    }
    
    with open("fix_report.json", 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\nFix report saved to: fix_report.json")

if __name__ == "__main__":
    main()
