#!/usr/bin/env python3
"""
UTIC 전수 audit — non-Z3 (E-prefix) + LEGACY (L-prefix) 카메라가 cctv-proxy /utic 워커에서
HTTP 404 를 반환하면 cctv_data.json 에 status='disabled' 로 마킹.

전략:
  - 병렬 호출 (worker 20개) 로 빠르게 검증
  - HTTP 404 만 broken 처리 (timeout/네트워크 오류는 일시적일 수 있으니 무시)
  - 이전엔 disabled 였지만 이번에 ok 인 카메라는 status='active' 로 회복
  - data/utic_audit_history.json 에 결과 누적 (디버깅/모니터링용)
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
WORKER = "https://cctv-proxy.pyw213.workers.dev/utic"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (cctv-audit/1.0; +https://pyw31337.github.io/cctv/)",
    "Origin": "https://pyw31337.github.io",
    "Referer": "https://pyw31337.github.io/cctv/",
}
TIMEOUT = 10
MAX_WORKERS = 20

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def is_target(cam):
    """audit 대상: source=UTIC 이고 kind=Z3 가 아닌 카메라 (L-prefix legacy 포함)."""
    if cam.get("source") != "UTIC":
        return False
    url = cam.get("url", "")
    if "kind=Z3" in url:
        return False  # Z3 는 z3_cache 경로로 따로 처리
    cid = cam.get("id", "")
    return cid.startswith("L") or cid.startswith("E")


def check_one(cam):
    """한 카메라를 worker /utic 으로 호출해 ok/404/기타 분류."""
    url = cam.get("url", "")
    try:
        qs = urllib.parse.urlparse(url).query
    except Exception:
        return cam["id"], "bad_url"
    target = f"{WORKER}?{qs}"
    try:
        req = urllib.request.Request(target, headers=HEADERS)
        r = urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx)
        body = r.read(500).decode(errors="replace").strip()
        if body.startswith("http") or body.startswith("#EXTM3U"):
            return cam["id"], "ok"
        return cam["id"], f"weird_{r.status}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return cam["id"], "404"
        return cam["id"], f"http_{e.code}"
    except Exception as e:
        return cam["id"], f"err_{type(e).__name__}"


def main(limit=None):
    with open(CCTV_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    targets = [c for c in data if is_target(c)]
    if limit:
        targets = targets[:limit]
    print(f"[audit] targets: {len(targets):,} cameras", flush=True)

    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        futs = {exe.submit(check_one, c): c for c in targets}
        done = 0
        for fut in as_completed(futs):
            cid, status = fut.result()
            results[cid] = status
            done += 1
            if done % 200 == 0:
                pct = done * 100 / len(targets)
                print(
                    f"[audit] progress {done}/{len(targets)} "
                    f"({pct:.1f}%, {time.time()-t0:.0f}s)",
                    flush=True,
                )

    by_status = {}
    for cid, s in results.items():
        by_status.setdefault(s, []).append(cid)
    print("[audit] result breakdown:")
    for s, ids in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
        print(f"  {s:18s} {len(ids):5d}")

    broken_ids = set(by_status.get("404", []))
    ok_ids = set(by_status.get("ok", []))
    print(f"[audit] confirmed broken (404): {len(broken_ids)}, ok: {len(ok_ids)}")

    # === cctv_data.json status 업데이트 ===
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    newly_disabled = 0
    recovered = 0
    for cam in data:
        cid = cam.get("id", "")
        if cid in broken_ids:
            if cam.get("status") != "disabled":
                cam["status"] = "disabled"
                cam["disabled_reason"] = "utic_audit_http_404"
                cam["disabled_at"] = now_iso
                newly_disabled += 1
        elif cid in ok_ids:
            # 회복: 이전 audit 에서 disabled 였으면 active 로 복귀
            if (
                cam.get("status") == "disabled"
                and cam.get("disabled_reason") == "utic_audit_http_404"
            ):
                cam["status"] = "active"
                cam.pop("disabled_reason", None)
                cam.pop("disabled_at", None)
                cam["recovered_at"] = now_iso
                recovered += 1

    print(
        f"[audit] cctv_data.json delta: {newly_disabled} newly disabled, {recovered} recovered"
    )

    with open(CCTV_DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[audit] wrote {CCTV_DATA}")

    # === audit log 누적 ===
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    if os.path.exists(AUDIT_LOG):
        with open(AUDIT_LOG, "r", encoding="utf-8") as f:
            history = json.load(f)
        if not isinstance(history, list):
            history = []
    else:
        history = []
    history.append(
        {
            "audited_at": now_iso,
            "targets": len(targets),
            "broken": len(broken_ids),
            "ok": len(ok_ids),
            "newly_disabled": newly_disabled,
            "recovered": recovered,
            "elapsed_sec": int(time.time() - t0),
        }
    )
    history = history[-90:]  # 최근 90 회만 유지
    with open(AUDIT_LOG, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            pass
    main(limit=limit)
