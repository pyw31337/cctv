import json
import requests
import re
import time
import xml.etree.ElementTree as ET
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = "cctv_data.json"
OUTPUT_REPORT_MD = "jindo_final_survey_report.md"
OUTPUT_REPORT_JSON = "jindo_final_survey_results.json"
UTIC_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# Jindo Bounding Box (refined)
LAT_MIN, LAT_MAX = 34.2, 34.6
LNG_MIN, LNG_MAX = 126.0, 126.5

KEYWORDS = ["진도", "포산", "우수영", "군내교차로", "사교교차로", "진도대교", "진도터널"]

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

def find_candidates(xml_content):
    log("Finding candidates from Master List...")
    candidates = {}
    try:
        root = ET.fromstring(xml_content)
        for record in root.findall("record"):
            name = record.find("cctvname").text or ""
            cid = record.find("cctvid").text or ""
            
            # Check keywords
            match = any(k in name for k in KEYWORDS)
            
            # Check coordinates if present in XML (some UTIC lists have lat/lng)
            lat_node = record.find("cctvlatitude")
            lng_node = record.find("cctvlongitude")
            if lat_node is not None and lng_node is not None:
                try:
                    lat, lng = float(lat_node.text), float(lng_node.text)
                    if LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX:
                        match = True
                except: pass
            
            if match and "당진" not in name:
                candidates[cid] = name
    except Exception as e:
        log(f"Error parsing XML: {e}")
    return candidates

def get_data_candidates():
    log("Finding candidates from cctv_data.json...")
    candidates = {}
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
        for item in data:
            name = item.get("name", "")
            lat = item.get("lat", 0)
            lng = item.get("lng", 0)
            
            match = any(k in name for k in KEYWORDS)
            if LAT_MIN <= lat <= LAT_MAX and LNG_MIN <= lng <= LNG_MAX:
                match = True
                
            if match and "당진" not in name:
                candidates[item["id"]] = name
    except Exception as e:
        log(f"Error loading data: {e}")
    return candidates

def validate(cid, name):
    url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={UTIC_KEY}&cctvid={cid}"
    res = {"id": cid, "name": name, "status": "UNKNOWN", "ip": "N/A", "reason": ""}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if resp.status_code != 200:
            res["status"] = "FAIL"
            res["reason"] = f"HTTP {resp.status_code}"
            return res
        
        if "비정상적인 접근" in resp.text:
            res["status"] = "BLOCKED"; res["reason"] = "Anti-crawling"; return res
        
        if "준비중" in resp.text or "점검중" in resp.text:
            res["status"] = "MAINTENANCE"; res["reason"] = "Under maintenance"; return res

        match = re.search(r"ConnectSrv\('([^']+)',", resp.text)
        if match:
            ip = match.group(1)
            res["ip"] = ip
            if any(g in ip for g in GARBAGE_IPS):
                res["status"] = "GARBAGE"; res["reason"] = f"Bad IP ({ip})"
            else:
                res["status"] = "OK"; res["reason"] = f"Valid IP ({ip})"
        else:
            res["status"] = "NO_STREAM"; res["reason"] = "No ConnectSrv"
    except Exception as e:
        res["status"] = "ERROR"; res["reason"] = str(e)
    return res

def main():
    master_xml = fetch_master_list()
    candidates = find_candidates(master_xml) if master_xml else {}
    candidates.update(get_data_candidates())
    
    # Also scan neighbors of E901119 (Jindo Tunnel Entrance)
    # Range E901100 - E901150
    for i in range(1100, 1151):
        cid = f"E90{i}"
        if cid not in candidates:
            candidates[cid] = f"SCAN_{cid}"
            
    log(f"Total unique candidates to verify: {len(candidates)}")
    
    results = []
    for count, (cid, name) in enumerate(sorted(candidates.items()), 1):
        log(f"[{count}/{len(candidates)}] Checking {cid} ({name})...")
        res = validate(cid, name)
        results.append(res)
        log(f"   -> {res['status']} ({res['reason']})")
        time.sleep(0.4)
        
    with open(OUTPUT_REPORT_JSON, "w") as f:
        json.dump(results, f, indent=2)
        
    with open(OUTPUT_REPORT_MD, "w") as f:
        f.write("# Jindo Final Comprehensive Survey Report\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Functional Jindo Streams (OK Only)\n\n")
        f.write("| ID | Name | IP | Status |\n")
        f.write("|---|---|---|---|\n")
        for r in sorted([r for r in results if r["status"] == "OK"], key=lambda x: x["id"]):
            f.write(f"| {r['id']} | {r['name']} | {r['ip']} | {r['status']} |\n")
            
        f.write("\n## Maintenance/Failed Items (Crucial for Jindo Tunnel)\n\n")
        f.write("| ID | Name | Status | Reason |\n")
        f.write("|---|---|---|---|\n")
        for r in sorted([r for r in results if r["status"] != "OK"], key=lambda x: x["id"]):
            if any(k in r["name"] for k in ["진도", "터널"]):
                f.write(f"| {r['id']} | {r['name']} | {r['status']} | {r['reason']} |\n")

    log(f"Final Survey completed. Results in {OUTPUT_REPORT_MD}")

if __name__ == "__main__":
    main()
