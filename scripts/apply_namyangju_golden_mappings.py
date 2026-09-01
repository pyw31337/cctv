#!/usr/bin/env python3
"""Apply and lock the verified Namyangju UTIC stream mappings."""

from __future__ import annotations

import json
from pathlib import Path

from cctv_runtime import (
    NAMYANGJU_GOLDEN_STREAMS,
    KNOWN_CAMERA_ID_ALIASES,
    apply_camera_id_aliases,
    apply_namyangju_golden_mappings,
    atomic_write_json,
    validate_namyangju_golden_mappings,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "cctv_data.json"
OVERRIDES_FILE = ROOT / "cctv_overrides.json"


def main() -> int:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("cctv_data.json must contain a list")

    changed = apply_camera_id_aliases(data)
    changed += apply_namyangju_golden_mappings(data)
    errors = validate_namyangju_golden_mappings(data, require_all=True)
    if errors:
        raise ValueError("; ".join(errors))

    overrides = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    if not isinstance(overrides, list):
        raise ValueError("cctv_overrides.json must contain a list")

    golden_ids = set(NAMYANGJU_GOLDEN_STREAMS)
    retired_ids = golden_ids | set(KNOWN_CAMERA_ID_ALIASES)
    retained = [item for item in overrides if item.get("id") not in retired_ids]
    by_id = {item.get("id"): item for item in data if item.get("id") in golden_ids}
    for camera_id, (name, stream_id) in NAMYANGJU_GOLDEN_STREAMS.items():
        item = by_id[camera_id]
        retained.append(
            {
                "id": camera_id,
                "name": name,
                "url": item["url"],
                "directUrl": item["directUrl"],
                "tags": ["direct_source", "locked_mapping", "golden_namyangju"],
                "golden_stream_id": stream_id,
                "_comment": "Verified Namyangju stream mapping; do not auto-renew.",
            }
        )

    atomic_write_json(DATA_FILE, data, sort_keys=False)
    atomic_write_json(OVERRIDES_FILE, retained, sort_keys=False)
    print(f"Applied {changed} mapping fields and locked {len(by_id)} Namyangju cameras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
