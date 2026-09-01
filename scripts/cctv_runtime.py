"""Compatibility shim for direct `python scripts/*.py` execution.

The canonical runtime helpers live at the repository root. When a script
inside `scripts/` imports `cctv_runtime`, Python resolves modules relative to
the script directory first, so this shim loads the root module and re-exports
its public names.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "cctv_runtime.py"
SPEC = importlib.util.spec_from_file_location("_cctv_runtime_impl", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Could not load runtime helpers from {MODULE_PATH}")

_IMPL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_IMPL)

for _name, _value in vars(_IMPL).items():
    if not _name.startswith("_"):
        globals()[_name] = _value

__all__ = [name for name in vars(_IMPL) if not name.startswith("_")]
