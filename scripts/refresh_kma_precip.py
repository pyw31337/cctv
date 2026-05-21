#!/usr/bin/env python3
"""Fetch KMA short-term forecast for a coarse grid covering South Korea and
dump it to data/kma_precip_current.json. Run hourly via GitHub Actions.

The KMA endpoint `https://www.kma.go.kr/wid/queryDFS.jsp?gridx={x}&gridy={y}`
is a public, key-free XML feed used by weather.go.kr itself. It returns the
next ~24 hours of forecast slots; we extract the *upcoming* slot's `pty`
(precipitation type), `r06`, `s06`, and `wfKor` for each grid point.

We use the city grid coordinates of the major-population centers plus a
sparse fill across mountain/coastal regions — 30 points total — which is
plenty for the heatmap overlay (Kakao map renders them as graduated
circles).
"""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error as urlerror
from urllib import request

LOG = logging.getLogger("refresh_kma_precip")
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "kma_precip_current.json"
KMA_URL = "https://www.kma.go.kr/wid/queryDFS.jsp?gridx={x}&gridy={y}"
UA = "Mozilla/5.0 (compatible; KmaPrecipRefresher/1.0)"
TIMEOUT = 10

# Grid points (KMA DFS XY) + display lat/lng + city label.
# Coverage: 광역시·도청 + 주요 산악/해안 보조점. ~30 points balances detail vs. cron load.
GRID_POINTS = [
    # 서울/수도권
    {"x": 60, "y": 127, "lat": 37.5665, "lng": 126.9780, "name": "서울"},
    {"x": 55, "y": 124, "lat": 37.4563, "lng": 126.7052, "name": "인천"},
    {"x": 60, "y": 121, "lat": 37.2636, "lng": 127.0286, "name": "수원"},
    {"x": 58, "y": 138, "lat": 38.1467, "lng": 128.5915, "name": "속초"},
    # 강원
    {"x": 73, "y": 134, "lat": 37.8228, "lng": 128.1555, "name": "강릉"},
    {"x": 73, "y": 119, "lat": 37.8813, "lng": 127.7298, "name": "춘천"},
    # 충청
    {"x": 67, "y": 100, "lat": 36.3504, "lng": 127.3845, "name": "대전"},
    {"x": 69, "y": 107, "lat": 36.6357, "lng": 127.4912, "name": "청주"},
    {"x": 66, "y": 103, "lat": 36.5184, "lng": 126.8000, "name": "세종"},
    {"x": 76, "y": 122, "lat": 37.7519, "lng": 128.8761, "name": "동해"},
    # 호남
    {"x": 58, "y": 74, "lat": 35.1595, "lng": 126.8526, "name": "광주"},
    {"x": 63, "y": 89, "lat": 35.8242, "lng": 127.1480, "name": "전주"},
    {"x": 50, "y": 67, "lat": 34.8118, "lng": 126.3922, "name": "목포"},
    {"x": 73, "y": 73, "lat": 34.7604, "lng": 127.6622, "name": "여수"},
    # 영남
    {"x": 89, "y": 90, "lat": 35.8714, "lng": 128.6014, "name": "대구"},
    {"x": 98, "y": 76, "lat": 35.1796, "lng": 129.0756, "name": "부산"},
    {"x": 102, "y": 84, "lat": 35.5384, "lng": 129.3114, "name": "울산"},
    {"x": 102, "y": 94, "lat": 36.0190, "lng": 129.3435, "name": "포항"},
    {"x": 91, "y": 77, "lat": 35.2284, "lng": 128.6811, "name": "창원"},
    {"x": 87, "y": 106, "lat": 36.5760, "lng": 128.5056, "name": "안동"},
    # 제주
    {"x": 52, "y": 38, "lat": 33.4996, "lng": 126.5312, "name": "제주"},
    {"x": 60, "y": 33, "lat": 33.2541, "lng": 126.5601, "name": "서귀포"},
    # 산악/보조
    {"x": 73, "y": 124, "lat": 37.6750, "lng": 128.2700, "name": "대관령"},
    {"x": 84, "y": 89, "lat": 35.8090, "lng": 127.6660, "name": "지리산"},
    {"x": 81, "y": 119, "lat": 37.7060, "lng": 128.6890, "name": "태백"},
]


def fetch_grid_point(point: dict) -> dict | None:
    url = KMA_URL.format(x=point["x"], y=point["y"])
    try:
        req = request.Request(url, headers={"User-Agent": UA})
        with request.urlopen(req, timeout=TIMEOUT) as r:
            xml = r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        LOG.warning("fetch failed for %s: %s", point["name"], exc)
        return None

    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        LOG.warning("XML parse failed for %s: %s", point["name"], exc)
        return None

    # First data element is the upcoming slot.
    data = root.find("body/data")
    if data is None:
        return None

    def text(tag, default=""):
        el = data.find(tag)
        return (el.text or "").strip() if el is not None else default

    def num(tag, default=0.0):
        try:
            v = float(text(tag))
            return 0.0 if v == -999.0 else v
        except (TypeError, ValueError):
            return default

    pty_map = {
        "0": "none",
        "1": "rain",
        "2": "sleet",
        "3": "snow",
        "5": "drizzle",
        "6": "drizzle_sleet",
        "7": "snow_flurry",
    }
    pty = text("pty", "0")
    return {
        "x": point["x"],
        "y": point["y"],
        "lat": point["lat"],
        "lng": point["lng"],
        "name": point["name"],
        "pty": pty_map.get(pty, "none"),
        "ptyCode": pty,
        "rainMm6h": num("r06"),
        "snowCm6h": num("s06"),
        "tempC": num("temp"),
        "wfKor": text("wfKor"),
        "wfEn": text("wfEn"),
        "skyCode": text("sky"),
    }


def run(output_path: Path) -> dict:
    LOG.info("Fetching %d KMA grid points…", len(GRID_POINTS))
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_grid_point, pt): pt for pt in GRID_POINTS}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                results.append(res)

    # Sort by name for deterministic JSON diffs.
    results.sort(key=lambda r: r["name"])

    summary = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source": "KMA DFS (www.kma.go.kr/wid/queryDFS.jsp)",
        "point_count": len(results),
        "any_precipitation": any(r["pty"] != "none" for r in results),
        "max_rain_mm6h": max((r["rainMm6h"] for r in results), default=0.0),
        "max_snow_cm6h": max((r["snowCm6h"] for r in results), default=0.0),
        "points": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    LOG.info("Wrote %s (%d points, max rain %.1fmm, max snow %.1fcm)",
             output_path, summary["point_count"],
             summary["max_rain_mm6h"], summary["max_snow_cm6h"])
    return summary


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    run(args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
