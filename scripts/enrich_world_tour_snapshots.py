#!/usr/bin/env python3
"""Remove snapshot-only world-tour feeds.

This script used to enrich global CCTV records with periodically refreshed
JPG snapshots. That made still images look like live video, so the product
policy is now the opposite: snapshot-only feeds are removed and prevented from
re-entering the user-facing list.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

LOG = logging.getLogger("remove_world_tour_snapshots")
DEFAULT_INPUT = Path(__file__).resolve().parent.parent / "data" / "world_tour_cams.json"


def is_video_item(cam: dict) -> bool:
    return bool(cam.get("videoId") or cam.get("embedUrl") or cam.get("playUrl"))


def is_snapshot_only(cam: dict) -> bool:
    return bool(cam.get("snapshotUrl")) and not is_video_item(cam)


def run(path: Path) -> dict:
    raw = json.loads(path.read_text())
    items = raw.get("items", [])
    removed = [cam for cam in items if is_snapshot_only(cam)]
    if removed:
        raw["items"] = [cam for cam in items if not is_snapshot_only(cam)]
        meta = raw.setdefault("collectionMeta", {})
        meta["itemCount"] = len(raw["items"])
        meta["snapshotPolicy"] = "Snapshot-only still-image feeds are excluded from the global CCTV list."
        raw["snapshotEnrichmentMeta"] = {
            "disabled": True,
            "reason": "Snapshot-only feeds are not continuous video and are removed instead of enriched.",
            "removedTotal": len(removed),
            "removedBySource": dict(Counter((cam.get("sourceType") or "unknown") for cam in removed)),
        }
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
    return {
        "removed": len(removed),
        "bySource": dict(Counter((cam.get("sourceType") or "unknown") for cam in removed)),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    result = run(args.input)
    LOG.info("Removed %d snapshot-only cams", result["removed"])
    for source, count in sorted(result["bySource"].items()):
        LOG.info("  %s: %d", source, count)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
