"""Question-level scoring and paper assembly.

Concept clusters (groups of semantically equivalent past questions) are scored with the
six-factor statistical model for every mark slot. Topic-level scores (from ranking/) are then
blended in by `apply_topic_scores`, so questions inherit the strength of their topic:

    priority score = TOPIC_SHARE x topic score + (1 - TOPIC_SHARE) x question score

Scores are ranking heuristics, not probabilities.
"""
from __future__ import annotations

import hashlib
import math
import random
from collections import Counter, defaultdict

from . import semantic
from .config import DEFAULT_THRESHOLDS, TOPIC_SHARE, WEIGHT_LABELS, long_categories
from .records import EXAM_LABEL, Corpus, Paper, topic_key  # noqa: F401  (re-exported)


# ------------------------------------------------------------------ helpers
def type_weight(paper_type: str, target: str) -> float:
    if paper_type == target:
        return 1.0
    if target == "SEMESTER":
        return 0.55  # CAT papers say something about what faculty think matters
    if paper_type == "SEMESTER":
        return 0.65
    return 0.5  # the other CAT (different units, so scope filtering does most of the work)


def cluster_key(texts: list[str]) -> str:
    return "c" + hashlib.md5("|".join(sorted(semantic.normalized_text(t) for t in texts)).encode()).hexdigest()[:10]


def confidence_level(n_relevant_papers: int, n_same_type: int) -> dict:
    if n_relevant_papers >= 6 and n_same_type >= 3:
        level, msg = "good", "Enough historical papers to see real patterns."
    elif n_relevant_papers >= 3:
        level, msg = "moderate", "Some history available - treat rankings as indicative."
    else:
        level, msg = "low", ("Very little history uploaded. Rankings lean mostly on the syllabus; "
                             "upload more previous papers to improve them.")
    return {"level": level, "message": msg, "papers": n_relevant_papers, "same_type_papers": n_same_type}


# ------------------------------------------------------------------ clustering
def build_clusters(corpus: Corpus) -> list[dict]:
    """Group paper + question-bank questions into concept clusters."""
    allq = [dict(q, _src="paper") for q in corpus.questions] + [dict(q, _src="bank") for q in corpus.bank_questions]
    if not allq:
        return []
    labels = semantic.cluster([q["text"] for q in allq], groups=[q.get("unit") for q in allq])
    groups: dict[int, list[dict]] = defaultdict(list)
    for q, lab in zip(allq, labels):
        groups[lab].append(q)
    clusters = []
    for members in groups.values():
        papers = [m for m in members if m["_src"] == "paper"]
        units = Counter(m.get("unit") for m in members if m.get("unit"))
        topics = Counter(m.get("topic") for m in members if m.get("topic"))
        clusters.append({
            "members": papers,
            "bank": [m for m in members if m["_src"] == "bank"],
            "unit": units.most_common(1)[0][0] if units else None,
            "topic": topics.most_common(1)[0][0] if topics else "",
        })
    return clusters


