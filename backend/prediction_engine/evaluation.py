"""Chronological, rolling-origin evaluation (no random splits, no future data).

For every dated paper P (in time order) that has at least MIN_HISTORY earlier dated papers:
  * the corpus is cut to papers strictly before P (question banks excluded: undated);
  * topics are ranked by each ranker, questions are selected, and both are compared to P.
The ML ranker at origin P is trained only on origins before P.

Reported per exam type and overall:
  Topic ranking:  Precision@K, Recall@K, NDCG@K (K = 5, 10 and R = topics actually asked)
  Questions:      exact question match rate, semantic topic match rate, unit coverage
Rankers:        frequency-only baseline, statistical, ML-assisted (when trainable).
"""
from __future__ import annotations

import copy
from collections import defaultdict

from . import metrics, semantic
from .config import MIN_HISTORY, normalize
from .predictor import apply_topic_scores, ranked_list, score_candidates
from .ranking import ml, statistical
from .records import Corpus, topic_key

FREQ_ONLY = {"frequency": 1.0, "recency": 0, "syllabus": 0, "unit_coverage": 0, "marks_pattern": 0, "variation": 0}
RELATED_SIM = 0.28


def question_match(preds: list[dict], hidden: list[dict], top_topic_keys: set[str]) -> dict:
    """Compare predicted questions (top-N) with the questions actually asked."""
    pred_texts, owner = [], []
    for i, p in enumerate(preds):
        for t in ([a["text"] for a in p["appearances"]] or [p["text"]]):
            pred_texts.append(t)
            owner.append(i)
    sim = semantic.similarity_matrix([h["text"] for h in hidden], pred_texts) if pred_texts and hidden else None
    rows, counts = [], {"exact": 0, "semantic": 0, "topic": 0, "miss": 0}
    for hi, h in enumerate(hidden):
        level, best_pred, best = "miss", None, 0.0
        if sim is not None:
            for k in range(len(pred_texts)):
                s = float(sim[hi, k])
                if semantic.exact_match(h["text"], pred_texts[k]) or s >= semantic.EXACT:
                    level, best_pred, best = "exact", owner[k], s
                    break
                if s > best:
                    best, best_pred = s, owner[k]
            if level != "exact":
                if best >= semantic.SAME_CONCEPT:
                    level = "semantic"
                elif h.get("topic") and topic_key(h.get("unit"), h["topic"]) in top_topic_keys:
                    level = "topic"
        counts[level] += 1
        rows.append({"text": h["text"], "marks": h.get("category"), "unit": h.get("unit"), "topic": h.get("topic", ""),
                     "match": level, "similarity": round(best, 2),
                     "predicted": preds[best_pred]["text"] if best_pred is not None and level in ("exact", "semantic") else None})
    n = len(hidden) or 1
    hidden_units = {h.get("unit") for h in hidden if h.get("unit")}
    pred_units = {p.get("unit") for p in preds if p.get("unit")}
    return {
        "exact_match_rate": round(counts["exact"] / n, 3),
        "semantic_topic_match_rate": round((counts["exact"] + counts["semantic"] + counts["topic"]) / n, 3),
        "unit_coverage": round(len(hidden_units & pred_units) / len(hidden_units), 3) if hidden_units else None,
        "counts": counts,
        "rows": rows,
    }


def _rank_with(unit: dict, weights: dict, have_syllabus: bool, bundle=None) -> list[dict]:
    rows = statistical.rank(copy.deepcopy(unit["rows"]), weights, have_syllabus)
    if bundle is not None:
        rows = ml.apply(bundle, rows)
    return rows


def _questions(unit: dict, cfg: dict, weights: dict, topic_rows: list[dict]) -> list[dict]:
    o = unit["origin"]
    scored = score_candidates(unit["train"], o.exam_type, cfg, weights, scope=unit["scope"], clusters=unit["clusters"])
    apply_topic_scores(scored, topic_rows)
    return ranked_list(scored, cfg)[: len(unit["hidden"])]


def build_units(corpus: Corpus, cfg: dict) -> list[dict]:
    return [ml.build_origin(corpus, o, cfg) for o in ml.evaluation_origins(corpus, cfg, MIN_HISTORY)]


