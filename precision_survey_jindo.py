import json
import requests
import re
import time
import xml.etree.ElementTree as ET
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = "cctv_data.json"
OUTPUT_REPORT_MD = "jindo_survey_report.md"
OUTPUT_REPORT_JSON = "jindo_survey_results.json"
UTIC_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

GARBAGE_IPS = [".73606", ".50247"]

def log(msg):
    print(f"[*] {msg}")

def fetch_master_list():
    log("Fetching UTIC Master List...")
    url = f"http://www.utic.go.kr/guide/cctvOpenData.do?key={UTIC_KEY}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        if resp.status_code == 200:
            return resp.content
    except Exception as e:
        log(f"Error fetching master list: {e}")
    return None

def parse_jindo_candidates(xml_content):
    log("Parsing Jindo candidates from Master List...")
    candidates = []
    try:
        root = ET.fromstring(xml_content)
        for record in root.findall("record"):
            name = record.find("cctvname").text or ""
            cid = record.find("cctvid").text or ""
            if "진도" in name and "당진" not in name:
                candidates.append({
                    "id": cid,
                    "name": name,
                    "source": "UTIC_MASTER"
                })
    except Exception as e:
        log(f"Error parsing XML: {e}")
    return candidates

def get_existing_jindo():
    log("Loading existing Jindo items from cctv_data.json...")
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        return [item for item in data if "진도" in item.get("name", "") and "당진" not in item.get("name", "")]
    except Exception as e:
        log(f"Error loading existing data: {e}")
    return []

def validate_stream(cid, name):
    url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={UTIC_KEY}&cctvid={cid}"
    result = {
        "id": cid,
        "name": name,
        "status": "UNKNOWN",
        "ip": "N/A",
        "reason": ""
    }
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if resp.status_code != 200:
            result["status"] = "FAIL"
            result["reason"] = f"HTTP {resp.status_code}"
            return result
        
        if "비정상적인 접근" in resp.text:
            result["status"] = "BLOCKED"
            result["reason"] = "Anti-crawling triggered"
            return result
        
        # Parse ConnectSrv
        match = re.search(r"ConnectSrv\('[^']+', '[^']+', '([^']+)'", resp.text)
        if match:
            ip = match.group(1)
            result["ip"] = ip
            if any(g in ip for g in GARBAGE_IPS):
                result["status"] = "GARBAGE"
                result["reason"] = f"Bad IP detected ({ip})"
            else:
                result["status"] = "OK"
                result["reason"] = f"Valid IP ({ip})"
        else:
            result["status"] = "NO_STREAM"
            result["reason"] = "ConnectSrv not found"
            
    except Exception as e:
        result["status"] = "ERROR"
        result["reason"] = str(e)
        
    return result

def main():
    start_time = time.time()
    
    # 1. Gather all candidates
    existing = get_existing_jindo()
    log(f"Found {len(existing)} existing Jindo items.")
    
    master_xml = fetch_master_list()
    master_candidates = []
    if master_xml:
        master_candidates = parse_jindo_candidates(master_xml)
        log(f"Found {len(master_candidates)} Jindo items in Master List.")
    
    # Deduplicate by ID
    all_candidates = {item["id"]: item["name"] for item in existing}
    for item in master_candidates:
        all_candidates[item["id"]] = item["name"]
        
    # Also add the suspected range E901100 - E901199 if not present
    for i in range(1100, 1200):
        cid = f"E90{i}"
        if cid not in all_candidates:
            all_candidates[cid] = f"SCAN_{cid}"
            
    log(f"Total unique candidates to survey: {len(all_candidates)}")
    
    # 2. Survey
    results = []
    count = 0
    total = len(all_candidates)
    
    for cid, name in sorted(all_candidates.items()):
        count += 1
        log(f"[{count}/{total}] Surveying {cid} ({name})...")
        res = validate_stream(cid, name)
        results.append(res)
        log(f"   -> {res['status']} ({res['reason']})")
        
        # Throttling
        time.sleep(0.5)
        
    # 3. Save Results
    with open(OUTPUT_REPORT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    
    # Generate MD Report
    with open(OUTPUT_REPORT_MD, "w") as f:
        f.write("# Jindo CCTV Precision Survey Report\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Candidates: {total}\n\n")
        
        f.write("## Summary\n")
        ok_count = len([r for r in results if r["status"] == "OK"])
        garbage_count = len([r for r in results if r["status"] == "GARBAGE"])
        blocked_count = len([r for r in results if r["status"] == "BLOCKED"])
        fail_count = len([r for r in results if r["status"] in ["FAIL", "ERROR", "NO_STREAM"]])
        
        f.write(f"- ✅ OK: {ok_count}\n")
        f.write(f"- 🚮 GARBAGE: {garbage_count}\n")
        f.write(f"- 🚫 BLOCKED: {blocked_count}\n")
        f.write(f"- ❌ FAILED/EMPTY: {fail_count}\n\n")
        
        f.write("## Detailed Results (OK Only)\n\n")
        f.write("| ID | Name | IP | Reason |\n")
        f.write("|---|---|---|---|\n")
        for r in sorted([r for r in results if r["status"] == "OK"], key=lambda x: x["id"]):
            f.write(f"| {r['id']} | {r['name']} | {r['ip']} | {r['reason']} |\n")
            
        f.write("\n## Garbage/Blocked Results\n\n")
        f.write("| ID | Name | IP | Status | Reason |\n")
        f.write("|---|---|---|---|---|\n")
        for r in sorted([r for r in results if r["status"] in ["GARBAGE", "BLOCKED"]], key=lambda x: x["id"]):
            f.write(f"| {r['id']} | {r['name']} | {r['ip']} | {r['status']} | {r['reason']} |\n")

    log(f"Survey completed in {time.time() - start_time:.1f}s")
    log(f"Report saved to {OUTPUT_REPORT_MD} and {OUTPUT_REPORT_JSON}")

if __name__ == "__main__":
    main()
