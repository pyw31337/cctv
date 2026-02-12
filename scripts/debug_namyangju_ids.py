import json
import re

def main():
    with open("cctv_data_pre_audit_v2.json", "r", encoding="utf-8") as f:
        data = json.load(f)
        
    print(f"{'Name':<30} | {'ID':<10} | {'Stream ID':<10}")
    print("-" * 60)
    
    for item in data:
        cctv_id = item.get("id", "")
        name = item.get("name", "")
        url = item.get("url", "")
        
        if cctv_id.startswith("L180"):
            match = re.search(r"/media/(L\d+)/", url)
            stream_id = match.group(1) if match else "N/A"
            
            if "마석" in name or "샛터" in name or "창현" in name or "퇴계원" in name or "양정" in name:
                print(f"{name:<30} | {cctv_id:<10} | {stream_id:<10}")

if __name__ == "__main__":
    main()