# ------------------------------------------------------------------ scoring
def score_candidates(corpus: Corpus, target: str, cfg: dict, weights: dict,
                     scope: list[int] | None = None, clusters: list[dict] | None = None) -> dict:
    """Rank every concept cluster (and untested syllabus topics) for the target exam.

    Returns {"candidates": [...], "confidence": {...}, "unit_stats": {...}}.
    Each candidate is scored separately for every mark slot of the target pattern.
    """
    tcfg = cfg[target]
    scope = set(scope or tcfg.get("units") or [])
    slots = sorted({s["marks_each"] for s in tcfg["sections"]})
    longs = long_categories(cfg)
    papers = {p.id: p for p in corpus.papers}
    t_latest = max((p.t for p in corpus.papers), default=0.0)
    w_total = sum(type_weight(p.exam_type, target) for p in corpus.papers) or 1.0
    n_same = sum(1 for p in corpus.papers if p.exam_type == target)

    clusters = clusters if clusters is not None else build_clusters(corpus)

    # ---- unit coverage: how much each in-scope unit appeared in the most recent relevant papers
    relevant = sorted([p for p in corpus.papers if type_weight(p.exam_type, target) >= 0.65 or p.exam_type == target],
                      key=lambda p: p.t)
    recent_ids = {p.id for p in relevant[-2:]}
    unit_counts_recent = Counter(q.get("unit") for q in corpus.questions
                                 if q["paper_id"] in recent_ids and q.get("unit") in scope)
    unit_counts_all = Counter(q.get("unit") for q in corpus.questions if q.get("unit") in scope)
    hours = {u["number"]: (u.get("hours") or 0) for u in corpus.units}
    if scope and all(hours.get(u) for u in scope):
        tot_h = sum(hours[u] for u in scope)
        expected = {u: hours[u] / tot_h for u in scope}
    else:
        expected = {u: 1 / len(scope) for u in scope} if scope else {}
    tot_recent = sum(unit_counts_recent.values())
    unit_factor = {}
    for u in scope:
        share = unit_counts_recent[u] / tot_recent if tot_recent else expected[u]
        unit_factor[u] = max(0.0, min(1.0, 0.5 + 2.0 * (expected[u] - share)))

    topic_breadth = Counter(c["topic"] for c in clusters if c["topic"])
    max_breadth = max(topic_breadth.values(), default=1)
    have_syllabus = bool(corpus.units)

    raw: list[dict] = []
    for c in clusters:
        unit = c["unit"]
        if scope and unit is not None and unit not in scope:
            continue
        mem = c["members"]
        if not mem and not c["bank"]:
            continue
        paper_ids = sorted({m["paper_id"] for m in mem}, key=lambda pid: papers[pid].t)
        weighted = sum(type_weight(papers[pid].exam_type, target) for pid in paper_ids)
        times = [papers[pid].t for pid in paper_ids]

        # Recency & repetition cycle
        cycle = None
        if times:
            gap = t_latest - times[-1]
            recent = math.exp(-gap / 1.5)
            if len(times) >= 2:
                intervals = [b - a for a, b in zip(times, times[1:]) if b - a > 0.05] or [1.0]
                cycle = sum(intervals) / len(intervals)
                expected_next = times[-1] + cycle
                # how "due" it is at the next exam (approx. half a year after the latest paper)
                due = math.exp(-abs((t_latest + 0.5) - expected_next) / max(cycle, 0.5))
                recency = 0.5 * recent + 0.5 * due
            else:
                recency = 0.6 * recent
        else:
            recency, cycle = 0.0, None

        # Syllabus importance
        bank_hits = len(c["bank"])
        if have_syllabus:
            base = 0.4 if c["topic"] else 0.12
            breadth = 0.25 * (topic_breadth[c["topic"]] / max_breadth) if c["topic"] else 0.0
            syl = base + breadth + 0.35 * min(1.0, bank_hits / 2)
        else:
            syl = 0.45 + 0.35 * min(1.0, bank_hits / 2)

        cats = Counter(m.get("category") for m in mem if m.get("category"))
        n_cat = sum(cats.values())
        distinct = []
        for m in mem:
            if not any(semantic.exact_match(m["text"], d) for d in distinct):
                distinct.append(m["text"])
        qtypes = {m.get("qtype") for m in mem}
        variation = min(1.0, (len(distinct) - 1) / 3) * 0.7 + min(1.0, (len(qtypes) - 1) / 2) * 0.3 if mem else 0.0

        exact_repeat = False
        for i in range(len(mem)):
            for j in range(i + 1, len(mem)):
                if mem[i]["paper_id"] != mem[j]["paper_id"] and semantic.exact_match(mem[i]["text"], mem[j]["text"]):
                    exact_repeat = True
        if not mem:
            evidence = "question_bank"
        elif exact_repeat:
            evidence = "exact_repeat"
        elif len(paper_ids) >= 2:
            evidence = "concept_repeat"
        else:
            evidence = "previously_asked"

        raw.append({
            "cluster": c, "paper_ids": paper_ids, "weighted": weighted, "recency": recency,
            "cycle": cycle, "syllabus": min(1.0, syl), "cats": cats, "n_cat": n_cat,
            "variation": variation, "evidence": evidence, "distinct": distinct, "bank_hits": bank_hits,
        })

    max_w = max((r["weighted"] for r in raw), default=1.0) or 1.0

    candidates: list[dict] = []
    for r in raw:
        c = r["cluster"]
        mem = c["members"]
        unit = c["unit"]
        freq = (r["weighted"] / max_w) ** 0.8 if r["weighted"] else 0.0
        ucov = unit_factor.get(unit, 0.4) if unit is not None else 0.35
        per_slot = {}
        for slot in slots:
            if r["n_cat"]:
                exact = r["cats"].get(slot, 0)
                related = sum(v for k, v in r["cats"].items() if k != slot and k in longs) if slot in longs else 0
                mpat = (exact + 0.6 * related) / r["n_cat"]
            else:
                mpat = 0.3
            factors = {"frequency": freq, "recency": r["recency"], "syllabus": r["syllabus"],
                       "unit_coverage": ucov, "marks_pattern": mpat, "variation": r["variation"]}
            score = 100 * sum(weights[k] * v for k, v in factors.items())
            per_slot[slot] = {"score": round(score, 1), "factors": {k: round(v, 3) for k, v in factors.items()}}

        # representative wording: most recent real question
        mem_sorted = sorted(mem, key=lambda m: papers[m["paper_id"]].t, reverse=True)
        rep = mem_sorted[0] if mem_sorted else c["bank"][0]
        appearances = [{
            "question_id": m.get("id"), "text": m["text"], "paper_id": m["paper_id"],
            "paper": papers[m["paper_id"]].label, "exam_type": papers[m["paper_id"]].exam_type,
            "year": papers[m["paper_id"]].year, "number": m.get("number", ""), "marks": m.get("category"),
        } for m in mem_sorted]
        cid = cluster_key([m["text"] for m in mem] or [rep["text"]])
        candidates.append({
            "id": cid,
            "topic_key": topic_key(unit, c["topic"]) if c["topic"] else cid,
            "text": rep["text"],
            "rep_by_slot": {slot: next((m["text"] for m in mem_sorted if m.get("category") == slot), None) for slot in slots},
            # most recent real wording of each kind, for slots the concept was never asked at
            "rep_short": next((m["text"] for m in mem_sorted if (m.get("category") or 0) <= 2), None),
            "rep_long": next((m["text"] for m in mem_sorted if (m.get("category") or 0) > 2), None),
            "unit": unit, "topic": c["topic"], "qtype": rep.get("qtype", "theory"),
            "evidence": r["evidence"],
            "slots": per_slot,
            "dominant_slot": (r["cats"].most_common(1)[0][0] if r["cats"] else None),
            "frequency": {
                "papers": len(r["paper_ids"]),
                "total_papers": len(corpus.papers),
                "by_type": dict(Counter(papers[p].exam_type for p in r["paper_ids"])),
                "weighted_share": round(r["weighted"] / w_total, 3),
            },
            "years": sorted({papers[p].year for p in r["paper_ids"] if papers[p].year}),
            "cycle_years": round(r["cycle"], 1) if r["cycle"] else None,
            "appearances": appearances,
            "bank_hits": r["bank_hits"],
            "variants": len(r["distinct"]),
        })

    # ---- syllabus topics that have never been asked: candidates for practice questions
    asked_topics = {c["topic"] for c in clusters if c["topic"] and c["members"]}
    for u in corpus.units:
        if scope and u["number"] not in scope:
            continue
        for topic in u.get("topics") or []:
            if topic in asked_topics:
                continue
            per_slot = {}
            for slot in slots:
                factors = {"frequency": 0.0, "recency": 0.0, "syllabus": 0.4 if have_syllabus else 0.3,
                           "unit_coverage": unit_factor.get(u["number"], 0.4),
                           "marks_pattern": 0.3, "variation": 0.0}
                per_slot[slot] = {"score": round(100 * sum(weights[k] * v for k, v in factors.items()), 1),
                                  "factors": factors}
            candidates.append({
                "id": cluster_key(["topic:" + topic]), "topic_key": topic_key(u["number"], topic),
                "text": "", "rep_by_slot": {},
                "unit": u["number"], "topic": topic, "qtype": "theory", "evidence": "practice_new",
                "slots": per_slot, "dominant_slot": None,
                "frequency": {"papers": 0, "total_papers": len(corpus.papers), "by_type": {}, "weighted_share": 0},
                "years": [], "cycle_years": None, "appearances": [], "bank_hits": 0, "variants": 0,
            })

    unit_stats = {u: {"recent_questions": unit_counts_recent[u], "all_questions": unit_counts_all[u],
                      "expected_share": round(expected[u], 3), "coverage_factor": round(unit_factor[u], 3)}
                  for u in sorted(scope)}
    return {
        "candidates": candidates,
        "confidence": confidence_level(sum(1 for p in corpus.papers if type_weight(p.exam_type, target) >= 0.55), n_same),
        "unit_stats": unit_stats,
        "slots": slots,
        "scope": sorted(scope),
        "clusters": clusters,
    }


