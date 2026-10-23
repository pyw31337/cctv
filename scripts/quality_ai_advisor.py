#!/usr/bin/env python3
"""Optional local Ollama advisor. It never changes stream mappings."""
from __future__ import annotations
import argparse, json, os, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path
from cctv_runtime import atomic_write_json
ROOT = Path(__file__).resolve().parents[1]
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(ROOT / "data" / "quality_policy.json")); parser.add_argument("--queue", default=str(ROOT / "data" / "quality_repair_queue.json")); parser.add_argument("--output", default=str(ROOT / "data" / "quality_ai_advice.json")); parser.add_argument("--model", default=os.environ.get("QUALITY_OLLAMA_MODEL", "qwen2.5vl:3b")); args = parser.parse_args()
    policy, queue = json.loads(Path(args.policy).read_text()), json.loads(Path(args.queue).read_text())
    output = {"schema": "cctv-quality-ai-advice-v1", "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "model": args.model, "advisory_only": True}
    prompt = "CCTV 운영 품질을 한국어 8개 이내 항목으로 요약하고 안전한 점검만 제안하세요. 카메라 ID나 URL 교체를 제안하지 마세요.\n" + json.dumps({"sources": policy.get("sources", {}), "repair_items": (queue.get("items") or [])[:80]}, ensure_ascii=False)
    if not shutil.which("ollama"): output.update({"status": "unavailable", "advice": "Ollama is not installed; deterministic quality policy remains active."})
    else:
        try: output.update({"status": "ok", "advice": subprocess.run(["ollama", "run", args.model, prompt], text=True, capture_output=True, timeout=120, check=True).stdout.strip()})
        except (subprocess.SubprocessError, OSError) as error: output.update({"status": "unavailable", "advice": f"Local AI unavailable: {error}"})
    atomic_write_json(Path(args.output), output, sort_keys=True); print(output["status"]); return 0
if __name__ == "__main__": raise SystemExit(main())
