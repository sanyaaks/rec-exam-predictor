"""Syllabus-based topic classification (configurable) and topic discovery.

Classification signals, strongest first:
  1. A student/admin-defined keyword for a topic appears in the question  -> source "keyword"
  2. The topic name itself appears in the question                          -> source "syllabus"
  3. Semantic similarity between question and topic text (+ unit title,
     keywords and subtopics)                                                -> source "syllabus"
Below `min_similarity` the question is left unmapped and sent to the review queue.

Discovery groups unmapped questions into candidate topics: BERTopic when installed and there
are enough questions, otherwise embedding/TF-IDF clustering labelled with class-based TF-IDF.
"""
from __future__ import annotations

import logging
import re
from collections import Counter

import numpy as np

from . import semantic

log = logging.getLogger(__name__)

DEFAULT_CLASSIFIER = {"min_similarity": 0.14, "keyword_score": 0.8, "name_match_score": 0.6}
GENERIC = {"introduction", "overview", "basics", "networks", "concepts", "applications", "types", "fundamentals"}


def subtopics_for(topic: str, meta: dict | None) -> list[str]:
    if meta and meta.get("subtopics"):
        return [s for s in meta["subtopics"] if s.strip()]
    m = re.search(r"\(([^)]+)\)", topic)
    return [s.strip() for s in re.split(r",|/|;", m.group(1)) if s.strip()] if m else []


_SMALL = {"of", "and", "the", "for", "in", "on", "to", "a", "an"}


def acronyms(topic: str) -> list[str]:
    """'Virtual LAN' -> VLAN, 'Quality of Service' -> QoS/QS, 'Domain Name System' -> DNS."""
    words = re.findall(r"[A-Za-z0-9]+", re.sub(r"\(.*?\)", "", topic))
    if len(words) < 2:
        return []
    def part(w, keep_small):
        if w.isupper() and len(w) > 1:
            return w
        if w.lower() in _SMALL:
            return w[0].lower() if keep_small else ""
        return w[0].upper()
    out = {"".join(part(w, False) for w in words), "".join(part(w, True) for w in words)}
    return [a for a in out if len(a) >= 2 and a.upper() != topic.upper()]


def topic_index(units: list[dict]) -> list[dict]:
    rows = []
    for u in units:
        meta_all = u.get("topic_meta") or {}
        for t in u.get("topics") or []:
            meta = meta_all.get(t) or {}
            kws = [k.strip() for k in meta.get("keywords", []) if k.strip()] + acronyms(t)
            subs = subtopics_for(t, meta)
            rows.append({"unit": u["number"], "topic": t, "keywords": kws, "subtopics": subs,
                         "text": " ".join([t, t, u.get("title", "")] + kws + subs)})
        if not u.get("topics") and u.get("title"):
            rows.append({"unit": u["number"], "topic": u["title"], "keywords": [], "subtopics": [], "text": u["title"]})
    return rows


def _phrase_in(phrase: str, text_l: str) -> bool:
    p = re.escape(phrase.lower().strip())
    return bool(p) and re.search(rf"(?<![a-z0-9]){p}(?![a-z0-9])", text_l) is not None


def _name_match_strength(topic: str) -> float:
    base = re.sub(r"\(.*?\)", "", topic).strip()
    if not base or base.lower() in GENERIC:
        return 0.0
    strong = len(base.split()) >= 2 or re.search(r"\d", base) or sum(c.isupper() for c in base) >= 2
    return 1.0 if strong else 0.0


def classify(questions: list[str], units: list[dict], allowed_units: list | None = None,
             unit_hints: list | None = None, cfg: dict | None = None) -> list[dict]:
    """One result per question: {unit, topic, subtopic, confidence, source, alternatives}."""
    cfg = {**DEFAULT_CLASSIFIER, **(cfg or {})}
    idx = topic_index(units)
    if not idx or not questions:
        return [{"unit": unit_hints[i] if unit_hints else None, "topic": "", "subtopic": "", "confidence": 0.0,
                 "source": "", "alternatives": []} for i in range(len(questions))]
    sim = semantic.similarity_matrix(questions, [r["text"] for r in idx])
    out = []
    for i, q in enumerate(questions):
        ql = q.lower()
        scores = sim[i].astype(float).copy()
        sources = ["syllabus"] * len(idx)
        for k, r in enumerate(idx):
            if any(_phrase_in(kw, ql) for kw in r["keywords"]):
                scores[k] = max(scores[k], cfg["keyword_score"])
                sources[k] = "keyword"
            elif _name_match_strength(r["topic"]) and _phrase_in(re.sub(r"\(.*?\)", "", r["topic"]).strip(), ql):
                scores[k] = max(scores[k], cfg["name_match_score"])
        hint = unit_hints[i] if unit_hints else None
        allowed = allowed_units[i] if allowed_units else None
        mask = np.ones(len(idx), dtype=bool)
        if hint:
            mask = np.array([r["unit"] == hint for r in idx])
        elif allowed:
            mask = np.array([r["unit"] in allowed for r in idx])
        if not mask.any():
            mask[:] = True
        scores[~mask] = -1
        order = np.argsort(-scores)
        alts = [{"unit": idx[k]["unit"], "topic": idx[k]["topic"], "score": round(float(scores[k]), 3)}
                for k in order[:3] if scores[k] > 0]
        j = int(order[0])
        conf = float(max(scores[j], 0))
        if conf < cfg["min_similarity"]:
            per_unit: dict[int, float] = {}
            for k, r in enumerate(idx):
                if mask[k]:
                    per_unit[r["unit"]] = max(per_unit.get(r["unit"], 0), sim[i, k])
            unit = hint
            if unit is None and per_unit:
                best_u = max(per_unit, key=per_unit.get)
                if per_unit[best_u] >= 0.08:
                    unit = best_u
                elif allowed and len(allowed) == 1:
                    unit = allowed[0]
            out.append({"unit": unit, "topic": "", "subtopic": "", "confidence": round(conf, 3), "source": "",
                        "alternatives": alts})
            continue
        r = idx[j]
        sub = ""
        if r["subtopics"]:
            hits = [s for s in r["subtopics"] if _phrase_in(s, ql)]
            if hits:
                sub = hits[0]
            else:
                ss = semantic.similarity_matrix([q], r["subtopics"])[0]
                if ss.max() >= 0.2:
                    sub = r["subtopics"][int(ss.argmax())]
        out.append({"unit": r["unit"], "topic": r["topic"], "subtopic": sub, "confidence": round(conf, 3),
                    "source": sources[j], "alternatives": alts})
    return out


