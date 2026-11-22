#!/usr/bin/env python3
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
now = datetime.now(timezone.utc)
source = ROOT / "cctv_data.json"
items = json.loads(source.read_text(encoding="utf-8"))
if not isinstance(items, list) or not items:
    raise RuntimeError("cctv_data.json has no persisted records")
ids = [str(item.get("id") or item.get("url") or "") for item in items]
unique = len(ids) == len(set(ids))
payload = {
    "schema": "lets_observability_v1", "run_id": f"cctv-{now.strftime('%Y%m%dT%H%M%SZ')}",
    "observed_at": now.isoformat(), "service_id": "cctv", "source": "persisted_cctv_catalog",
    "stages": {"collect": {"status": "success", "ok": len(items), "artifact": True}, "analyze": {"status": "not_started", "ok": None}, "quality": {"status": "success" if unique else "failed", "quality_issue_count": 0 if unique else len(items)-len(set(ids))}, "publish": {"status": "success", "artifact": True}},
    "counts": {"records": len(items)}, "artifacts": {"catalog": hashlib.sha256(source.read_bytes()).hexdigest()}, "note": "Persisted CCTV catalog snapshot."
}
out = ROOT / "data" / "observability" / "latest.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(f"CCTV records observed: {len(items)}")
