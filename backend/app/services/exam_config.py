"""Default exam patterns and scoring weights.

These are *editable starting points*. Patterns differ by subject and regulation,
so every subject stores its own copy and students/admins can change it.
"""
import copy

from prediction_engine.config import DEFAULT_WEIGHTS, WEIGHT_LABELS, normalize  # noqa: F401
from prediction_engine.topics import DEFAULT_CLASSIFIER

DEFAULT_EXAM_CONFIG = {
    "units_count": 5,
    "mark_categories": [2, 11, 13, 15],
    "CAT1": {
        "label": "CAT 1",
        "units": [1, 2],
        "duration": "1 hr 30 min",
        "ranker": "auto",
        "confirmed": False,
        "sections": [
            {"name": "A", "title": "PART A", "marks_each": 2, "count": 6, "choice": "none",
             "instruction": "Answer ALL questions"},
            {"name": "B", "title": "PART B", "marks_each": 11, "count": 4, "choice": "either_or",
             "instruction": "Answer ALL questions, choosing either (a) or (b)"},
        ],
    },
    "CAT2": {
        "label": "CAT 2",
        "units": [3, 4],
        "duration": "1 hr 30 min",
        "ranker": "auto",
        "confirmed": False,
        "sections": [
            {"name": "A", "title": "PART A", "marks_each": 2, "count": 6, "choice": "none",
             "instruction": "Answer ALL questions"},
            {"name": "B", "title": "PART B", "marks_each": 11, "count": 4, "choice": "either_or",
             "instruction": "Answer ALL questions, choosing either (a) or (b)"},
        ],
    },
    "SEMESTER": {
        "label": "End Semester Examination",
        "units": [1, 2, 3, 4, 5],
        "duration": "3 hours",
        "ranker": "auto",
        "confirmed": False,
        "sections": [
            {"name": "A", "title": "PART A", "marks_each": 2, "count": 10, "choice": "none",
             "instruction": "Answer ALL questions"},
            {"name": "B", "title": "PART B", "marks_each": 13, "count": 5, "choice": "either_or",
             "instruction": "Answer ALL questions, choosing either (a) or (b)"},
            {"name": "C", "title": "PART C", "marks_each": 15, "count": 1, "choice": "either_or",
             "instruction": "Answer the question, choosing either (a) or (b)"},
        ],
    },
    "priority_thresholds": {"very_high": 62, "high": 48, "moderate": 34},
    # syllabus topic classifier (see prediction_engine/topics.py)
    "classification": dict(DEFAULT_CLASSIFIER),
}

EXAM_TYPES = ["CAT1", "CAT2", "SEMESTER"]


def merged_config(stored: dict | None) -> dict:
    cfg = copy.deepcopy(DEFAULT_EXAM_CONFIG)
    for k, v in (stored or {}).items():
        if k in ("CAT1", "CAT2", "SEMESTER") and isinstance(v, dict):
            cfg[k] = {**cfg[k], **v}
        elif k == "classification" and isinstance(v, dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def normalized_weights(stored: dict | None, exam_type: str | None = None) -> dict:
    """Weights may be flat (shared by all exams) or per exam type: {"CAT1": {...}, "SEMESTER": {...}}."""
    stored = stored or {}
    if exam_type and isinstance(stored.get(exam_type), dict):
        return normalize(stored[exam_type])
    return normalize({k: v for k, v in stored.items() if not isinstance(v, dict)})


def weights_by_type(stored: dict | None) -> dict:
    return {et: normalized_weights(stored, et) for et in EXAM_TYPES}


def long_categories(cfg: dict) -> list[int]:
    return [m for m in cfg.get("mark_categories", [2, 11, 13, 15]) if m > 2]


def nearest_category(marks: int | None, cfg: dict) -> int | None:
    if marks is None:
        return None
    cats = sorted(cfg.get("mark_categories", [2, 11, 13, 15]))
    if marks in cats:
        return marks
    if marks <= 3:
        return min(cats)
    # sub-part marks (e.g. 6, 7, 8) belong to long-answer slots; caller usually overrides
    return min(cats, key=lambda c: abs(c - marks))
