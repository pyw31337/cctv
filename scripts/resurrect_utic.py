#!/usr/bin/env python3
"""
UTIC audit 으로 manual_check 처리된 카메라들을 살릴 방법을 시도.

배경:
  - audit_utic_broken.py 가 cctv-proxy worker /utic 에서 HTTP 404 를 받은 카메라를
    status='manual_check' 로 마킹함. 하지만 100개 표본 검증 결과 56% 가 UTIC API 에서
    여전히 살아있는 정보를 반환함. cctv_data.json 의 url 이 stale 한 게 원인.
  - 따라서 UTIC API getCctvInfoById.do 로 fresh 정보를 받아 URL 을 재구성하고,
    worker /utic 으로 한 번 더 검증해 OK 면 status='active' 로 복원.

처리 흐름:
  1) status='manual_check' 또는 legacy disabled 이면서 utic_audit_http_404 카메라 모두 대상
  2) UTIC API 로 새 정보 fetch (CCTVIP/KIND/CCTVNAME/CH/ID/PASSWD/PORT)
  3) 응답 정보로 URL 재구성 (renew_cctv_urls.construct_url 로직 재사용)
  4) 새 URL 을 cctv-proxy /utic 으로 검증 - OK (http URL or m3u8) 면 부활
  5) 부활: cctv.url 갱신, status='active', resurrected_at 기록
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CCTV_DATA = os.path.join(ROOT, "cctv_data.json")
AUDIT_LOG = os.path.join(ROOT, "data", "utic_audit_history.json")

UTIC_INFO_URL = "https://www.utic.go.kr/map/getCctvInfoById.do"
UTIC_KEY = "yjEgVGKAyWZGHyTy0gqNA8ZAq6IudLYWVqk8frqUI"
WORKER = "https://cctv-proxy.pyw213.workers.dev/utic"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (cctv-resurrect/1.0; +https://pyw31337.github.io/cctv/) Chrome/120",
    "Referer": "https://www.utic.go.kr/",
}
TIMEOUT = 8
MAX_WORKERS = 15

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def fetch_api_info(cctv_id):
    """UTIC getCctvInfoById.do 호출, JSON 정보 반환 or None."""
    url = f"{UTIC_INFO_URL}?cctvId={cctv_id}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=TIMEOUT, context=ctx)
        body = r.read().decode(errors="replace").strip()
        if not body.startswith("{"):
            return None
        info = json.loads(body)
        # 유효성: 최소한 CCTVIP 나 MOVIE 있어야 함
        ip = info.get("CCTVIP") or info.get("cctvIp") or ""
        if not (ip or info.get("MOVIE") or info.get("PASSWD")):
            return None
        # ip=='0' 인 경우는 stream id 가 없으니 무시
        if ip == "0":
            return None
        return info
    except Exception:
        return None


def construct_url(cctv_id, info):
    """renew_cctv_urls.construct_url 로직 재사용 (특수 케이스 + general)."""
    cctv_ip = info.get("CCTVIP") or info.get("cctvIp") or ""
    cctv_name = info.get("CCTVNAME") or info.get("cctvName") or ""
    kind = info.get("KIND") or info.get("kind") or ""

    # 한강·금강·낙동강·영산강 특수 케이스
    if cctv_id.startswith("E61"):
        return f"https://www.nakdongriver.go.kr/sumun/popup/cctvView.do?Obscd={info.get('ID', '')}"
    if cctv_id.startswith("E60"):
        return f"https://hrfco.go.kr/sumun/cctvPopup.do?Obscd={info.get('ID', '')}"
    if cctv_id.startswith("E62"):
        return f"https://www.geumriver.go.kr/html/sumun/rtmpView.jsp?wlobscd={info.get('PASSWD', '')}&cctvcd={info.get('ID', '')}"
    if cctv_id.startswith("E63"):
        return f"https://www.yeongsanriver.go.kr/sumun/videoDetail.do?wlobscd={info.get('PASSWD', '')}"

    # Direct stream servers
    if cctv_ip in ("210.95.12.126", "211.114.87.164"):
        sid = info.get("ID")
        if sid:
            return f"http://{cctv_ip}/media/{sid}/chunklist.m3u8"
    if cctv_ip == "211.57.45.101":
        sid = info.get("ID")
        if sid and (sid.startswith("L") or "_video" in sid):
            return f"https://211.57.45.101/media/{sid}/chunklist.m3u8"
    if cctv_id.startswith("L12") and (info.get("ID", "").startswith("cctv_")):
        return f"https://trafficcctv.paju.go.kr/live/{info.get('ID')}.stream/playlist.m3u8"

    # General: openDataCctvStream.jsp
    encoded_name = urllib.parse.quote(urllib.parse.quote(cctv_name))
    params = [
        ("key", UTIC_KEY),
        ("cctvid", cctv_id),
        ("cctvName", encoded_name),
        ("kind", kind),
        ("cctvip", cctv_ip),
        ("cctvch", info.get("CH") or "null"),
        ("id", info.get("ID") or "null"),
        ("cctvpasswd", info.get("PASSWD") or "null"),
        ("cctvport", info.get("PORT") or "null"),
    ]
    qs = "&".join(f"{k}={v}" for k, v in params)
    return f"https://www.utic.go.kr/jsp/map/openDataCctvStream.jsp?{qs}"


def verify_worker(url):
    """cctv-proxy /utic 호출, 정상 응답이면 True."""
    try:
        qs = urllib.parse.urlparse(url).query
    except Exception:
        return False
    if not qs:
        return False
    target = f"{WORKER}?{qs}"
    try:
        r = urllib.request.urlopen(urllib.request.Request(target, headers=HEADERS), timeout=TIMEOUT, context=ctx)
        body = r.read(500).decode(errors="replace").strip()
        return body.startswith("http") or body.startswith("#EXTM3U")
    except Exception:
        return False


def verify_direct_stream(url):
    """Direct HLS/MP4 URL 은 worker 가 아니라 원본을 직접 짧게 확인한다."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        req = urllib.request.Request(url, headers=HEADERS, method="GET")
        r = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        body = r.read(512).decode(errors="replace").strip()
        content_type = (r.headers.get("Content-Type") or "").lower()
        if body.startswith("#EXTM3U"):
            return True
        if "mpegurl" in content_type or "mp4" in content_type:
            return True
        return 200 <= getattr(r, "status", 0) < 300 and url.endswith((".m3u8", ".mp4"))
    except Exception:
        return False


