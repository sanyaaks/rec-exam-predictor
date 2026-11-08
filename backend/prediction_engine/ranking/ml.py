"""Optional supervised topic ranker (LightGBM, or XGBoost if LightGBM is missing).

Training data comes from rolling origins: for every dated past paper P with enough history,
features are computed from papers strictly before P and the label says whether each topic
appeared in P. The model is pooled across exam types (target-type indicator features) because
any single exam type rarely has enough papers on its own.

The model is only used when the data gate passes AND it beats the statistical ranker on later,
held-out origins. Its output is shown as a rank-based score, never as a probability.
"""
from __future__ import annotations

import copy
import logging

import numpy as np

from .. import metrics
from ..config import ML_GATE, MIN_HISTORY, scope_for
from ..features import ML_FEATURES, label_keys, topic_table
from ..predictor import build_clusters
from ..records import Corpus, Paper
from . import statistical

log = logging.getLogger(__name__)
ML_BLEND = 0.5   # topic score = (1 - ML_BLEND) x statistical + ML_BLEND x ML rank score


def backend_available() -> str | None:
    try:
        import lightgbm  # noqa: F401
        return "lightgbm"
    except ImportError:
        pass
    try:
        import xgboost  # noqa: F401
        return "xgboost"
    except ImportError:
        return None


def evaluation_origins(corpus: Corpus, cfg: dict, min_history: int = MIN_HISTORY) -> list[Paper]:
    dated = sorted([p for p in corpus.papers if p.dated and p.exam_type in cfg], key=lambda p: p.t)
    return [p for p in dated if sum(1 for q in dated if q.t < p.t - 1e-6) >= min_history]


def build_origin(corpus: Corpus, origin: Paper, cfg: dict) -> dict:
    """Leakage-free training/evaluation unit for one past paper."""
    train = corpus.before(origin.t)               # strictly earlier, no question banks
    scope = scope_for(cfg, origin.exam_type, origin.units_covered or None)
    clusters = build_clusters(train)
    rows = topic_table(train, origin.exam_type, scope, clusters)
    hidden = [q for q in corpus.questions if q["paper_id"] == origin.id]
    gains = label_keys(hidden, rows, clusters, scope)
    for r in rows:
        r["y"] = 1 if gains.get(r["key"]) else 0
    return {"origin": origin, "train": train, "scope": scope, "clusters": clusters, "rows": rows,
            "gains": gains, "hidden": hidden}


def _xy(rows: list[dict]):
    X = np.array([[r["features"][f] for f in ML_FEATURES] for r in rows], dtype=float)
    y = np.array([r.get("y", 0) for r in rows], dtype=int)
    return X, y


def fit(units: list[dict], seed: int = 0):
    rows = [r for u in units for r in u["rows"]]
    if not rows:
        return None
    X, y = _xy(rows)
    if y.min() == y.max():
        return None
    kind = backend_available()
    if kind == "lightgbm":
        import lightgbm as lgb
        model = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.05, num_leaves=15, min_child_samples=5,
                                   subsample=0.9, subsample_freq=1, colsample_bytree=0.9, reg_lambda=1.0,
                                   random_state=seed, verbose=-1)
    elif kind == "xgboost":
        import xgboost as xgb
        model = xgb.XGBClassifier(n_estimators=150, learning_rate=0.05, max_depth=4, subsample=0.9,
                                  colsample_bytree=0.9, random_state=seed, eval_metric="logloss")
    else:
        return None
    model.fit(X, y)
    return {"model": model, "kind": kind, "features": list(ML_FEATURES)}


def raw_scores(bundle, rows: list[dict]) -> np.ndarray:
    if not rows:
        return np.zeros(0)
    X = np.array([[r["features"].get(f, 0.0) for f in bundle["features"]] for r in rows], dtype=float)
    return bundle["model"].predict_proba(X)[:, 1]


def apply(bundle, rows: list[dict]) -> list[dict]:
    """Blend ML rank scores into statistically ranked rows (rows must already have stat_score)."""
    raw = raw_scores(bundle, rows)
    if len(rows) == 0:
        return rows
    order = np.argsort(np.argsort(raw))               # 0 = worst
    pct = 100.0 * order / max(len(rows) - 1, 1)
    for r, s, p in zip(rows, raw, pct):
        r["ml_rank_score"] = round(float(p), 1)
        r["ml_raw"] = float(s)
        r["score"] = round((1 - ML_BLEND) * r["stat_score"] + ML_BLEND * p, 1)
    rows.sort(key=lambda r: (-r["score"], r["pseudo"], r["label"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _ranked_keys(rows):
    return [r["key"] for r in rows]


def gate_and_validate(units: list[dict], weights: dict, have_syllabus: bool, n_dated_papers: int) -> dict:
    """Decide whether the ML ranker may be used, with the evidence for the decision."""
    kind = backend_available()
    positives = sum(r.get("y", 0) for u in units for r in u["rows"])
    info = {"backend": kind, "origins": len(units), "positives": positives, "dated_papers": n_dated_papers,
            "gate": dict(ML_GATE), "use_ml": False}
    if kind is None:
        info["reason"] = "No ML library installed (pip install lightgbm). Using statistical ranking."
        return info
    if n_dated_papers < ML_GATE["min_dated_papers"] or len(units) < ML_GATE["min_origins"] or positives < ML_GATE["min_positives"]:
        info["reason"] = (f"Not enough history for a reliable ML model (need at least {ML_GATE['min_dated_papers']} dated "
                          f"papers, {ML_GATE['min_origins']} evaluation origins and {ML_GATE['min_positives']} topic "
                          f"appearances; have {n_dated_papers}, {len(units)}, {positives}). Using statistical ranking.")
        return info
    n_val = max(ML_GATE["min_val_origins"], round(len(units) / 3))
    val = []
    for i in range(len(units) - n_val, len(units)):
        bundle = fit(units[:i])
        if bundle is None:
            continue
        stat_rows = statistical.rank(copy.deepcopy(units[i]["rows"]), weights, have_syllabus)
        ml_rows = apply(bundle, copy.deepcopy(stat_rows))
        g = units[i]["gains"]
        k = max(1, sum(1 for v in g.values() if v))
        val.append({"paper": units[i]["origin"].label,
                    "statistical_ndcg": round(metrics.ndcg_at_k(_ranked_keys(stat_rows), g, k), 3),
                    "ml_ndcg": round(metrics.ndcg_at_k(_ranked_keys(ml_rows), g, k), 3)})
    info["validation"] = val
    if len(val) < ML_GATE["min_val_origins"]:
        info["reason"] = "Could not validate the ML model on enough held-out papers. Using statistical ranking."
        return info
    s = sum(v["statistical_ndcg"] for v in val) / len(val)
    m = sum(v["ml_ndcg"] for v in val) / len(val)
    info.update(statistical_ndcg=round(s, 3), ml_ndcg=round(m, 3))
    if m >= s + ML_GATE["min_gain"]:
        info["use_ml"] = True
        info["reason"] = f"ML-assisted ranking beat statistical ranking on {len(val)} held-out papers (NDCG@R {m:.3f} vs {s:.3f})."
    else:
        info["reason"] = (f"ML did not beat statistical ranking on held-out papers (NDCG@R {m:.3f} vs {s:.3f}). "
                          "Using statistical ranking.")
    return info
