#!/usr/bin/env python3
"""Audit and explicitly promote reviewed camera-to-stream mapping candidates.

Collectors never call this script. A candidate is only written to the locked
registry when it is structurally valid, unique, and the operator supplies
``--promote``. This keeps transient resolver observations out of production.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from cctv_runtime import (
    STREAM_MAPPING_REGISTRY_FILE,
    stream_id_from_url,
    validate_stream_mapping_registry,
)


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def validate_candidates(candidates: list[dict], catalog: list[dict], registry: dict) -> list[str]:
    errors: list[str] = []
    existing = {str(item.get("camera_id") or "").upper(): item for item in registry.get("mappings", [])}
    stream_owners = {
        str(item.get("stream_id") or "").upper(): str(item.get("camera_id") or "").upper()
        for item in registry.get("mappings", [])
        if isinstance(item, dict)
    }
    catalog_by_id = {str(item.get("id") or "").upper(): item for item in catalog if isinstance(item, dict)}

    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("candidate is not an object")
            continue
        camera_id = str(candidate.get("camera_id") or "").upper()
        stream_id = str(candidate.get("stream_id") or "").upper()
        if not camera_id or not stream_id or not candidate.get("name") or not candidate.get("source"):
            errors.append(f"{camera_id or '<missing>'}: camera_id, stream_id, name, source are required")
            continue
        if candidate.get("verified") is not True:
            errors.append(f"{camera_id}: candidate must be explicitly verified")
        owner = stream_owners.get(stream_id)
        if owner and owner != camera_id:
            errors.append(f"{camera_id}: stream {stream_id} already belongs to {owner}")
        item = catalog_by_id.get(camera_id)
        if not item:
            errors.append(f"{camera_id}: camera is not present in catalog")
            continue
        if str(item.get("source") or "").upper() != str(candidate.get("source") or "").upper():
            errors.append(f"{camera_id}: source mismatch")
        if item.get("name") != candidate.get("name"):
            errors.append(f"{camera_id}: name mismatch")
        actual_stream = stream_id_from_url(item.get("directUrl") or item.get("url"))
        if actual_stream and actual_stream != stream_id and camera_id not in existing:
            errors.append(f"{camera_id}: catalog already points to {actual_stream}, refusing silent replacement")
        for coordinate in ("lat", "lng"):
            try:
                if abs(float(item.get(coordinate)) - float(candidate.get(coordinate))) > 0.001:
                    errors.append(f"{camera_id}: {coordinate} mismatch")
            except (TypeError, ValueError):
                errors.append(f"{camera_id}: missing {coordinate}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True, help="JSON list or {mappings: [...]} candidate file")
    parser.add_argument("--catalog", type=Path, default=Path("cctv_data.json"))
    parser.add_argument("--registry", type=Path, default=STREAM_MAPPING_REGISTRY_FILE)
    parser.add_argument("--promote", action="store_true", help="write verified candidates to the registry")
    args = parser.parse_args()

    candidates_payload = load_json(args.input, [])
    candidates = candidates_payload.get("mappings", []) if isinstance(candidates_payload, dict) else candidates_payload
    registry = load_json(args.registry, {"version": 1, "mappings": []})
    catalog = load_json(args.catalog, [])
    if not isinstance(candidates, list) or not isinstance(registry, dict) or not isinstance(catalog, list):
        print("invalid candidate, registry, or catalog JSON")
        return 1

    errors = validate_candidates(candidates, catalog, registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"AUDIT OK: {len(candidates)} candidate mapping(s)")
    if not args.promote:
        print("DRY RUN: no mapping was promoted; pass --promote after review")
        return 0

    by_camera = {str(item.get("camera_id")).upper(): item for item in registry.get("mappings", [])}
    for candidate in candidates:
        entry = dict(candidate)
        entry.pop("verified", None)
        entry.update({"locked": True, "status": "verified"})
        by_camera[str(entry["camera_id"]).upper()] = entry
    updated = dict(registry)
    updated["mappings"] = list(by_camera.values())
    errors = []
    merged_streams = {}
    for entry in updated["mappings"]:
        camera_id = str(entry.get("camera_id") or "").upper()
        stream_id = str(entry.get("stream_id") or "").upper()
        if not camera_id or not stream_id or entry.get("locked") is not True or entry.get("status") != "verified":
            errors.append(f"{camera_id or '<missing>'}: promoted entry is not locked/verified")
        if stream_id in merged_streams and merged_streams[stream_id] != camera_id:
            errors.append(f"{camera_id}: stream {stream_id} already belongs to {merged_streams[stream_id]}")
        merged_streams[stream_id] = camera_id
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    content = json.dumps(updated, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.registry.parent, delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    temp_path.replace(args.registry)
    print(f"PROMOTED: {len(candidates)} mapping(s) -> {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
