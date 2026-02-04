import json
import time
import os
import smtplib
import requests
import concurrent.futures
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Configuration
DATA_FILE = 'cctv_data.json'
ALERT_THRESHOLD = 0.30  # 30%
ALERT_EMAIL_RECIPIENT = "pyw213@naver.com"
SMTP_SERVER = "smtp.gmail.com"  # Default to Gmail, change if using Naver: smtp.naver.com
SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")

def load_data():
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def check_url(cctv):
    url = cctv.get('url')
    if not url:
        return False, "No URL"

    try:
        # Timeout 5s, verify=False for some gov certs
        # Use GET with stream=True to avoid downloading large files, just check headers/start
        with requests.get(url, timeout=5, stream=True, verify=False) as response:
            if response.status_code in [200, 302]:
                return True, "OK"
            return False, f"Status {response.status_code}"
    except Exception as e:
        return False, str(e)

def send_alert_email(stats, broken_samples):
    if not SMTP_USER or not SMTP_PASSWORD:
        print("SMTP credentials not found. Skipping email.")
        return

    subject = f"[CCTV Alert] High Failure Rate Detected ({stats['failure_rate']:.1f}%)"
    
    body = f"""
    <h2>CCTV Validation Alert</h2>
    <p><b>Date:</b> {datetime.now().strftime('%Y-%m-%d')}</p>
    <p><b>Total Checked:</b> {stats['total']}</p>
    <p><b>Success:</b> {stats['success']} ({stats['success_rate']:.1f}%)</p>
    <p><b>Failed:</b> {stats['failed']} (<span style="color:red">{stats['failure_rate']:.1f}%</span>)</p>
    
    <h3>Warning</h3>
    <p>The failure rate successfully exceeded the threshold of {ALERT_THRESHOLD*100}%.</p>
    
    <h3>Broken Stream Samples (First 10)</h3>
    <ul>
    """
    
    for item in broken_samples[:10]:
        body += f"<li><b>{item['name']}</b> ({item['id']}): {item['error']} <br> <a href='{item['url']}'>{item['url']}</a></li>"
    
    body += "</ul>"

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = ALERT_EMAIL_RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        text = msg.as_string()
        server.sendmail(SMTP_USER, ALERT_EMAIL_RECIPIENT, text)
        server.quit()
        print(f"Alert email sent to {ALERT_EMAIL_RECIPIENT}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    print("Starting Weekly Validation...")
    
    # 1. Load Data
    all_data = load_data()
    total_count = len(all_data)
    
    # 2. Slice Data (Day of Week: 0=Mon, 6=Sun)
    weekday = datetime.today().weekday()
    target_data = [item for i, item in enumerate(all_data) if i % 7 == weekday]
    
    print(f"Total CCTVs: {total_count}")
    print(f"Today's Slice (Day {weekday}): {len(target_data)} items")

    # 3. Validate
    success_count = 0
    failed_count = 0
    broken_list = []

    requests.packages.urllib3.disable_warnings()

    # Max threads 20 to avoid being blocked
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_cctv = {executor.submit(check_url, cctv): cctv for cctv in target_data}
        
        # Progress indication
        completed = 0
        for future in concurrent.futures.as_completed(future_to_cctv):
            cctv = future_to_cctv[future]
            try:
                is_valid, msg = future.result()
                if is_valid:
                    success_count += 1
                else:
                    failed_count += 1
                    broken_list.append({
                        "id": cctv.get('id'),
                        "name": cctv.get('name'),
                        "url": cctv.get('url'),
                        "error": msg
                    })
            except Exception as e:
                failed_count += 1
            
            completed += 1
            if completed % 100 == 0:
                print(f"Progress: {completed}/{len(target_data)}...")

    # 4. Stats
    total_checked = success_count + failed_count
    if total_checked == 0:
        print("No items checked.")
        return

    failure_rate = failed_count / total_checked
    stats = {
        "total": total_checked,
        "success": success_count,
        "failed": failed_count,
        "success_rate": (success_count/total_checked)*100,
        "failure_rate": failure_rate*100
    }

    print("\n=== Validation Results ===")
    print(f"Success: {stats['success']}")
    print(f"Failed: {stats['failed']}")
    print(f"Failure Rate: {stats['failure_rate']:.2f}%")

    # 5. Alert
    if failure_rate >= ALERT_THRESHOLD:
        print(f"[ALERT] Failure rate exceeds {ALERT_THRESHOLD*100}%. Sending email...")
        send_alert_email(stats, broken_list)
    else:
        print("[OK] Failure rate is within acceptable limits.")

if __name__ == "__main__":
    main()
