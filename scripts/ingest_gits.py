#!/usr/bin/env python3
"""
GITS 카메라 (경기도 지능형 교통체계) 1,800+개를 cctv_data.json 에 ingest.

배경:
  - 이전엔 cctv-proxy worker /gits 엔드포인트가 실시간으로 popup → video URL 추출했으나
    현재 Oracle /gits 가 hang/응답 없음. 클라이언트 재생 경로가 전부 막힘.
  - GITS popup 자체는 살아있고 `<video src="https://gitsview.gg.go.kr/{id}/{token}">` 패턴으로
    유효한 mp4/m3u8 토큰을 반환함이 확인됨 (테스트 일자: 2026-05-21).
  - 따라서 popup 을 daily 로 한 번씩 긁어 fresh URL 을 cctv_data.json 에 박는 전략으로 전환.

전략:
  - collectors.gits.GitsCollector 를 그대로 사용 (이미 popup 3개 패턴 처리)
  - 새로 받은 카메라는 갱신하고, 이번 실행에서 누락된 기존 ID는 검토 상태로 보존
  - 결과: 일시적인 토큰 발급 실패로 카탈로그가 축소되지 않음
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from collectors.gits import GitsCollector

CCTV_DATA = os.path.join(ROOT, "cctv_data.json")


def merge_gits_catalog(data, fresh, now_iso):
    others = [cam for cam in data if cam.get("source") != "GITS"]
    existing = {
        str(cam.get("id")): cam
        for cam in data
        if cam.get("source") == "GITS" and cam.get("id")
    }
    fresh_by_id = {}
    for cam in fresh:
        cam_id = str(cam.get("id") or "")
        if not cam_id:
            continue
        normalized = dict(cam)
        normalized.setdefault("source", "GITS")
        normalized["status"] = "active"
        normalized.setdefault("backup_urls", [])
        normalized["ingested_at"] = now_iso
        normalized.pop("health_reason", None)
        normalized.pop("health_checked_at", None)
        fresh_by_id[cam_id] = normalized

    retained = []
    for cam_id, cam in existing.items():
        if cam_id in fresh_by_id:
            continue
        preserved = dict(cam)
        preserved["status"] = "manual_check"
        preserved["health_reason"] = "stream_missing_latest_gits_ingest"
        preserved["health_checked_at"] = now_iso
        retained.append(preserved)

    return others + list(fresh_by_id.values()) + retained, {
        "fresh": len(fresh_by_id),
        "retained": len(retained),
        "new": len(set(fresh_by_id) - set(existing)),
        "updated": len(set(fresh_by_id) & set(existing)),
    }


def main():
    print("[gits-ingest] starting GitsCollector...", flush=True)
    t0 = time.time()
    collector = GitsCollector()
    fresh = collector.fetch_data()
    print(
        f"[gits-ingest] collector returned {len(fresh)} cameras "
        f"in {time.time()-t0:.0f}s",
        flush=True,
    )

    if not fresh:
        print("[gits-ingest] empty result - aborting to avoid wiping cctv_data.json", flush=True)
        sys.exit(1)

    with open(CCTV_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    before_gits = sum(1 for c in data if c.get("source") == "GITS")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    merged, stats = merge_gits_catalog(data, fresh, now_iso)
    after_gits = sum(1 for c in merged if c.get("source") == "GITS")
    print(
        f"[gits-ingest] cctv_data.json: GITS {before_gits} -> {after_gits}, "
        f"total {len(data)} -> {len(merged)}; {stats}",
        flush=True,
    )

    with open(CCTV_DATA, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"[gits-ingest] wrote {CCTV_DATA}", flush=True)


if __name__ == "__main__":
    main()
