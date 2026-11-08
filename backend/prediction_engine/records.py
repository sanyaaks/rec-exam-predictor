"""Plain data records the engine works on. No database or web framework types here,
so the engine can be developed, tested and retrained independently of the app."""
from __future__ import annotations

from dataclasses import dataclass, field

EXAM_LABEL = {"CAT1": "CAT 1", "CAT2": "CAT 2", "SEMESTER": "Semester"}


@dataclass
class Paper:
    id: int
    exam_type: str          # CAT1 | CAT2 | SEMESTER
    year: int | None
    month: int | None
    label: str
    seq: int = 0
    units_covered: list[int] = field(default_factory=list)

    @property
    def dated(self) -> bool:
        return self.year is not None

    @property
    def t(self) -> float:
        """Fractional year used for chronological ordering (undated papers sort by upload order)."""
        if self.year is None:
            return float(self.seq)
        return self.year + ((self.month or 6) - 1) / 12.0


@dataclass
class Corpus:
    papers: list[Paper]
    questions: list[dict]          # id,text,category,unit,topic,subtopic,qtype,paper_id,number
    bank_questions: list[dict] = field(default_factory=list)   # undated faculty lists / question banks
    units: list[dict] = field(default_factory=list)            # [{number,title,topics,hours,topic_meta}]

    def before(self, cutoff_t: float, include_banks: bool = False) -> "Corpus":
        """Only papers dated strictly before `cutoff_t` (leakage guard for training/backtests)."""
        keep = [p for p in self.papers if p.dated and p.t < cutoff_t - 1e-6]
        ids = {p.id for p in keep}
        return Corpus(papers=keep, questions=[q for q in self.questions if q["paper_id"] in ids],
                      bank_questions=list(self.bank_questions) if include_banks else [], units=self.units)


def topic_key(unit, topic: str) -> str:
    return f"u{unit or 0}:{topic}"