def verify_url(url):
    parsed = urllib.parse.urlparse(url or "")
    if parsed.path.endswith((".m3u8", ".mp4")):
        return verify_direct_stream(url)
    return verify_worker(url)


def try_resurrect(cam):
    """단일 카메라 부활 시도. (cctv_id, status, new_url or None)"""
    cid = cam["id"]
    info = fetch_api_info(cid)
    if not info:
        return cid, "api_dead", None
    new_url = construct_url(cid, info)
    if not new_url:
        return cid, "url_failed", None
    if verify_url(new_url):
        return cid, "alive", new_url
    return cid, "worker_still_404", None


def main():
    with open(CCTV_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    targets = [
        c for c in data
        if c.get("status") in ("manual_check", "disabled")
        and (c.get("health_reason") == "utic_audit_http_404" or c.get("disabled_reason") == "utic_audit_http_404")
    ]
    print(f"[resurrect] candidates: {len(targets):,} (manual_check/legacy disabled by utic_audit_http_404)", flush=True)
    if not targets:
        print("[resurrect] nothing to do", flush=True)
        return

    by_id = {c["id"]: c for c in data}
    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futs = {exe.submit(try_resurrect, c): c for c in targets}
        done = 0
        for fut in as_completed(futs):
            cid, status, new_url = fut.result()
            results[cid] = (status, new_url)
            done += 1
            if done % 200 == 0:
                pct = done * 100 / len(targets)
                print(
                    f"[resurrect] progress {done}/{len(targets)} "
                    f"({pct:.1f}%, {time.time()-t0:.0f}s)",
                    flush=True,
                )

    from collections import Counter
    counter = Counter(s for s, _ in results.values())
    print("[resurrect] breakdown:")
    for s, n in counter.most_common():
        pct = n*100/len(targets)
        print(f"  {s:25s}: {n:4d} ({pct:.1f}%)")

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    resurrected = 0
    for cid, (status, new_url) in results.items():
        if status == "alive" and new_url:
            cam = by_id[cid]
            cam["url"] = new_url
            cam["status"] = "active"
            cam.pop("health_reason", None)
            cam.pop("health_checked_at", None)
            cam.pop("disabled_reason", None)
            cam.pop("disabled_at", None)
            cam["resurrected_at"] = now_iso
            resurrected += 1

    print(f"[resurrect] resurrected: {resurrected} cameras", flush=True)

    with open(CCTV_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[resurrect] wrote {CCTV_DATA}", flush=True)

    # audit history 에 resurrect 라인 추가
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = []
    else:
        history = []
    history.append({
        "audited_at": now_iso,
        "phase": "resurrect",
        "targets": len(targets),
        "resurrected": resurrected,
        "breakdown": dict(counter),
        "elapsed_sec": int(time.time() - t0),
    })
    history = history[-90:]
    with open(AUDIT_LOG, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
