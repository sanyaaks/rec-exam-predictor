"""Semantic matching: recognise questions that ask the same concept in different words.

Two similarity signals:
  * Lexical baseline (always on): TF-IDF word uni/bi-grams on concept terms + character
    n-grams + weighted key-term overlap. Cheap, transparent, no downloads.
  * Sentence-BERT (all-MiniLM-L6-v2) when available - catches paraphrases with no shared words.
The final similarity blends both; a mismatch of specific technical terms (IPv4 vs IPv6) is penalised.

Instruction words ("explain", "draw and explain", "with a neat diagram") are stripped
before comparison so that the *concept* is compared, not the phrasing.
"""
from __future__ import annotations

import logging
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from . import embeddings

log = logging.getLogger(__name__)

INSTRUCTION_PHRASES = [
    r"with (a )?neat (sketch|diagram)s?", r"with (suitable |an? )?examples?", r"with (a )?suitable diagram",
    r"in detail", r"briefly", r"in brief", r"neatly", r"write (short |a short )?notes? on", r"short notes? on",
    r"draw and explain", r"explain (in detail )?(about )?", r"describe", r"discuss", r"elaborate( on)?",
    r"illustrate", r"outline", r"what (is|are) (meant by|the)?", r"what do you (mean|understand) by",
    r"define", r"state", r"list (out )?(the )?", r"mention", r"give (an? )?(account of)?", r"write about",
    r"draw", r"sketch", r"enumerate", r"justify", r"how (does|do|is|are|can)", r"why (is|are|do|does)",
    r"bring out", r"highlight", r"summarize", r"examine", r"analy[sz]e", r"identify", r"name",
]
STOP = set("""a an the of in on for to and or with its it is are be by as at from that this these those
which what how why when where who whom your you their there various any each all some two three
four five six seven eight nine ten its into using use used between suitable example examples neat
diagram diagrams detail briefly also its can do does give write short note notes about one types
type different important main""".split())
RE_INSTR = re.compile(r"\b(" + "|".join(INSTRUCTION_PHRASES) + r")\b", re.I)


# Exam-language near-synonyms (subject independent): "architecture of X", "structure of X",
# "X header format" all ask for the same thing.
SYNONYMS = {
    **dict.fromkeys(["architecture", "structure", "format", "formats", "organization", "organisation",
                     "layout", "header", "headers", "anatomy"], "structure"),
    **dict.fromkeys(["working", "operation", "operations", "functioning", "mechanism", "works"], "working"),
    **dict.fromkeys(["advantages", "merits", "benefits", "pros"], "advantages"),
    **dict.fromkeys(["disadvantages", "demerits", "limitations", "drawbacks", "cons"], "limitations"),
    **dict.fromkeys(["types", "classification", "classify", "kinds", "categories"], "types"),
    **dict.fromkeys(["functions", "function", "role", "roles", "purpose", "significance", "need", "use", "uses"], "role"),
    **dict.fromkeys(["algorithm", "algorithms"], "algorithm"),
    **dict.fromkeys(["protocols"], "protocol"),
    **dict.fromkeys(["packets", "datagram", "datagrams"], "packet"),
}


def concept_text(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\(\s*\d{1,2}\s*\)", " ", t)
    t = RE_INSTR.sub(" ", t)
    t = re.sub(r"[^a-z0-9+#/ ]+", " ", t)
    words, seen = [], set()
    for w in t.split():
        if w in STOP or len(w) <= 1:
            continue
        w = SYNONYMS.get(w, w)
        if w and w not in seen:
            seen.add(w)
            words.append(w)
    return " ".join(words)


def normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def backend_name() -> str:
    st = embeddings.status()
    return f"Sentence-BERT ({st['model']}) + TF-IDF" if st["sbert"] else "TF-IDF hybrid (local baseline)"


def _key_terms(text: str) -> dict[str, float]:
    """Concept terms with weights: acronyms / alphanumeric terms (IPv6, CSMA/CD, 802.11) count double."""
    out: dict[str, float] = {}
    original = {re.sub(r"[^a-z0-9+#/]", "", w.lower()): w for w in text.split()}
    for w in concept_text(text).split():
        raw = original.get(w, w)
        strong = bool(re.search(r"\d", w)) or (sum(ch.isupper() for ch in raw) >= 2) or "/" in w
        out[w] = 2.0 if strong else 1.0
    return out


def _overlap_matrix(texts_a: list[str], texts_b: list[str]) -> np.ndarray:
    ka = [_key_terms(t) for t in texts_a]
    kb = [_key_terms(t) for t in texts_b]
    m = np.zeros((len(ka), len(kb)))
    mismatch = np.zeros((len(ka), len(kb)), dtype=bool)
    for i, a in enumerate(ka):
        if not a:
            continue
        wa = sum(a.values())
        sa = {k for k, v in a.items() if v > 1}
        for j, b in enumerate(kb):
            if not b:
                continue
            shared = sum(min(a[k], b[k]) for k in a.keys() & b.keys())
            if shared:
                m[i, j] = shared / min(wa, sum(b.values()))
            sb = {k for k, v in b.items() if v > 1}
            # both name specific technical terms (IPv4 vs IPv6, CSMA/CD vs CSMA/CA) and share none
            mismatch[i, j] = bool(sa and sb and not (sa & sb))
    return m, mismatch


def lexical_similarity(texts_a: list[str], texts_b: list[str] | None = None) -> np.ndarray:
    """TF-IDF baseline similarity in [0, 1] (no technical-term penalty applied)."""
    return _lexical(texts_a, texts_a if texts_b is None else texts_b)[0]


# SBERT cosine for same-domain but unrelated questions sits around 0.2-0.35 with MiniLM;
# paraphrases sit around 0.6-0.9. Rescale so both signals share a similar range.
# Calibrated on must-merge / must-separate question pairs (tests/test_engine.py): MiniLM alone
# over-rates short questions sharing a protocol name (e.g. "TCP congestion control" vs "TCP
# connection management" = 0.82), so it is a 30% signal on top of the lexical baseline.
SBERT_FLOOR, SBERT_SPAN = 0.30, 0.40
SBERT_WEIGHT = 0.3


def _lexical(texts_a, texts_b):
    ca = [concept_text(t) or normalized_text(t) for t in texts_a]
    cb = [concept_text(t) or normalized_text(t) for t in texts_b]
    corpus = ca + cb
    word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, token_pattern=r"[a-z0-9+#/]+")
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    try:
        W = word.fit_transform(corpus)
        sw = cosine_similarity(W[: len(ca)], W[len(ca):])
    except ValueError:
        sw = np.zeros((len(ca), len(cb)))
    C = char.fit_transform(corpus)
    sc = cosine_similarity(C[: len(ca)], C[len(ca):])
    so, mismatch = _overlap_matrix(texts_a, texts_b)
    return np.clip(0.45 * sw + 0.25 * sc + 0.30 * so, 0, 1), mismatch


def sbert_similarity(texts_a: list[str], texts_b: list[str] | None = None) -> np.ndarray | None:
    ea = embeddings.encode(list(texts_a))
    if ea is None:
        return None
    eb = ea if texts_b is None else embeddings.encode(list(texts_b))
    return np.clip(((ea @ eb.T) - SBERT_FLOOR) / SBERT_SPAN, 0, 1)


def similarity_matrix(texts_a: list[str], texts_b: list[str] | None = None) -> np.ndarray:
    """Concept similarity in [0, 1]: lexical baseline blended with SBERT when available."""
    sym = texts_b is None
    texts_b = texts_a if texts_b is None else texts_b
    if not texts_a or not texts_b:
        return np.zeros((len(texts_a), len(texts_b)))
    lex, mismatch = _lexical(texts_a, texts_b)
    sb = sbert_similarity(texts_a, None if sym else texts_b)
    sim = lex if sb is None else (1 - SBERT_WEIGHT) * lex + SBERT_WEIGHT * sb
    return np.clip(sim * np.where(mismatch, 0.5, 1.0), 0, 1)


def exact_match(a: str, b: str) -> bool:
    na, nb = normalized_text(a), normalized_text(b)
    if na == nb:
        return True
    sa, sb = set(na.split()), set(nb.split())
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= 0.85


# Thresholds (tuned on the bundled sample papers; see tests/)
SAME_CONCEPT_LEXICAL = 0.37   # same concept, possibly different wording (TF-IDF only)
SAME_CONCEPT_SBERT = 0.51     # same, when SBERT is blended in
EXACT = 0.85                  # near-verbatim repeat


def same_concept() -> float:
    return SAME_CONCEPT_SBERT if embeddings.available() else SAME_CONCEPT_LEXICAL


def __getattr__(name):  # keep `semantic.SAME_CONCEPT` working, resolved at call time
    if name == "SAME_CONCEPT":
        return same_concept()
    raise AttributeError(name)


def cluster(texts: list[str], threshold: float | None = None, groups: list | None = None) -> list[int]:
    """Average-linkage agglomerative clustering on concept similarity.

    `groups` (e.g. unit numbers) prevents merging questions known to belong to different units.
    Returns a cluster label per text.
    """
    threshold = same_concept() if threshold is None else threshold
    n = len(texts)
    if n == 0:
        return []
    if n == 1:
        return [0]
    sim = similarity_matrix(texts)
    if groups is not None:
        for i in range(n):
            for j in range(n):
                if groups[i] is not None and groups[j] is not None and groups[i] != groups[j]:
                    sim[i, j] = 0.0
    from sklearn.cluster import AgglomerativeClustering

    dist = 1.0 - sim
    np.fill_diagonal(dist, 0.0)
    model = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                    distance_threshold=1.0 - threshold)
    return model.fit_predict(dist).tolist()
