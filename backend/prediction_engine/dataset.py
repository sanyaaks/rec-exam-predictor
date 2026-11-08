"""Structured examination dataset (one row per extracted question).

`previous_appearance_count` is computed without leakage: the number of distinct papers dated
strictly before this question's paper that contain the same concept (semantic cluster).
"""
from __future__ import annotations

from collections import defaultdict

from . import semantic

FIELDS = ["subject_code", "subject_name", "regulation", "semester", "department", "academic_year",
          "examination_year", "examination_type", "faculty_id", "question_text", "normalized_question", "marks",
          "question_type", "unit", "topic", "subtopic", "syllabus_version", "previous_appearance_count"]


def build(subject: dict, papers: list[dict], questions: list[dict]) -> list[dict]:
    """subject: {code,name,regulation,semester,department,syllabus_version}
    papers: [{id, exam_type, academic_year, exam_year, exam_month, faculty_id}]
    questions: [{id, paper_id, text, category, qtype, unit, topic, subtopic}]"""
    pinfo = {p["id"]: p for p in papers}

    def t(pid):
        p = pinfo[pid]
        return None if p.get("exam_year") is None else p["exam_year"] + ((p.get("exam_month") or 6) - 1) / 12

    labels = semantic.cluster([q["text"] for q in questions], groups=[q.get("unit") for q in questions]) if questions else []
    papers_by_cluster: dict[int, set] = defaultdict(set)
    for q, lab in zip(questions, labels):
        papers_by_cluster[lab].add(q["paper_id"])
    rows = []
    for q, lab in zip(questions, labels):
        p = pinfo[q["paper_id"]]
        tq = t(q["paper_id"])
        prev = None
        if tq is not None:
            prev = sum(1 for pid in papers_by_cluster[lab] if pid != q["paper_id"] and t(pid) is not None and t(pid) < tq - 1e-6)
        rows.append({
            "subject_code": subject.get("code", ""), "subject_name": subject.get("name", ""),
            "regulation": subject.get("regulation", ""), "semester": subject.get("semester"),
            "department": subject.get("department", ""), "academic_year": p.get("academic_year", ""),
            "examination_year": p.get("exam_year"), "examination_type": p.get("exam_type"),
            "faculty_id": p.get("faculty_id") or "", "question_text": q["text"],
            "normalized_question": semantic.normalized_text(q["text"]), "marks": q.get("category"),
            "question_type": q.get("qtype", ""), "unit": q.get("unit"), "topic": q.get("topic", ""),
            "subtopic": q.get("subtopic", ""), "syllabus_version": subject.get("syllabus_version", ""),
            "previous_appearance_count": prev,
        })
    return rows
