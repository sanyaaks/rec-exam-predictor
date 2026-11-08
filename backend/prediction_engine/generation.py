"""Question generation grounded in real syllabus topics and retrieved historical questions.

Retrieval: the past questions most similar to the topic (same unit preferred).
Generation:  an injected `llm_json(system, prompt, schema)` callable (the app supplies Claude);
             without it, deterministic templates are used.
Every output is labelled as generated, records which retrieved questions it was based on,
and is discarded if it simply duplicates a past question (that would blur the line between
historical evidence and AI output).
"""
from __future__ import annotations

from . import semantic
from .predictor import practice_wording, variation_wording

PROMPT_VERSION = "gen-v1"

SYSTEM = (
    "You write university examination practice questions for Anna University / Rajalakshmi Engineering College "
    "students. Stay strictly inside the given syllabus topic. Use the retrieved past questions only as style and "
    "scope references. Never copy a past question verbatim and never claim a question appeared in an exam."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "kind": {"type": "string", "enum": ["variation", "new_practice"]},
                    "question_type": {"type": "string", "enum": ["theory", "diagram", "numerical", "derivation",
                                                                  "programming", "comparison", "definition"]},
                    "based_on": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["text", "kind", "question_type", "based_on"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["questions"],
    "additionalProperties": False,
}


def retrieve(query: str, pool: list[dict], unit: int | None = None, k: int = 6) -> list[dict]:
    """Top-k past questions for a topic query; same-unit questions are preferred."""
    if not pool:
        return []
    sims = semantic.similarity_matrix([query], [p["text"] for p in pool])[0]
    scored = []
    for p, s in zip(pool, sims):
        bonus = 0.1 if unit is not None and p.get("unit") == unit else 0.0
        scored.append((float(s) + bonus, p))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], []
    for s, p in scored:
        if s < 0.12 or any(semantic.exact_match(p["text"], t) for t in seen):
            continue
        seen.append(p["text"])
        out.append({**p, "similarity": round(s, 3)})
        if len(out) >= k:
            break
    return out


def _dedupe_against_history(items: list[dict], retrieved: list[dict]) -> tuple[list[dict], list[dict]]:
    if not items:
        return [], []
    hist = [r["text"] for r in retrieved]
    sims = semantic.similarity_matrix([i["text"] for i in items], hist) if hist else None
    keep, dropped = [], []
    for n, it in enumerate(items):
        dup = None
        if sims is not None:
            for j, h in enumerate(hist):
                if semantic.exact_match(it["text"], h) or sims[n, j] >= semantic.EXACT:
                    dup = retrieved[j]
                    break
        if dup:
            dropped.append({**it, "reason": "Duplicates a past question", "duplicate_of": dup.get("id")})
        elif not any(semantic.exact_match(it["text"], k["text"]) for k in keep):
            keep.append(it)
    return keep, dropped


def generate(topic: str, unit: int | None, unit_title: str, marks: int, count: int, retrieved: list[dict],
             syllabus_topics: list[str], subject_name: str, llm_json=None) -> dict:
    count = max(1, min(count, 8))
    source, model_items = "template", []
    if llm_json is not None:
        refs = "\n".join(f"[{i}] ({r.get('paper', 'past paper')}, {r.get('marks') or '?'} marks) {r['text']}"
                         for i, r in enumerate(retrieved)) or "(no past questions on this topic)"
        prompt = (
            f"Subject: {subject_name}\nUnit {unit}: {unit_title}\nSyllabus topic: {topic}\n"
            f"Other topics in this unit: {', '.join(syllabus_topics[:20])}\n\n"
            f"Retrieved past questions (reference only):\n{refs}\n\n"
            f"Write {count} distinct {marks}-mark questions on the topic. Mix 'variation' items (a new wording or "
            f"angle on a retrieved question - list its index in based_on) and 'new_practice' items (cover an aspect "
            f"of the topic not yet asked - based_on may be empty). Match the depth expected for {marks} marks."
        )
        data = llm_json(SYSTEM, prompt, SCHEMA)
        if data and isinstance(data.get("questions"), list):
            source = "llm"
            for q in data["questions"][:count]:
                based = [retrieved[i]["id"] for i in q.get("based_on", []) if isinstance(i, int) and 0 <= i < len(retrieved)]
                model_items.append({"text": q["text"].strip(), "marks": marks, "kind": q.get("kind", "new_practice"),
                                    "qtype": q.get("question_type", "theory"), "based_on": based})
    if not model_items:
        source = "template"
        for r in retrieved[: max(0, count - 1)]:
            model_items.append({"text": variation_wording(r["text"], marks, r.get("qtype", "theory")), "marks": marks,
                                "kind": "variation", "qtype": r.get("qtype", "theory"), "based_on": [r.get("id")]})
        model_items.append({"text": practice_wording(topic, marks), "marks": marks, "kind": "new_practice",
                            "qtype": "theory", "based_on": []})
    keep, dropped = _dedupe_against_history(model_items, retrieved)
    for k in keep:
        k["source"] = source
    return {"questions": keep, "discarded": dropped, "source": source, "prompt_version": PROMPT_VERSION,
            "retrieved": [{"id": r.get("id"), "text": r["text"], "paper": r.get("paper"), "similarity": r["similarity"]}
                          for r in retrieved]}
