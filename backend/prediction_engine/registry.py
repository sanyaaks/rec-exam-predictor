"""Versioned model artifacts on disk: <root>/<namespace>/v<N>/{model.joblib, meta.json}.

The app records each version in its database too; this module only owns the files.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib


def save(root: str | Path, namespace: str, bundle: dict | None, meta: dict) -> tuple[int, str]:
    base = Path(root) / namespace
    base.mkdir(parents=True, exist_ok=True)
    existing = [int(p.name[1:]) for p in base.glob("v*") if p.name[1:].isdigit()]
    version = max(existing, default=0) + 1
    d = base / f"v{version}"
    d.mkdir()
    if bundle is not None:
        joblib.dump(bundle, d / "model.joblib")
    meta = {**meta, "version": version, "saved_at": datetime.now(timezone.utc).isoformat()}
    (d / "meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    return version, str(d)


def load(path: str | Path) -> dict | None:
    f = Path(path) / "model.joblib"
    return joblib.load(f) if f.exists() else None