def apply_topic_scores(scored: dict, topic_rows: list[dict]) -> dict:
    """Blend topic-level scores into every candidate's slot scores (in place)."""
    by_key = {r["key"]: r for r in topic_rows}
    for c in scored["candidates"]:
        row = by_key.get(c["topic_key"])
        ts = row["score"] if row else 0.0
        c["topic_score"] = ts
        c["topic_rank"] = row["rank"] if row else None
        c["topic_label"] = row["label"] if row else (c["topic"] or "")
        for slot in c["slots"].values():
            q = slot.get("question_score", slot["score"])
            slot["question_score"] = q
            slot["topic_score"] = ts
            slot["score"] = round(TOPIC_SHARE * ts + (1 - TOPIC_SHARE) * q, 1)
    scored["topics"] = topic_rows
    return scored


# ------------------------------------------------------------------ presentation
def priority_for(score: float, cfg: dict) -> str:
    th = cfg.get("priority_thresholds", DEFAULT_THRESHOLDS)
    if score >= th["very_high"]:
        return "very_high"
    if score >= th["high"]:
        return "high"
    if score >= th["moderate"]:
        return "moderate"
    return "lower"


PRIORITY_LABEL = {"very_high": "Very high priority", "high": "High priority",
                  "moderate": "Moderate priority", "lower": "Lower priority"}
