"""App <-> prediction engine adapter: builds engine records from the database and picks the ranker."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

import prediction_engine as engine
from prediction_engine import registry

from .. import models
from ..config import DATA_DIR
from . import pipeline
from .exam_config import merged_config, normalized_weights

MODEL_DIR = DATA_DIR / "models"


def weights_for(subject: models.Subject):
    return lambda et: normalized_weights(subject.weights, et)


def active_model(db: Session, subject: models.Subject) -> models.ModelVersion | None:
    return (db.query(models.ModelVersion).filter_by(subject_id=subject.id, status="active")
            .order_by(models.ModelVersion.version.desc()).first())


@lru_cache(maxsize=32)
def _load(path: str, mtime: float):
    return registry.load(path)


def load_bundle(mv: models.ModelVersion | None):
    if not mv or not mv.artifact_path:
        return None
    f = Path(mv.artifact_path) / "model.joblib"
    return _load(mv.artifact_path, f.stat().st_mtime) if f.exists() else None


def model_staleness(db: Session, subject: models.Subject, mv: models.ModelVersion | None) -> dict:
    corpus = pipeline.load_corpus(db, subject)
    dated = {p.id for p in corpus.papers if p.dated}
    if not mv:
        return {"new_papers": len(dated)}
    return {"new_papers": len(dated - set(mv.train_paper_ids or [])),
            "removed_papers": len(set(mv.train_paper_ids or []) - dated)}


def ranker_choice(db: Session, subject: models.Subject, exam_type: str) -> tuple[object, dict]:
    """Which topic ranker to use for this exam type, and why."""
    cfg = merged_config(subject.exam_config)
    mode = cfg.get(exam_type, {}).get("ranker", "auto")
    mv = active_model(db, subject)
    info = {"mode": mode, "used": "statistical", "model_version": None, "reason": ""}
    if mode == "statistical":
        info["reason"] = "Statistical ranking selected in Settings."
        return None, info
    if mv is None:
        info["reason"] = ("No validated ML model for this subject yet - train one in the Accuracy tab. "
                          "Using statistical ranking (frequency, recency, syllabus, unit rotation).")
        return None, info
    bundle = load_bundle(mv)
    if bundle is None:
        info["reason"] = "Model file missing - retrain. Using statistical ranking."
        return None, info
    info.update(used="ml", model_version=mv.version, model_version_id=mv.id,
                reason=mv.gate.get("reason", "Validated ML-assisted ranking."))
    stale = model_staleness(db, subject, mv)
    if stale.get("new_papers") or stale.get("removed_papers"):
        info["stale"] = stale
    return bundle, info


def run_predict(db: Session, subject: models.Subject, exam_type: str, units: list[int] | None = None):
    cfg = merged_config(subject.exam_config)
    bundle, rinfo = ranker_choice(db, subject, exam_type)
    pred = engine.predict(pipeline.load_corpus(db, subject), exam_type, cfg, normalized_weights(subject.weights, exam_type),
                          scope_override=units, ml_bundle=bundle)
    return pred, rinfo, cfg