def run(corpus: Corpus, cfg: dict, weights_for, include_ml: bool = True, units: list[dict] | None = None,
        detail: bool = True) -> dict:
    """weights_for: callable exam_type -> normalized weights (lets CAT 1/CAT 2/Semester differ)."""
    units = units if units is not None else build_units(corpus, cfg)
    have_syllabus = bool(corpus.units)
    ml_kind = ml.backend_available() if include_ml else None
    folds = []
    for i, u in enumerate(units):
        o = u["origin"]
        w = weights_for(o.exam_type)
        gains = u["gains"]
        res = {}
        rankers = {"frequency_baseline": (normalize(FREQ_ONLY), None), "statistical": (w, None)}
        if ml_kind:
            prior = units[:i]
            if len(prior) >= 3 and sum(r.get("y", 0) for p in prior for r in p["rows"]) >= 10:
                bundle = ml.fit(prior)
                if bundle is not None:
                    rankers["ml"] = (w, bundle)
        for name, (wts, bundle) in rankers.items():
            trows = _rank_with(u, wts, have_syllabus, bundle)
            keys = [r["key"] for r in trows]
            rep = metrics.ranking_report(keys, gains)
            r_k = max(1, rep["relevant_topics"])
            preds = _questions(u, cfg, wts, trows)
            qm = question_match(preds, u["hidden"], set(keys[:r_k]))
            rep.update({k: qm[k] for k in ("exact_match_rate", "semantic_topic_match_rate", "unit_coverage")})
            if detail and name == ("ml" if "ml" in rankers else "statistical"):
                res["rows"] = qm["rows"]
                res["top_topics"] = [{"label": r["label"], "unit": r["unit"], "score": r["score"],
                                      "asked": bool(gains.get(r["key"]))} for r in trows[:10]]
                res["missed_topics"] = [k.split(":", 2)[-1] for k, g in gains.items() if g and k not in set(keys[:r_k])][:10]
            res[name] = rep
        folds.append({"paper_id": o.id, "paper": o.label, "exam_type": o.exam_type, "year": o.year,
                      "train_papers": len(u["train"].papers), "hidden_questions": len(u["hidden"]),
                      "relevant_topics": res["statistical"]["relevant_topics"],
                      "novel_topics": res["statistical"]["novel_topics"], **res})

    def summarize(fs):
        out = {}
        for name in ("frequency_baseline", "statistical", "ml"):
            vals = [f[name] for f in fs if name in f]
            if not vals:
                continue
            keys = [k for k in vals[0] if isinstance(vals[0][k], (int, float)) and k not in ("relevant_topics", "novel_topics")]
            out[name] = {k: round(sum(v[k] for v in vals if v.get(k) is not None) /
                                  max(1, sum(1 for v in vals if v.get(k) is not None)), 3) for k in keys}
            out[name]["folds"] = len(vals)
        return out

    by_type = defaultdict(list)
    for f in folds:
        by_type[f["exam_type"]].append(f)
    return {
        "folds": folds,
        "summary": summarize(folds) if folds else None,
        "by_exam_type": {et: summarize(fs) for et, fs in by_type.items()},
        "enough_data": len(folds) >= 2,
        "ml_backend": ml_kind,
        "note": ("Rolling-origin evaluation: each paper is predicted using only papers dated before it (question "
                 "banks excluded). K=R means K equals the number of topics actually asked. Unmatched 'novel' topics "
                 "count against recall. These are measurements on your own uploads, not guarantees or probabilities."),
    }


WEIGHT_PRESETS = {
    "Balanced (default)": {"frequency": 0.25, "recency": 0.15, "syllabus": 0.20, "unit_coverage": 0.15, "marks_pattern": 0.15, "variation": 0.10},
    "History-heavy": {"frequency": 0.40, "recency": 0.20, "syllabus": 0.10, "unit_coverage": 0.10, "marks_pattern": 0.15, "variation": 0.05},
    "Repetition-cycle": {"frequency": 0.25, "recency": 0.35, "syllabus": 0.10, "unit_coverage": 0.10, "marks_pattern": 0.15, "variation": 0.05},
    "Syllabus-led": {"frequency": 0.15, "recency": 0.10, "syllabus": 0.35, "unit_coverage": 0.20, "marks_pattern": 0.15, "variation": 0.05},
    "Unit rotation": {"frequency": 0.20, "recency": 0.15, "syllabus": 0.15, "unit_coverage": 0.30, "marks_pattern": 0.15, "variation": 0.05},
    "Marks-pattern": {"frequency": 0.25, "recency": 0.10, "syllabus": 0.15, "unit_coverage": 0.10, "marks_pattern": 0.30, "variation": 0.10},
    "Frequency only": FREQ_ONLY,
}


def compare_weights(corpus: Corpus, cfg: dict, current: dict, exam_type: str | None = None) -> dict:
    """Evaluate the current weights and presets on the same rolling origins (statistical ranker)."""
    units = build_units(corpus, cfg)
    if exam_type:
        units_eval = [u for u in units if u["origin"].exam_type == exam_type]
    else:
        units_eval = units
    if not units_eval:
        return {"rows": [], "best": None, "folds": 0, "enough_data": False,
                "note": "Not enough dated papers to compare weightings (need at least 3 papers in time order)."}
    rows = []
    for name, w in {"Your current weights": current, **WEIGHT_PRESETS}.items():
        wn = normalize(w)
        res = run(corpus, cfg, lambda _et: wn, include_ml=False, units=units_eval, detail=False)
        sm = res["summary"]["statistical"]
        objective = 0.5 * sm["ndcg@R"] + 0.3 * sm["semantic_topic_match_rate"] + 0.2 * sm["recall@10"]
        rows.append({"name": name, "weights": wn, "objective": round(objective, 3),
                     **{k: sm[k] for k in ("precision@5", "recall@10", "ndcg@10", "ndcg@R", "exact_match_rate",
                                           "semantic_topic_match_rate", "unit_coverage")}})
    rows.sort(key=lambda r: -r["objective"])
    return {"rows": rows, "best": rows[0]["name"], "folds": len(units_eval), "enough_data": len(units_eval) >= 3,
            "note": ("Objective = 0.5 x NDCG@R + 0.3 x semantic topic match rate + 0.2 x Recall@10, averaged over "
                     "rolling origins. With few papers, differences of a few points are noise.")}