EVIDENCE_LABEL = {
    "exact_repeat": "Exact repeat - asked word-for-word more than once",
    "concept_repeat": "Repeated concept - asked before with different wording",
    "previously_asked": "Asked once before",
    "question_bank": "From uploaded question bank / faculty list (not seen in a past paper)",
    "practice_new": "Practice question - generated from the syllabus, never asked in uploaded papers",
    "predicted_variation": "Predicted variation of a known question (generated wording)",
}


def reasons_for(c: dict, slot: int, cfg: dict) -> list[str]:
    f = c["slots"][slot]["factors"]
    out = []
    fr = c["frequency"]
    if fr["papers"]:
        types = ", ".join(f"{EXAM_LABEL.get(k, k)} ×{v}" for k, v in fr["by_type"].items())
        out.append(f"Asked in {fr['papers']} of {fr['total_papers']} uploaded papers ({types}).")
    if c["evidence"] == "exact_repeat":
        out.append("The same question has been repeated almost word-for-word.")
    elif c["variants"] > 1:
        out.append(f"Asked in {c['variants']} different wordings - expect a rephrased version.")
    if c["years"]:
        out.append(f"Last seen in {max(c['years'])}.")
    if c.get("cycle_years") and f["recency"] >= 0.5:
        cy = c["cycle_years"]
        every = f"{round(cy * 12)} months" if cy < 1 else f"{cy:g} year" + ("s" if cy != 1 else "")
        out.append(f"Tends to come back about every {every} and looks due.")
    if f["marks_pattern"] >= 0.7 and c["frequency"]["papers"]:
        out.append(f"Usually asked as a {slot}-mark question.")
    elif c["dominant_slot"] and c["dominant_slot"] != slot and c["frequency"]["papers"]:
        out.append(f"Mostly asked as a {c['dominant_slot']}-mark question; could appear as {slot} marks.")
    if f["unit_coverage"] >= 0.65 and c["unit"]:
        out.append(f"Unit {c['unit']} has been under-tested in recent papers.")
    if c["bank_hits"]:
        out.append("Listed in the uploaded question bank / faculty important questions.")
    if c["topic"] and f["syllabus"] >= 0.4:
        out.append(f"Maps to the syllabus topic \"{c['topic']}\".")
    if c["evidence"] == "practice_new":
        out.append("Never asked in the uploaded papers - included so syllabus coverage isn't ignored.")
    return out


