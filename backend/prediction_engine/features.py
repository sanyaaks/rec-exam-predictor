"""Topic-level features computed from a (training) corpus.

The caller is responsible for passing a corpus that only contains papers dated before the
cutoff (Corpus.before). Nothing in this module looks at the target paper, so the same
function produces training rows (for past origins) and serving rows (for the next exam).

Topic universe for a target exam:
  * every syllabus topic in the exam's units, and
  * every concept cluster that has no syllabus topic ("unmapped concept" pseudo-topics).
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

from . import semantic
from .predictor import build_clusters, cluster_key, type_weight
from .records import Corpus, topic_key

ML_FEATURES = [
    "n_hist", "freq_same", "freq_other", "freq_weighted", "count_log", "gap_years", "in_last_same",
    "in_last_any", "due", "cycle", "unit_cov", "hours_share", "short_share", "long_share",
    "n_concepts", "n_variants", "syllabus_mapped", "never_asked",
    "target_cat1", "target_cat2", "target_sem",
]


def _unit_factors(corpus: Corpus, target: str, scope: list[int]) -> tuple[dict, dict]:
    relevant = sorted([p for p in corpus.papers if type_weight(p.exam_type, target) >= 0.65], key=lambda p: p.t)
    recent_ids = {p.id for p in relevant[-2:]}
    recent = Counter(q.get("unit") for q in corpus.questions if q["paper_id"] in recent_ids and q.get("unit") in scope)
    hours = {u["number"]: (u.get("hours") or 0) for u in corpus.units}
    if scope and all(hours.get(u) for u in scope):
        tot = sum(hours[u] for u in scope)
        expected = {u: hours[u] / tot for u in scope}
    else:
        expected = {u: 1 / len(scope) for u in scope} if scope else {}
    tot_recent = sum(recent.values())
    factor = {}
    for u in scope:
        share = recent[u] / tot_recent if tot_recent else expected[u]
        factor[u] = max(0.0, min(1.0, 0.5 + 2.0 * (expected[u] - share)))
    return factor, expected


def topic_table(corpus: Corpus, target: str, scope: list[int], clusters: list[dict] | None = None) -> list[dict]:
    """One row per candidate topic with raw stats and ML features."""
    scope = list(scope)
    papers = {p.id: p for p in corpus.papers}
    clusters = clusters if clusters is not None else build_clusters(corpus)
    t_latest = max((p.t for p in corpus.papers), default=0.0)
    same = sorted([p for p in corpus.papers if p.exam_type == target], key=lambda p: p.t)
    other = [p for p in corpus.papers if p.exam_type != target]
    last_same = same[-1].id if same else None
    last_any = max(corpus.papers, key=lambda p: p.t).id if corpus.papers else None
    unit_factor, expected = _unit_factors(corpus, target, scope)
    w_total = sum(type_weight(p.exam_type, target) for p in corpus.papers) or 1.0

    rows: dict[str, dict] = {}

    def row_for(key, unit, topic, label, pseudo):
        if key not in rows:
            rows[key] = {"key": key, "unit": unit, "topic": topic, "label": label, "pseudo": pseudo,
                         "questions": [], "concepts": 0, "bank_hits": 0, "examples": []}
        return rows[key]

    for u in corpus.units:
        if scope and u["number"] not in scope:
            continue
        for t in u.get("topics") or []:
            row_for(topic_key(u["number"], t), u["number"], t, t, False)

    for c in clusters:
        unit = c["unit"]
        if scope and unit is not None and unit not in scope:
            continue
        members = c["members"]
        if c["topic"]:
            key = topic_key(unit, c["topic"])
            r = row_for(key, unit, c["topic"], c["topic"], False)
        else:
            texts = [m["text"] for m in members] or [b["text"] for b in c["bank"]]
            key = cluster_key(texts)
            r = row_for(key, unit, "", (texts[0][:70] if texts else "Unmapped concept"), True)
        r["questions"].extend(members)
        r["concepts"] += 1 if members else 0
        r["bank_hits"] += len(c["bank"])
        if members and len(r["examples"]) < 3:
            r["examples"].append(members[0]["text"])

    out = []
    max_concepts = max((r["concepts"] for r in rows.values()), default=1) or 1
    for r in rows.values():
        qs = r["questions"]
        pids = sorted({q["paper_id"] for q in qs}, key=lambda pid: papers[pid].t)
        times = [papers[p].t for p in pids]
        same_hits = sum(1 for p in pids if papers[p].exam_type == target)
        other_hits = len(pids) - same_hits
        weighted = sum(type_weight(papers[p].exam_type, target) for p in pids)
        gap = (t_latest - times[-1]) if times else 5.0
        cycle, due = 0.0, 0.0
        if len(times) >= 2:
            intervals = [b - a for a, b in zip(times, times[1:]) if b - a > 0.05] or [1.0]
            cycle = sum(intervals) / len(intervals)
            due = math.exp(-abs((t_latest + 0.5) - (times[-1] + cycle)) / max(cycle, 0.5))
        cats = Counter(q.get("category") for q in qs if q.get("category"))
        n_cat = sum(cats.values()) or 1
        distinct = []
        for q in qs:
            if not any(semantic.exact_match(q["text"], d) for d in distinct):
                distinct.append(q["text"])
        f = {
            "n_hist": len(corpus.papers),
            "freq_same": same_hits / len(same) if same else 0.0,
            "freq_other": other_hits / len(other) if other else 0.0,
            "freq_weighted": weighted / w_total,
            "count_log": math.log1p(len(qs)),
            "gap_years": min(gap, 5.0),
            "in_last_same": 1.0 if last_same in pids else 0.0,
            "in_last_any": 1.0 if last_any in pids else 0.0,
            "due": due,
            "cycle": cycle,
            "unit_cov": unit_factor.get(r["unit"], 0.4) if r["unit"] is not None else 0.35,
            "hours_share": expected.get(r["unit"], 0.0),
            "short_share": sum(v for k, v in cats.items() if k <= 2) / n_cat if qs else 0.0,
            "long_share": sum(v for k, v in cats.items() if k > 2) / n_cat if qs else 0.0,
            "n_concepts": r["concepts"] / max_concepts,
            "n_variants": min(len(distinct), 6) / 6,
            "syllabus_mapped": 0.0 if r["pseudo"] else 1.0,
            "never_asked": 0.0 if qs else 1.0,
            "target_cat1": 1.0 if target == "CAT1" else 0.0,
            "target_cat2": 1.0 if target == "CAT2" else 0.0,
            "target_sem": 1.0 if target == "SEMESTER" else 0.0,
        }
        by_type = Counter(papers[p].exam_type for p in pids)
        out.append({
            "key": r["key"], "unit": r["unit"], "topic": r["topic"], "label": r["label"], "pseudo": r["pseudo"],
            "features": f, "bank_hits": r["bank_hits"], "weighted": weighted,
            "stats": {"papers": len(pids), "total_papers": len(corpus.papers), "questions": len(qs),
                      "by_type": dict(by_type), "years": sorted({papers[p].year for p in pids if papers[p].year}),
                      "last_year": max((papers[p].year for p in pids if papers[p].year), default=None),
                      "concepts": r["concepts"], "variants": len(distinct)},
            "examples": r["examples"],
        })
    return out


def label_keys(hidden: list[dict], rows: list[dict], train_clusters: list[dict], scope: list[int]) -> dict[str, int]:
    """Which candidate topics actually appeared in a (hidden) paper, with question counts as gains.

    Mapped questions use their syllabus topic. Unmapped questions are matched to a training
    pseudo-topic by semantic similarity; anything else counts as a 'novel:' topic that no
    ranking could have retrieved (kept so recall is not overstated).
    """
    keys = {r["key"] for r in rows}
    gains: dict[str, int] = defaultdict(int)
    pseudo = [(cluster_key([m["text"] for m in c["members"]] or [b["text"] for b in c["bank"]]), c)
              for c in train_clusters if not c["topic"] and c["members"]]
    unmapped = [q for q in hidden if not q.get("topic")]
    sims = None
    member_texts, owner = [], []
    for k, c in pseudo:
        for m in c["members"]:
            member_texts.append(m["text"])
            owner.append(k)
    if unmapped and member_texts:
        sims = semantic.similarity_matrix([q["text"] for q in unmapped], member_texts)
    ui = 0
    for q in hidden:
        if q.get("topic"):
            k = topic_key(q.get("unit"), q["topic"])
            gains[k if k in keys else "novel:" + k] += 1
            continue
        best_k = None
        if sims is not None:
            j = int(sims[ui].argmax())
            if sims[ui, j] >= semantic.SAME_CONCEPT and owner[j] in keys:
                best_k = owner[j]
        gains[best_k or f"novel:q{q.get('id')}"] += 1
        ui += 1
    return dict(gains)
