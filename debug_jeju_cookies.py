import requests

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# 1. Visit Main Page to get Cookies (JSESSIONID, etc.)
main_url = "https://www.jejuits.go.kr/jido/mainView.do"
print("Visiting main page...")
resp = s.get(main_url, verify=False)
print(f"Main Page Status: {resp.status_code}")
print(f"Cookies: {s.cookies.get_dict()}")

# 2. Request Stream URL
api_url = "https://www.jejuits.go.kr/jido/streamUrl.do"
payload = {"DEVICE_ID": "C62"}
headers = {
    "Referer": "https://www.jejuits.go.kr/jido/mainView.do?DEVICE_KIND=CCTV",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest"
}

print("Requesting Stream URL...")
resp = s.post(api_url, data=payload, headers=headers, verify=False)
print(f"API Status: {resp.status_code}")
print(f"API Response: {resp.text}")