# ------------------------------------------------------------------ discovery
def _ctfidf_labels(groups: list[list[str]], top_n: int = 4) -> list[list[str]]:
    from sklearn.feature_extraction.text import CountVectorizer

    docs = [" ".join(semantic.concept_text(t) for t in g) for g in groups]
    if not any(docs):
        return [[] for _ in groups]
    cv = CountVectorizer(ngram_range=(1, 2), token_pattern=r"[a-z0-9+#/]+")
    X = cv.fit_transform(docs).toarray().astype(float)
    tf = X / np.maximum(X.sum(axis=1, keepdims=True), 1)
    avg = X.sum() / len(groups)
    idf = np.log(1 + avg / np.maximum(X.sum(axis=0), 1))
    w = tf * idf
    vocab = np.array(cv.get_feature_names_out())
    labels = []
    for row in w:
        terms = []
        for k in np.argsort(-row):
            if row[k] <= 0 or len(terms) >= top_n:
                break
            t = vocab[k]
            if not any(t in x or x in t for x in terms):
                terms.append(t)
        labels.append(terms)
    return labels


def discover(questions: list[dict], units: list[dict], min_size: int = 2, method: str = "auto") -> dict:
    """Group unclassified questions into candidate topics for human review (nothing is applied automatically).

    questions: [{id, text, unit}]; method: auto | bertopic | builtin.
    Returns {"method", "topics": [{label, keywords, question_ids, unit, suggested_topic}], "unclustered": [ids]}.
    """
    if len(questions) < min_size:
        return {"method": "none", "topics": [], "unclustered": [q["id"] for q in questions]}
    texts = [q["text"] for q in questions]
    labels = None
    used = "embedding-clustering + c-TF-IDF"
    # BERTopic (UMAP + HDBSCAN) needs a reasonable number of documents; on small sets it over-merges,
    # so "auto" only uses it from 50 unclassified questions. "bertopic" forces it (needs >= 10).
    if (method == "auto" and len(questions) >= 50) or (method == "bertopic" and len(questions) >= 10):
        try:
            from bertopic import BERTopic
            from . import embeddings

            emb = embeddings.encode(texts)
            if emb is not None:
                model = BERTopic(min_topic_size=max(2, min_size), calculate_probabilities=False, verbose=False)
                labels, _ = model.fit_transform(texts, embeddings=emb)
                used = "BERTopic"
        except Exception as e:  # not installed / too few docs for UMAP
            log.info("BERTopic unavailable for discovery (%s); using built-in clustering", e)
            labels = None
    if labels is None:
        labels = semantic.cluster(texts, threshold=semantic.same_concept() - 0.07)
    groups: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        if lab == -1:
            continue
        groups.setdefault(int(lab), []).append(i)
    clusters = [g for g in groups.values() if len(g) >= min_size]
    clustered = {i for g in clusters for i in g}
    kw = _ctfidf_labels([[texts[i] for i in g] for g in clusters])
    idx = topic_index(units)
    topics = []
    for g, words in zip(clusters, kw):
        unit = Counter(questions[i].get("unit") for i in g if questions[i].get("unit")).most_common(1)
        unit = unit[0][0] if unit else None
        label = " / ".join(words[:3]).title() if words else texts[g[0]][:50]
        suggestion = None
        if idx:
            cand = [r for r in idx if unit is None or r["unit"] == unit] or idx
            s = semantic.similarity_matrix([" ".join(texts[i] for i in g)], [r["text"] for r in cand])[0]
            k = int(np.argmax(s))
            if s[k] >= 0.12:
                suggestion = {"unit": cand[k]["unit"], "topic": cand[k]["topic"], "score": round(float(s[k]), 3)}
        topics.append({"label": label, "keywords": words, "unit": unit, "suggested_topic": suggestion,
                       "question_ids": [questions[i]["id"] for i in g], "examples": [texts[i] for i in g[:4]]})
    topics.sort(key=lambda t: -len(t["question_ids"]))
    return {"method": used, "topics": topics,
            "unclustered": [questions[i]["id"] for i in range(len(questions)) if i not in clustered]}
