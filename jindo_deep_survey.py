import json
import requests
import re
import time
import xml.etree.ElementTree as ET
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DATA_FILE = "cctv_data.json"
OUTPUT_REPORT_MD = "jindo_deep_survey_report.md"
OUTPUT_REPORT_JSON = "jindo_deep_survey_results.json"
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
        # Filter for Jindo (ignoring Dangjin)
        return [item for item in data if "진도" in item.get("name", "") and "당진" not in item.get("name", "")]
    except Exception as e:
        log(f"Error loading existing data: {e}")
    return []

def deep_validate_stream(cid, name):
    url = f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?key={UTIC_KEY}&cctvid={cid}"
    result = {
        "id": cid,
        "name": name,
        "status": "UNKNOWN",
        "ip": "N/A",
        "reason": "",
        "stream_url": ""
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
        
        # Parse ConnectSrv to get internal stream info
        # ConnectSrv('IP', 'Port', 'ID')
        match = re.search(r"ConnectSrv\('([^']+)', '([^']+)', '([^']+)'", resp.text)
        if match:
            ip = match.group(1)
            port = match.group(2)
            stream_id = match.group(3)
            result["ip"] = ip
            
            if any(g in ip for g in GARBAGE_IPS):
                result["status"] = "GARBAGE"
                result["reason"] = f"Bad IP detected ({ip})"
                return result
            
            # Construct a theoretical RTSP/HTTP URL based on UTIC patterns if possible?
            # Actually, UTIC streams often use a specific relay server.
            # Let's try to see if the IP responds to the port.
            # (Warning: firewall might block direct connection, but 80/443 might be open for some)
            
            # Also check for "No Image" indicators in HTML
            if "준비중" in resp.text or "점검중" in resp.text:
                result["status"] = "MAINTENANCE"
                result["reason"] = "Under maintenance / Preparations"
                return result

            result["status"] = "OK"
            result["reason"] = f"Valid ConnectSrv ({ip}:{port})"
            
        else:
            result["status"] = "NO_STREAM"
            result["reason"] = "ConnectSrv not found in player HTML"
            
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
    
    # De-duplicate and combine
    all_candidates = {}
    for item in existing:
        all_candidates[item["id"]] = item["name"]
    for item in master_candidates:
        all_candidates[item["id"]] = item["name"]
        
    log(f"Total unique Jindo candidates: {len(all_candidates)}")
    
    # 2. Survey
    results = []
    count = 0
    total = len(all_candidates)
    
    for cid, name in sorted(all_candidates.items()):
        count += 1
        log(f"[{count}/{total}] Deep Checking {cid} ({name})...")
        res = deep_validate_stream(cid, name)
        results.append(res)
        log(f"   -> {res['status']} ({res['reason']})")
        time.sleep(0.5)
        
    # 3. Analyze Duplicates (items with same IP or very similar coordinates if available)
    # Since we don't have coords for all yet, we check for name similarity and IP collision.
    ip_map = {}
    for res in results:
        if res["status"] == "OK" and res["ip"] != "N/A":
            if res["ip"] not in ip_map:
                ip_map[res["ip"]] = []
            ip_map[res["ip"]].append(res)
            
    # 4. Generate Combined Report
    with open(OUTPUT_REPORT_JSON, "w") as f:
        json.dump(results, f, indent=2)
        
    with open(OUTPUT_REPORT_MD, "w") as f:
        f.write("# Jindo CCTV Deep Survey Report\n\n")
        f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Potential Duplicates (Shared Source IPs)\n")
        f.write("Some IDs share the same backend IP/Port, indicating they might be redundant entries.\n\n")
        for ip, items in ip_map.items():
            if len(items) > 1:
                f.write(f"### IP: {ip}\n")
                for it in items:
                    f.write(f"- {it['id']}: {it['name']}\n")
                f.write("\n")
                
        f.write("## Status of Failed/Suspect Items\n\n")
        f.write("| ID | Name | Status | Reason |\n")
        f.write("|---|---|---|---|\n")
        # Focus on "진도터널입구" or any NO_STREAM/GARBAGE
        for r in results:
            if r["status"] != "OK" or "진도터널입구" in r["name"]:
                f.write(f"| {r['id']} | {r['name']} | {r['status']} | {r['reason']} |\n")

    log(f"Deep Survey completed. Report saved to {OUTPUT_REPORT_MD}")

if __name__ == "__main__":
    main()
