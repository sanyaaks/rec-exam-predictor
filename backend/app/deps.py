from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .services.exam_config import merged_config, normalized_weights, weights_by_type


def get_subject(db: Session, user: models.User, subject_id: int) -> models.Subject:
    s = db.get(models.Subject, subject_id)
    if not s or s.owner_id != user.id:
        raise HTTPException(404, "Subject not found")
    return s


def get_document(db: Session, user: models.User, doc_id: int) -> models.Document:
    d = db.get(models.Document, doc_id)
    if not d or d.subject.owner_id != user.id:
        raise HTTPException(404, "Document not found")
    return d


def get_question(db: Session, user: models.User, qid: int) -> models.Question:
    q = db.get(models.Question, qid)
    if not q or q.document.subject.owner_id != user.id:
        raise HTTPException(404, "Question not found")
    return q


def user_out(u: models.User) -> dict:
    return {"id": u.id, "email": u.email, "name": u.name, "department": u.department,
            "is_guest": u.email.endswith("@guest.local")}


def subject_out(s: models.Subject, full: bool = False) -> dict:
    out = {"id": s.id, "name": s.name, "code": s.code, "department": s.department, "regulation": s.regulation,
           "semester": s.semester, "syllabus_version": s.syllabus_version or "", "is_demo": s.is_demo, "created_at": s.created_at.isoformat()}
    if full:
        out["exam_config"] = merged_config(s.exam_config)
        out["weights"] = normalized_weights(s.weights)
        out["units"] = [{"id": u.id, "number": u.number, "title": u.title, "topics": u.topics or [], "hours": u.hours,
                         "topic_meta": u.topic_meta or {}} for u in s.units]
        out["weights_by_type"] = weights_by_type(s.weights)
    return out


def document_out(d: models.Document, with_text: bool = False) -> dict:
    out = {"id": d.id, "subject_id": d.subject_id, "filename": d.filename, "mime": d.mime, "kind": d.kind,
           "exam_type": d.exam_type, "academic_year": d.academic_year, "exam_year": d.exam_year,
           "exam_month": d.exam_month, "units_covered": d.units_covered or [], "status": d.status,
           "faculty_id": d.faculty_id or "", "feedback_for_prediction_id": d.feedback_for_prediction_id,
           "extraction_method": d.extraction_method, "notes": d.notes, "page_count": d.page_count,
           "is_sample": d.is_sample, "question_count": len(d.questions), "created_at": d.created_at.isoformat(),
           "has_file": bool(d.stored_path)}
    if with_text:
        out["raw_text"] = d.raw_text
    return out


def question_out(q: models.Question) -> dict:
    d = q.document
    return {"id": q.id, "document_id": q.document_id, "number": q.number, "choice": q.choice, "sub": q.sub,
            "section": q.section, "text": q.text, "marks": q.marks, "category": q.category, "qtype": q.qtype,
            "unit": q.unit, "topic": q.topic, "subtopic": q.subtopic or "", "topic_source": q.topic_source or "",
            "topic_confidence": q.topic_confidence, "co": q.co,
            "bloom": q.bloom, "confidence": q.confidence, "verified": q.verified, "excluded": q.excluded,
            "exam_type": d.exam_type, "exam_year": d.exam_year, "academic_year": d.academic_year,
            "doc_kind": d.kind, "doc_name": d.filename, "is_sample": d.is_sample}
