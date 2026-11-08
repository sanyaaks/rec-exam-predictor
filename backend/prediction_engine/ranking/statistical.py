"""Statistical topic ranker: frequency- and recency-weighted six-factor score (0-100).

Used by default, and always when there is too little data for the ML ranker."""
from __future__ import annotations

import math


def topic_factors(row: dict, max_weighted: float, max_concepts: int, have_syllabus: bool) -> dict:
    f = row["features"]
    st = row["stats"]
    frequency = (row["weighted"] / max_weighted) ** 0.8 if row["weighted"] and max_weighted else 0.0
    if st["papers"] >= 2:
        recency = 0.5 * math.exp(-f["gap_years"] / 1.5) + 0.5 * f["due"]
    elif st["papers"] == 1:
        recency = 0.6 * math.exp(-f["gap_years"] / 1.5)
    else:
        recency = 0.0
    bank = min(1.0, row["bank_hits"] / 2)
    if have_syllabus:
        syllabus = (0.4 if not row["pseudo"] else 0.12) + 0.25 * min(1.0, st["concepts"] / max(max_concepts, 1)) + 0.35 * bank
    else:
        syllabus = 0.45 + 0.35 * bank
    marks = max(f["short_share"], f["long_share"]) if st["questions"] else 0.3
    variation = min(1.0, (st["variants"] - 1) / 3) if st["variants"] > 1 else 0.0
    return {"frequency": frequency, "recency": recency, "syllabus": min(1.0, syllabus),
            "unit_coverage": f["unit_cov"], "marks_pattern": marks, "variation": variation}


def rank(rows: list[dict], weights: dict, have_syllabus: bool) -> list[dict]:
    """Adds `score`, `factors` and `stat_score` to each row; returns rows sorted best-first."""
    max_w = max((r["weighted"] for r in rows), default=0.0) or 1.0
    max_c = max((r["stats"]["concepts"] for r in rows), default=1) or 1
    for r in rows:
        fac = topic_factors(r, max_w, max_c, have_syllabus)
        r["factors"] = {k: round(v, 3) for k, v in fac.items()}
        r["stat_score"] = round(100 * sum(weights[k] * v for k, v in fac.items()), 1)
        r["score"] = r["stat_score"]
    rows.sort(key=lambda r: (-r["score"], r["pseudo"], r["label"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows
