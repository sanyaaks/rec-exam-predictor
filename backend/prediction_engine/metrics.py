"""Ranking metrics. `gains` maps topic key -> number of questions on that topic in the actual paper.
Keys starting with 'novel:' are relevant topics no ranker could retrieve; they count in the
denominators so results are never overstated."""
from __future__ import annotations

import math


def precision_at_k(ranked: list[str], gains: dict[str, int], k: int) -> float:
    top = ranked[:k]
    return sum(1 for key in top if gains.get(key)) / k if k else 0.0


def recall_at_k(ranked: list[str], gains: dict[str, int], k: int) -> float:
    rel = [key for key, g in gains.items() if g]
    if not rel:
        return 0.0
    return sum(1 for key in ranked[:k] if gains.get(key)) / len(rel)


def ndcg_at_k(ranked: list[str], gains: dict[str, int], k: int) -> float:
    dcg = sum((2 ** gains.get(key, 0) - 1) / math.log2(i + 2) for i, key in enumerate(ranked[:k]))
    ideal = sorted((g for g in gains.values() if g), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def ranking_report(ranked: list[str], gains: dict[str, int], ks=(5, 10)) -> dict:
    n_rel = sum(1 for g in gains.values() if g)
    out = {}
    for k in ks:
        out[f"precision@{k}"] = round(precision_at_k(ranked, gains, k), 3)
        out[f"recall@{k}"] = round(recall_at_k(ranked, gains, k), 3)
        out[f"ndcg@{k}"] = round(ndcg_at_k(ranked, gains, k), 3)
    r = max(n_rel, 1)
    out["precision@R"] = round(precision_at_k(ranked, gains, r), 3)   # R = number of topics actually asked
    out["ndcg@R"] = round(ndcg_at_k(ranked, gains, r), 3)
    out["relevant_topics"] = n_rel
    out["novel_topics"] = sum(1 for key, g in gains.items() if g and key.startswith("novel:"))
    return out
