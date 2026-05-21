#!/usr/bin/env python3
"""Enrich data/world_tour_cams.json with `snapshotUrl` so that in-app
image-refresh playback can replace the "open the original site" prompt
for the four high-confidence sources where direct JPG access is permitted.

Covered sources:
  - hktraffic    : Hong Kong Transport Department traffic CCTV (CORS-open, ~1 min)
  - usgsvolcano  : USGS VolcView ash-cam network            (CORS-open, ~5-10 min)
  - panomax      : Panomax preview images                    (validate via HEAD)
  - roundshot    : Roundshot dated CDN URLs                  (refresh requires
                   collector re-run; in-app shows the latest snapshot captured
                   at collection time — better than an external redirect.)

Usage:
    python3 scripts/enrich_world_tour_snapshots.py \
        [--input data/world_tour_cams.json] \
        [--no-validate-panomax]

This script is idempotent — running it twice produces the same output.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error as urlerror
from urllib import request

LOG = logging.getLogger("enrich_world_tour_snapshots")
DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "world_tour_cams.json"
USER_AGENT = "cctv-snapshot-enricher/1.0 (+https://github.com/pyw31337/cctv)"
PANOMAX_HEAD_TIMEOUT_SEC = 6


def derive_snapshot(cam: dict) -> str | None:
    """Return a best-effort direct JPG URL for the given world-tour cam.

    Returns None for sources we don't yet know how to embed inline.
    """
    source_type = (cam.get("sourceType") or "").lower()
    source_url = cam.get("sourceUrl") or ""
    thumb_url = cam.get("thumbnailUrl") or ""

    if source_type == "hktraffic":
        # sourceUrl is already a direct .JPG (e.g. https://tdcctv.data.one.gov.hk/H422F2.JPG)
        return source_url if source_url.lower().endswith(".jpg") else None

    if source_type == "usgsvolcano":
        # thumbnail: .../current-thumb.jpg → upgrade to full-size .../current.jpg
        if thumb_url.endswith("-thumb.jpg"):
            return thumb_url.replace("-thumb.jpg", ".jpg")
        return thumb_url if thumb_url.endswith(".jpg") else None

    if source_type == "panomax":
        # panodata.panomax.com/cams/{id}/preview_og.jpg — used directly. Some cam IDs
        # return 404; validation happens in a separate pass.
        return thumb_url if thumb_url.endswith(".jpg") else None

    if source_type == "roundshot":
        # Date-stamped CDN URL. Won't auto-update inside the browser but the value
        # is refreshed every time this script runs (e.g. via the daily GHA).
        return thumb_url if thumb_url.endswith(".jpg") else None

    return None


def head_ok(url: str) -> bool:
    """Return True if HEAD returns 200. Falls back to a tiny GET on 405."""
    try:
        req = request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
        with request.urlopen(req, timeout=PANOMAX_HEAD_TIMEOUT_SEC) as resp:
            return 200 <= resp.status < 300
    except urlerror.HTTPError as exc:
        if exc.code in (405, 501):  # method not allowed — try GET with byte range
            try:
                req = request.Request(
                    url,
                    headers={"User-Agent": USER_AGENT, "Range": "bytes=0-15"},
                )
                with request.urlopen(req, timeout=PANOMAX_HEAD_TIMEOUT_SEC) as resp:
                    return 200 <= resp.status < 300
            except Exception:  # pragma: no cover
                return False
        return False
    except Exception:
        return False


def validate_panomax(snapshot_by_id: dict[str, str], max_workers: int = 16) -> set[str]:
    """Return the set of cam IDs whose Panomax preview image returns HTTP 200."""
    keep: set[str] = set()
    if not snapshot_by_id:
        return keep
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(head_ok, url): cam_id for cam_id, url in snapshot_by_id.items()}
        for fut in as_completed(futures):
            cam_id = futures[fut]
            try:
                if fut.result():
                    keep.add(cam_id)
            except Exception:
                continue
    return keep


def run(input_path: Path, validate_panomax_flag: bool = True) -> dict:
    raw = json.loads(input_path.read_text())
    items = raw["items"]

    counters: dict[str, int] = {}
    panomax_candidates: dict[str, str] = {}

    for cam in items:
        snap = derive_snapshot(cam)
        if not snap:
            continue
        source_type = (cam.get("sourceType") or "").lower()
        if source_type == "panomax":
            panomax_candidates[cam["id"]] = snap
            continue
        cam["snapshotUrl"] = snap
        cam.setdefault("playbackKind", "snapshot")
        counters[source_type] = counters.get(source_type, 0) + 1

    if panomax_candidates:
        if validate_panomax_flag:
            LOG.info("Validating %d panomax preview URLs…", len(panomax_candidates))
            keep = validate_panomax(panomax_candidates)
        else:
            keep = set(panomax_candidates.keys())
        for cam in items:
            if cam["id"] in keep:
                cam["snapshotUrl"] = panomax_candidates[cam["id"]]
                cam.setdefault("playbackKind", "snapshot")
                counters["panomax"] = counters.get("panomax", 0) + 1

    raw["snapshotEnrichmentMeta"] = {
        "counts": counters,
        "total": sum(counters.values()),
    }
    input_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    return counters


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT), type=Path)
    parser.add_argument("--no-validate-panomax", action="store_true",
                        help="Skip the per-cam HEAD validation for Panomax (faster).")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    counters = run(args.input, validate_panomax_flag=not args.no_validate_panomax)
    LOG.info("Enriched %d cams with snapshotUrl", sum(counters.values()))
    for source, count in sorted(counters.items()):
        LOG.info("  %s: %d", source, count)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
