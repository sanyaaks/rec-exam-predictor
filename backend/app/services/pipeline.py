"""Glue between the database, the document-processing services and the prediction engine."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .. import models
from prediction_engine import semantic, topics
from prediction_engine.records import EXAM_LABEL, Corpus, Paper

from . import extraction, ingestion
from .exam_config import merged_config

log = logging.getLogger(__name__)


def paper_label(doc: models.Document) -> str:
    base = EXAM_LABEL.get(doc.exam_type, doc.exam_type)
    when = doc.academic_year or (str(doc.exam_year) if doc.exam_year else "")
    return f"{base} {when}".strip()


def subject_units(subject: models.Subject) -> list[dict]:
    return [{"number": u.number, "title": u.title, "topics": u.topics or [], "hours": u.hours,
             "topic_meta": u.topic_meta or {}} for u in subject.units]


def _allowed_units(doc: models.Document, cfg: dict):
    return doc.units_covered or (cfg.get(doc.exam_type, {}).get("units") if doc.exam_type in ("CAT1", "CAT2") else None)


def remap_subject(db: Session, subject: models.Subject) -> int:
    """(Re)assign unit/topic for every question that the student hasn't manually verified."""
    qs = (db.query(models.Question).join(models.Document)
          .filter(models.Question.subject_id == subject.id).all())
    qs = [q for q in qs if not q.verified]
    if not qs:
        return 0
    units = subject_units(subject)
    cfg = merged_config(subject.exam_config)
    allowed = [_allowed_units(q.document, cfg) or None for q in qs]
    # a unit printed on the paper / question bank header (confidence 1.0) is trusted over similarity
    hints = [q.unit if (q.unit and q.topic_confidence >= 1.0) else None for q in qs]
    mapped = topics.classify([q.text for q in qs], units, allowed, hints, cfg.get("classification"))
    for q, m, hint in zip(qs, mapped, hints):
        if hint is None:
            q.unit = m["unit"]
        q.topic, q.subtopic, q.topic_source = m["topic"], m["subtopic"], m["source"]
        if q.topic_confidence < 1.0:
            q.topic_confidence = m["confidence"]
    db.commit()
    return len(qs)


def process_document(db: Session, doc: models.Document) -> models.Document:
    subject = doc.subject
    cfg = merged_config(subject.exam_config)
    doc.status = "processing"
    db.commit()
    try:
        res = ingestion.extract_text(doc.stored_path)
    except Exception as e:
        log.exception("extraction failed")
        doc.status, doc.notes = "failed", f"Could not read file: {e}"
        db.commit()
        return doc
    doc.raw_text = res.text
    doc.extraction_method = res.method
    doc.page_count = res.pages
    notes = list(res.warnings)

    if doc.kind == "syllabus":
        units = extraction.parse_syllabus(res.text)
        if units:
            for u in list(subject.units):
                db.delete(u)
            db.flush()
            for u in units:
                db.add(models.SyllabusUnit(subject_id=subject.id, number=u["number"], title=u["title"],
                                           topics=u["topics"], hours=u["hours"], topic_meta={}))
            db.commit()
            db.refresh(subject)
            remap_subject(db, subject)
            doc.status = "done"
            notes.append(f"Found {len(units)} units and {sum(len(u['topics']) for u in units)} topics.")
        else:
            doc.status = "needs_review"
            notes.append("No 'UNIT I/II/...' headings found. Add units manually in the Syllabus tab.")
        doc.notes = "\n".join(notes)
        db.commit()
        return doc

    for q in list(doc.questions):
        db.delete(q)
    db.flush()
    ocr = "ocr" in res.method
    parsed = extraction.parse_questions(res.text, doc.exam_type, cfg, ocr=ocr)
    units = subject_units(subject)
    allowed = _allowed_units(doc, cfg)
    mapped = topics.classify([p.text for p in parsed], units, [allowed] * len(parsed),
                             [p.unit_hint for p in parsed], cfg.get("classification"))
    for p, m in zip(parsed, mapped):
        db.add(models.Question(
            subject_id=subject.id, document_id=doc.id, number=p.number, choice=p.choice, sub=p.sub,
            section=p.section, text=p.text, marks=p.marks, category=p.category,
            qtype=extraction.classify_qtype(p.text), unit=m["unit"], topic=m["topic"], subtopic=m["subtopic"],
            topic_source=m["source"], topic_confidence=1.0 if p.unit_hint else m["confidence"],
            normalized_text=semantic.normalized_text(p.text), co=p.co, bloom=p.bloom, confidence=p.confidence,
        ))
    if not parsed:
        doc.status = "needs_review"
        notes.append("No questions could be extracted automatically. Add them in the Questions tab.")
    else:
        low = sum(1 for p in parsed if p.confidence < 0.6)
        doc.status = "needs_review" if low > len(parsed) * 0.3 else "done"
        notes.append(f"Extracted {len(parsed)} questions" + (f"; {low} need a quick check." if low else "."))
    doc.notes = "\n".join(notes)
    db.commit()
    return doc


def load_corpus(db: Session, subject: models.Subject) -> Corpus:
    docs = (db.query(models.Document).filter(models.Document.subject_id == subject.id,
                                              models.Document.status.in_(["done", "needs_review"])).all())
    papers, questions, bank = [], [], []
    paper_docs = sorted([d for d in docs if d.kind == "question_paper" and d.exam_type in ("CAT1", "CAT2", "SEMESTER")],
                        key=lambda d: (d.exam_year or 0, d.exam_month or 6, d.id))
    for i, d in enumerate(paper_docs):
        papers.append(Paper(id=d.id, exam_type=d.exam_type, year=d.exam_year, month=d.exam_month,
                            label=paper_label(d), seq=i, units_covered=list(d.units_covered or [])))
    paper_ids = {p.id for p in papers}
    for d in docs:
        for q in d.questions:
            if q.excluded:
                continue
            row = {"id": q.id, "text": q.text, "category": q.category, "unit": q.unit, "topic": q.topic,
                   "subtopic": q.subtopic, "qtype": q.qtype, "paper_id": d.id, "number": q.number}
            if d.id in paper_ids:
                questions.append(row)
            elif d.kind == "question_bank":
                bank.append(row)
    return Corpus(papers=papers, questions=questions, bank_questions=bank, units=subject_units(subject))