def prep_advice(priority: str, slot: int, qtype: str) -> str:
    extra = {"diagram": " Practise the diagram until you can draw it from memory.",
             "numerical": " Solve 2-3 problems of this type with full steps.",
             "derivation": " Write out the derivation end-to-end at least twice.",
             "programming": " Write and dry-run the program by hand.",
             "comparison": " Prepare a comparison table with 6-8 points."}.get(qtype, "")
    if slot <= 2:
        base = {"very_high": "Must know - memorise a crisp 3-4 line answer.",
                "high": "Learn the definition and one key point.",
                "moderate": "Read once and note keywords.",
                "lower": "Skim if time permits."}[priority]
    else:
        base = {"very_high": "Prepare first: full structured answer with headings.",
                "high": "Prepare a complete answer outline and key points.",
                "moderate": "Know the main subheadings and a diagram.",
                "lower": "Revise the concept; prepare if time permits."}[priority]
    return base + extra


def practice_wording(topic: str, slot: int, qtype: str = "theory") -> str:
    if slot <= 2:
        return f"Define {topic} and state its significance."
    if slot >= 15:
        return f"Analyse {topic} in detail with a suitable example or case study, highlighting its design considerations."
    return f"Explain {topic} in detail with a neat diagram where applicable."


def variation_wording(text: str, slot: int, qtype: str) -> str:
    """A deterministic, rule-based rephrasing. Always labelled as generated."""
    core = semantic.RE_INSTR.sub("", text).strip(" .?:,").strip()
    core = core[0].lower() + core[1:] if core else text
    if slot <= 2:
        return f"What is meant by {core}?" if qtype != "comparison" else f"Differentiate: {core}."
    if qtype == "diagram":
        return f"With a neat sketch, describe {core}."
    if qtype in ("numerical", "programming"):
        return f"Solve a problem of the same kind with different values: {core}."
    return f"Discuss {core}, with suitable examples and a diagram where relevant."


def present(c: dict, slot: int, cfg: dict) -> dict:
    s = c["slots"][slot]
    pr = priority_for(s["score"], cfg)
    wording = "past"
    text = c["rep_by_slot"].get(slot)
    if not text:
        text = c.get("rep_short") if slot <= 2 else c.get("rep_long")
        if text and slot > 2:
            wording = "past_other_marks"
    if not text and c["text"]:
        # the concept was only ever asked in the other format (e.g. as a 2-marker): adapt the
        # wording, and say clearly that this wording is generated
        core = semantic.RE_INSTR.sub("", c["text"]).strip(" .?:,") or c["text"]
        text = practice_wording(c["topic"] or core, slot, c["qtype"])
        wording = "generated"
    if not text:
        text = practice_wording(c["topic"], slot, c["qtype"])
        wording = "generated"
    item = {
        "id": f"{c['id']}-{slot}",
        "cluster_id": c["id"],
        "text": text,
        "marks": slot,
        "unit": c["unit"],
        "topic": c["topic"],
        "qtype": c["qtype"],
        "score": s["score"],
        "question_score": s.get("question_score", s["score"]),
        "topic_score": s.get("topic_score"),
        "topic_rank": c.get("topic_rank"),
        "topic_key": c.get("topic_key"),
        "factors": s["factors"],
        "factor_labels": WEIGHT_LABELS,
        "priority": pr,
        "priority_label": PRIORITY_LABEL[pr],
        "evidence": c["evidence"],
        "evidence_label": EVIDENCE_LABEL[c["evidence"]],
        "frequency": c["frequency"],
        "years": c["years"],
        "appearances": c["appearances"],
        "reasons": reasons_for(c, slot, cfg),
        "prep": prep_advice(pr, slot, c["qtype"]),
        "wording": wording,
        "is_generated": wording == "generated",
        "variation": None,
    }
    if wording == "generated" and c["appearances"]:
        item["reasons"].insert(0, f"Wording is generated for a {slot}-mark slot: the concept was asked before "
                                  "(see previous appearances), but not in this form.")
    if c["appearances"] and wording != "generated":
        item["variation"] = {"text": variation_wording(text, slot, c["qtype"]),
                             "label": EVIDENCE_LABEL["predicted_variation"], "generated_by": "rules"}
    return item


