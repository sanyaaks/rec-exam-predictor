"""Engine-level defaults. Subject-specific values (exam patterns, weights) are passed in by the app."""

DEFAULT_WEIGHTS = {
    "frequency": 0.25,
    "recency": 0.15,
    "syllabus": 0.20,
    "unit_coverage": 0.15,
    "marks_pattern": 0.15,
    "variation": 0.10,
}

WEIGHT_LABELS = {
    "frequency": "Historical frequency",
    "recency": "Recency & repetition cycle",
    "syllabus": "Syllabus importance",
    "unit_coverage": "Unit coverage & rotation",
    "marks_pattern": "Marks-pattern consistency",
    "variation": "Semantic variations",
}

DEFAULT_THRESHOLDS = {"very_high": 62, "high": 48, "moderate": 34}

# Final question priority = TOPIC_SHARE x topic score + (1 - TOPIC_SHARE) x question score
TOPIC_SHARE = 0.6

# ML data gate: below these, the statistical ranker is used and the reason is reported.
ML_GATE = {"min_dated_papers": 8, "min_origins": 5, "min_positives": 25, "min_val_origins": 2, "min_gain": 0.01}
MIN_HISTORY = 2   # earlier dated papers required before a paper can be an evaluation origin


def normalize(weights: dict | None) -> dict:
    w = dict(DEFAULT_WEIGHTS)
    for k, v in (weights or {}).items():
        if k in w:
            try:
                w[k] = max(0.0, float(v))
            except (TypeError, ValueError):
                pass
    tot = sum(w.values()) or 1.0
    return {k: v / tot for k, v in w.items()}


def long_categories(cfg: dict) -> list[int]:
    return [m for m in cfg.get("mark_categories", [2, 11, 13, 15]) if m > 2]


def scope_for(cfg: dict, exam_type: str, override: list[int] | None = None) -> list[int]:
    if override:
        return sorted(set(int(u) for u in override))
    return sorted(cfg.get(exam_type, {}).get("units") or [])
