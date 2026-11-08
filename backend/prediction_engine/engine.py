"""Public facade of the prediction engine.

    predict(...)            topic ranking -> question ranking for one exam type
    paper(...)              predicted paper following the exam pattern
    train(...)              fit + validate the optional ML ranker on rolling origins
    evaluate(...)           rolling-origin backtest (see evaluation.py)
    compare_prediction(...) feedback: stored prediction vs the actual paper

The app passes plain records (records.py) and receives plain dicts; there are no web or
database dependencies, so models can be improved without touching the frontend.
"""
from __future__ import annotations

from collections import defaultdict

from . import embeddings, evaluation, metrics, semantic
from .config import ML_GATE, scope_for
from .features import topic_table
from .predictor import (apply_topic_scores, assemble_paper, build_clusters, priority_for, ranked_list,
                        score_candidates)
from .ranking import ml, statistical
from .records import EXAM_LABEL, Corpus, topic_key

ENGINE_VERSION = "2.0.0"


def info() -> dict:
    return {"version": ENGINE_VERSION, "embeddings": embeddings.status(), "similarity": semantic.backend_name(),
            "ml_backend": ml.backend_available(), "ml_gate": ML_GATE}


def _topic_reasons(r: dict) -> list[str]:
    st, f = r["stats"], r["features"]
    out = []
    if st["papers"]:
        types = ", ".join(f"{EXAM_LABEL.get(k, k)} ×{v}" for k, v in st["by_type"].items())
        out.append(f"Appeared in {st['papers']} of {st['total_papers']} papers ({types}).")
        if st["last_year"]:
            out.append(f"Last asked in {st['last_year']}.")
        if f["due"] >= 0.5:
            out.append("Looks due based on how often it usually returns.")
    else:
        out.append("Not asked in the uploaded papers yet.")
    if f["unit_cov"] >= 0.65 and r["unit"]:
        out.append(f"Unit {r['unit']} has been under-tested recently.")
    if r["bank_hits"]:
        out.append("In the faculty question bank.")
    if r["pseudo"]:
        out.append("Not mapped to a syllabus topic - review it in the Review tab.")
    return out


def rank_topics(corpus: Corpus, target: str, cfg: dict, weights: dict, scope: list[int],
                clusters: list[dict], ml_bundle=None) -> list[dict]:
    rows = topic_table(corpus, target, scope, clusters)
    rows = statistical.rank(rows, weights, bool(corpus.units))
    if ml_bundle is not None:
        rows = ml.apply(ml_bundle, rows)
    for r in rows:
        r["priority"] = priority_for(r["score"], cfg)
        r["reasons"] = _topic_reasons(r)
    return rows


def _topic_out(r: dict) -> dict:
    return {k: r.get(k) for k in ("key", "label", "unit", "topic", "pseudo", "score", "stat_score", "ml_rank_score",
                                  "rank", "priority", "factors", "stats", "examples", "reasons", "bank_hits")}


def predict(corpus: Corpus, target: str, cfg: dict, weights: dict, scope_override: list[int] | None = None,
            ml_bundle=None) -> dict:
    scope = scope_for(cfg, target, scope_override)
    clusters = build_clusters(corpus)
    trows = rank_topics(corpus, target, cfg, weights, scope, clusters, ml_bundle)
    scored = score_candidates(corpus, target, cfg, weights, scope=scope, clusters=clusters)
    apply_topic_scores(scored, trows)
    items = ranked_list(scored, cfg)
    for it in items:
        it["ranker"] = "ml" if ml_bundle is not None else "statistical"
    return {"scored": scored, "items": items, "topics": [_topic_out(r) for r in trows], "scope": scope,
            "confidence": scored["confidence"], "unit_stats": scored["unit_stats"],
            "ranker": "ml" if ml_bundle is not None else "statistical"}


def paper(prediction: dict, target: str, cfg: dict, seed: int = 0) -> dict:
    p = assemble_paper(prediction["scored"], target, cfg, seed=seed)
    p["ranker"] = prediction["ranker"]
    p["topic_ranking"] = prediction["topics"][:40]      # snapshot for later feedback comparison
    return p


def evaluate(corpus: Corpus, cfg: dict, weights_for, include_ml: bool = True) -> dict:
    return evaluation.run(corpus, cfg, weights_for, include_ml=include_ml)


def train(corpus: Corpus, cfg: dict, weights_for) -> dict:
    """Fit the pooled ML topic ranker on all rolling origins and decide (gate + validation) if it may be used."""
    units = evaluation.build_units(corpus, cfg)
    dated = [p for p in corpus.papers if p.dated]
    # validation uses the semester weights as the statistical reference (pooled model)
    gate = ml.gate_and_validate(units, weights_for("SEMESTER"), bool(corpus.units), len(dated))
    bundle = ml.fit(units) if gate.get("backend") and units else None
    cutoff = max((p.t for p in dated), default=None)
    return {"bundle": bundle, "gate": gate, "train_paper_ids": sorted(p.id for p in dated),
            "train_cutoff_t": cutoff, "n_rows": sum(len(u["rows"]) for u in units), "origins": len(units)}


def compare_prediction(snapshot: dict, actual: list[dict]) -> dict:
    """Compare a stored predicted paper (made before the exam) with the questions actually asked."""
    items = [o for s in snapshot.get("sections", []) for q in s["questions"] for o in q["options"]]
    topics = snapshot.get("topic_ranking") or []
    keys = [t["key"] for t in topics]
    gains: dict[str, int] = defaultdict(int)
    texts, owner = [], []
    for i, it in enumerate(items):
        for t in ([a["text"] for a in it.get("appearances", [])] or [it["text"]]):
            texts.append(t)
            owner.append(i)
    sims = semantic.similarity_matrix([q["text"] for q in actual], texts) if texts and actual else None
    for n, q in enumerate(actual):
        if q.get("topic"):
            k = topic_key(q.get("unit"), q["topic"])
            gains[k if k in keys else "novel:" + k] += 1
            continue
        best = None
        if sims is not None:
            j = int(sims[n].argmax())
            if sims[n, j] >= semantic.SAME_CONCEPT:
                best = items[owner[j]].get("topic_key")
        gains[best if best in keys else f"novel:q{q.get('id')}"] += 1
    rep = metrics.ranking_report(keys, dict(gains))
    r_k = max(1, rep["relevant_topics"])
    qm = evaluation.question_match(items, actual, set(keys[:r_k]))
    return {**rep, **{k: qm[k] for k in ("exact_match_rate", "semantic_topic_match_rate", "unit_coverage", "counts")},
            "rows": qm["rows"], "predicted_questions": len(items), "actual_questions": len(actual)}