def ranked_list(scored: dict, cfg: dict) -> list[dict]:
    """Flat list of best (candidate, slot) pairs - each concept appears once, under its best slot."""
    out = []
    for c in scored["candidates"]:
        best = max(c["slots"], key=lambda s: c["slots"][s]["score"]
                   + (5 if c["dominant_slot"] == s else 0)
                   + (-8 if c["dominant_slot"] and c["dominant_slot"] != s and (s <= 2) != (c["dominant_slot"] <= 2) else 0))
        out.append(present(c, best, cfg))
    out.sort(key=lambda x: (-x["score"], x["is_generated"]))
    return out


# ------------------------------------------------------------------ paper assembly
def _spread_units(scope: list[int], n: int) -> list[int | None]:
    if not scope or n < len(scope):
        return [None] * n  # e.g. a single Part C question: best concept from any unit
    return [scope[i * len(scope) // n] for i in range(n)]


def assemble_paper(scored: dict, target: str, cfg: dict, seed: int = 0,
                   unit_distribution: dict | None = None) -> dict:
    """Build a predicted paper following the configured sections.

    seed=0 picks the strict top candidates; other seeds sample from the high-scoring pool
    (softmax over scores) to give an alternative but still evidence-weighted set.
    """
    rng = random.Random(seed)
    tcfg = cfg[target]
    scope = scored.get("scope") or sorted(tcfg.get("units") or [])
    used: set[str] = set()
    sections_out = []
    qno = 1
    for sec in tcfg["sections"]:
        slot = sec["marks_each"]
        either = sec.get("choice") == "either_or"
        n = sec["count"]
        unit_plan = (unit_distribution or {}).get(sec["name"]) or _spread_units(scope, n)
        questions = []
        for i in range(n):
            unit = unit_plan[i] if i < len(unit_plan) else None
            picks = []
            for _ in range(2 if either else 1):
                pool = [c for c in scored["candidates"] if c["id"] not in used and slot in c["slots"]
                        and (unit is None or c["unit"] == unit)]
                if not pool:
                    pool = [c for c in scored["candidates"] if c["id"] not in used and slot in c["slots"]]
                if not pool:
                    break

                def eff(c):
                    s = c["slots"][slot]["score"]
                    # a concept that is clearly a 2-marker shouldn't fill a long slot (and vice versa)
                    if c["dominant_slot"] and (c["dominant_slot"] <= 2) != (slot <= 2):
                        s -= 15
                    return s

                pool.sort(key=eff, reverse=True)
                if seed:
                    top = pool[:8]
                    wts = [math.exp(eff(c) / 8.0) for c in top]
                    choice = rng.choices(top, weights=wts, k=1)[0]
                else:
                    choice = pool[0]
                used.add(choice["id"])
                picks.append(present(choice, slot, cfg))
            if not picks:
                continue
            questions.append({"number": qno, "unit": unit, "options": picks})
            qno += 1
        sections_out.append({
            "name": sec["name"], "title": sec["title"], "instruction": sec.get("instruction", ""),
            "marks_each": slot, "count": n, "choice": sec.get("choice", "none"),
            "total": slot * n, "questions": questions,
        })
    total = sum(s["total"] for s in sections_out)
    return {"exam_type": target, "label": tcfg.get("label", target), "duration": tcfg.get("duration", ""),
            "units": scope, "total_marks": total, "sections": sections_out, "seed": seed,
            "confidence": scored["confidence"]}
