#!/usr/bin/env python3
"""Round 2 of in-app playback expansion.

Adds `snapshotUrl` for two more sources:

  - baltic   : 96 cams. Their `thumbs.balticlivecam.com/blc/*_sm.jpg` URLs are
               live thumbnails that the CDN refreshes every ~30-60 minutes
               (verified Last-Modified). The other Baltic thumbnail bucket
               (`balticlivecam.com/images/webcam_*-453x255.jpg`) is a STATIC
               2021-era promo image; we exclude it.
  - worldcam : 97 cams. Each cam page on worldcam.eu embeds a per-cam live
               JPG at `https://www.worldcam.pl/images/webcams/420x236/<slug>.jpg`.
               The slug is per-page and not derivable, so we scrape it.

Both sources require HEAD-validation because some cams are dead.

Run after `enrich_world_tour_snapshots.py` (round 1). Both scripts are
idempotent and only ever ADD `snapshotUrl` to cams that don't have it.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error as urlerror
from urllib import request

LOG = logging.getLogger("enrich_world_tour_v2")
DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "world_tour_cams.json"
UA = "Mozilla/5.0 (compatible; CctvWorldTourEnricher/2.0)"
TIMEOUT = 12
WORLDCAM_LIVE_IMG_RE = re.compile(
    r'https?://(?:www\.)?(?:img\.)?worldcam\.pl/(?:images/)?webcams/420x236/[^"\' >]+\.jpg',
    re.I,
)


def fetch(url: str) -> str | None:
    try:
        req = request.Request(url, headers={"User-Agent": UA})
        with request.urlopen(req, timeout=TIMEOUT) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as exc:
        LOG.debug("fetch failed %s: %s", url, exc)
        return None


def head_ok(url: str) -> bool:
    try:
        req = request.Request(url, method="HEAD", headers={"User-Agent": UA})
        with request.urlopen(req, timeout=TIMEOUT) as r:
            return 200 <= r.status < 300
    except urlerror.HTTPError as exc:
        return exc.code == 405  # treat method-not-allowed as "image exists"
    except Exception:
        return False


def baltic_snapshot(cam: dict) -> str | None:
    """Return the live thumbnail URL when it's hosted on the live CDN."""
    thumb = cam.get("thumbnailUrl") or ""
    if thumb.startswith("https://thumbs.balticlivecam.com/"):
        return thumb
    return None


def worldcam_snapshot(cam: dict) -> str | None:
    """Fetch the per-cam page and extract the first 420x236 JPG URL."""
    source_url = cam.get("sourceUrl") or ""
    if not source_url:
        return None
    html = fetch(source_url)
    if not html:
        return None
    # The main cam's snapshot is the first 420x236 image on the page; other
    # 420x236 references are neighbor previews further down — taking the first
    # match gives us the right one for ~all observed cases.
    match = WORLDCAM_LIVE_IMG_RE.search(html)
    return match.group(0) if match else None


def parallel(items, worker, max_workers=10):
    out = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(worker, c): c["id"] for c in items}
        for fut in as_completed(futures):
            cam_id = futures[fut]
            try:
                out[cam_id] = fut.result()
            except Exception:
                out[cam_id] = None
    return out


def run(path: Path) -> dict[str, int]:
    raw = json.loads(path.read_text())
    items = raw["items"]
    by_source: dict[str, list[dict]] = {}
    for cam in items:
        if cam.get("snapshotUrl"):
            continue  # already enriched in round 1
        st = (cam.get("sourceType") or "").lower()
        if st in ("baltic", "worldcam"):
            by_source.setdefault(st, []).append(cam)

    counters: dict[str, int] = {}

    # Baltic — derive snapshot from existing thumbnailUrl, no fetch needed.
    baltic_cams = by_source.get("baltic", [])
    baltic_candidates = {c["id"]: baltic_snapshot(c) for c in baltic_cams}
    baltic_candidates = {k: v for k, v in baltic_candidates.items() if v}
    LOG.info("Baltic candidates: %d", len(baltic_candidates))
    # HEAD-validate (some `_sm.jpg` URLs 404).
    head_results = parallel(
        [{"id": k, "_url": v} for k, v in baltic_candidates.items()],
        lambda c: head_ok(c["_url"]),
        max_workers=16,
    )
    for cam in baltic_cams:
        url = baltic_candidates.get(cam["id"])
        if url and head_results.get(cam["id"]):
            cam["snapshotUrl"] = url
            cam.setdefault("playbackKind", "snapshot")
            counters["baltic"] = counters.get("baltic", 0) + 1

    # WorldCam — scrape each cam page.
    worldcam_cams = by_source.get("worldcam", [])
    LOG.info("WorldCam scrape: %d pages", len(worldcam_cams))
    wc_results = parallel(worldcam_cams, worldcam_snapshot, max_workers=8)
    # HEAD-validate the discovered URLs (some scrapes return stale URLs).
    head_targets = [{"id": k, "_url": v} for k, v in wc_results.items() if v]
    wc_head = parallel(
        head_targets,
        lambda c: head_ok(c["_url"]),
        max_workers=12,
    )
    for cam in worldcam_cams:
        url = wc_results.get(cam["id"])
        if url and wc_head.get(cam["id"]):
            cam["snapshotUrl"] = url
            cam.setdefault("playbackKind", "snapshot")
            counters["worldcam"] = counters.get("worldcam", 0) + 1

    # Update the enrichment meta to reflect the cumulative count.
    meta = raw.setdefault("snapshotEnrichmentMeta", {})
    rolling = dict(meta.get("counts", {}))
    for src, n in counters.items():
        rolling[src] = rolling.get(src, 0) + n
    meta["counts"] = rolling
    meta["total"] = sum(rolling.values())
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    return counters


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    counts = run(args.input)
    LOG.info("Added snapshotUrl to %d more cams", sum(counts.values()))
    for src, n in counts.items():
        LOG.info("  %s: %d", src, n)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
