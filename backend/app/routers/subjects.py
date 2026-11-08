import json
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_user
from ..config import MAX_UPLOAD_MB, UPLOAD_DIR
from ..db import get_db
from ..deps import document_out, get_document, get_question, get_subject, question_out, subject_out
from prediction_engine import semantic

from ..services import extraction, pipeline
from ..services.exam_config import DEFAULT_WEIGHTS, merged_config
from ..services.ingestion import SUPPORTED

router = APIRouter(prefix="/api", tags=["subjects"])


# ------------------------------------------------------------------ subjects
class SubjectIn(BaseModel):
    name: str
    code: str = ""
    department: str = ""
    regulation: str = "2023"
    semester: int = 1


class SubjectPatch(BaseModel):
    name: str | None = None
    code: str | None = None
    department: str | None = None
    regulation: str | None = None
    semester: int | None = None
    syllabus_version: str | None = None
    exam_config: dict | None = None
    weights: dict | None = None


def _stats(db: Session, s: models.Subject, user: models.User) -> dict:
    docs = s.documents
    qcount = db.query(models.Question).filter(models.Question.subject_id == s.id).count()
    topics = sum(len(u.topics or []) for u in s.units)
    done = db.query(models.TopicProgress).filter_by(user_id=user.id, subject_id=s.id, status="completed").count()
    last = max([d.created_at for d in docs], default=s.created_at)
    return {**subject_out(s), "documents": len([d for d in docs if d.kind == "question_paper"]),
            "questions": qcount, "topics": topics, "topics_completed": done,
            "has_syllabus": bool(s.units), "updated_at": last.isoformat()}


@router.get("/subjects")
def list_subjects(user=Depends(current_user), db: Session = Depends(get_db)):
    subs = db.query(models.Subject).filter(models.Subject.owner_id == user.id).order_by(models.Subject.created_at.desc()).all()
    return [_stats(db, s, user) for s in subs]


@router.post("/subjects")
def create_subject(body: SubjectIn, user=Depends(current_user), db: Session = Depends(get_db)):
    s = models.Subject(owner_id=user.id, name=body.name.strip(), code=body.code.strip().upper(),
                       department=body.department, regulation=body.regulation, semester=body.semester,
                       exam_config={}, weights=dict(DEFAULT_WEIGHTS))
    db.add(s)
    db.commit()
    return subject_out(s, full=True)


@router.get("/subjects/{sid}")
def get_subject_detail(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    return {**subject_out(s, full=True), **{k: v for k, v in _stats(db, s, user).items() if k not in subject_out(s)}}


@router.patch("/subjects/{sid}")
def patch_subject(sid: int, body: SubjectPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    data = body.model_dump(exclude_unset=True)
    remap = False
    if "exam_config" in data:
        cfg = merged_config(data["exam_config"])
        for et in ("CAT1", "CAT2", "SEMESTER"):
            secs = cfg[et].get("sections") or []
            if not secs or any(int(x.get("count", 0)) < 1 or int(x.get("marks_each", 0)) < 1 for x in secs):
                raise HTTPException(400, f"{et}: every section needs a question count and marks of at least 1")
        cats = sorted({int(x["marks_each"]) for et in ("CAT1", "CAT2", "SEMESTER") for x in cfg[et]["sections"]}
                      | set(cfg.get("mark_categories", [])))
        cfg["mark_categories"] = cats
        for et in ("CAT1", "CAT2", "SEMESTER"):   # saving the pattern = the student confirmed it
            if (data["exam_config"].get(et) or {}).get("confirmed") is not False:
                cfg[et]["confirmed"] = True
        s.exam_config = cfg
        remap = True
    if "weights" in data:
        raw = data["weights"] or {}
        if any(isinstance(v, dict) for v in raw.values()):     # per exam type
            w = {}
            for et, ww in raw.items():
                if et in ("CAT1", "CAT2", "SEMESTER") and isinstance(ww, dict):
                    w[et] = {k: float(v) for k, v in ww.items() if k in DEFAULT_WEIGHTS}
                    if sum(w[et].values()) <= 0:
                        raise HTTPException(400, f"{et}: at least one weight must be above zero")
        else:
            w = {k: float(v) for k, v in raw.items() if k in DEFAULT_WEIGHTS}
            if sum(w.values()) <= 0:
                raise HTTPException(400, "At least one weight must be above zero")
        s.weights = w
    for k in ("name", "code", "department", "regulation", "semester", "syllabus_version"):
        if k in data and data[k] is not None:
            setattr(s, k, data[k])
    db.commit()
    if remap:
        pipeline.remap_subject(db, s)
    return subject_out(s, full=True)


@router.delete("/subjects/{sid}")
def delete_subject(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    paths = [d.stored_path for d in s.documents if d.stored_path]
    db.delete(s)
    db.commit()
    for p in paths:
        Path(p).unlink(missing_ok=True)
    return {"ok": True}


# ------------------------------------------------------------------ syllabus
class UnitIn(BaseModel):
    number: int
    title: str = ""
    topics: list[str] = []
    hours: int | None = None
    topic_meta: dict = {}   # {topic: {"keywords": [...], "subtopics": [...]}}


class SyllabusIn(BaseModel):
    units: list[UnitIn]
    syllabus_version: str | None = None


class TextIn(BaseModel):
    text: str


@router.put("/subjects/{sid}/syllabus")
def put_syllabus(sid: int, body: SyllabusIn, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    for u in list(s.units):
        db.delete(u)
    db.flush()
    for u in body.units:
        topics_ = [t.strip() for t in u.topics if t.strip()]
        meta = {t: {"keywords": [k.strip() for k in (m or {}).get("keywords", []) if k.strip()],
                    "subtopics": [k.strip() for k in (m or {}).get("subtopics", []) if k.strip()]}
                for t, m in (u.topic_meta or {}).items() if t in topics_}
        db.add(models.SyllabusUnit(subject_id=s.id, number=u.number, title=u.title.strip(),
                                   topics=topics_, hours=u.hours, topic_meta=meta))
    if body.syllabus_version is not None:
        s.syllabus_version = body.syllabus_version.strip()
    db.commit()
    db.refresh(s)
    pipeline.remap_subject(db, s)
    return subject_out(s, full=True)


@router.post("/subjects/{sid}/syllabus/parse")
def parse_syllabus_text(sid: int, body: TextIn, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, sid)
    units = extraction.parse_syllabus(body.text)
    if not units:
        raise HTTPException(400, "Couldn't find 'UNIT I', 'UNIT II' ... headings in that text.")
    return {"units": units}


# ------------------------------------------------------------------ documents
@router.get("/subjects/{sid}/documents")
def list_documents(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    docs = sorted(s.documents, key=lambda d: (d.kind != "syllabus", -(d.exam_year or 0), d.exam_type))
    return [document_out(d) for d in docs]


def _parse_int(v):
    try:
        return int(v) if v not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


@router.post("/subjects/{sid}/documents")
async def upload_documents(sid: int, files: list[UploadFile] = File(...), meta: str = Form("[]"),
                           user=Depends(current_user), db: Session = Depends(get_db)):
    """Upload one or more files. `meta` is a JSON list (one object per file, same order) with
    kind, exam_type, academic_year, exam_year, exam_month, units_covered."""
    s = get_subject(db, user, sid)
    try:
        metas = json.loads(meta)
    except json.JSONDecodeError:
        raise HTTPException(400, "Bad metadata")
    if isinstance(metas, dict):
        metas = [metas] * len(files)
    out = []
    for i, f in enumerate(files):
        m = metas[i] if i < len(metas) else (metas[-1] if metas else {})
        ext = Path(f.filename or "").suffix.lower()
        if ext not in SUPPORTED:
            raise HTTPException(400, f"{f.filename}: unsupported file type. Use PDF, DOCX, JPG or PNG.")
        data = await f.read()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(400, f"{f.filename}: larger than {MAX_UPLOAD_MB} MB")
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
        dest.write_bytes(data)
        kind = m.get("kind") or "question_paper"
        d = models.Document(
            subject_id=s.id, uploaded_by=user.id, filename=f.filename or dest.name, stored_path=str(dest),
            mime=f.content_type or "", kind=kind,
            exam_type=(m.get("exam_type") or "NA") if kind == "question_paper" else "NA",
            academic_year=m.get("academic_year") or "", exam_year=_parse_int(m.get("exam_year")),
            exam_month=_parse_int(m.get("exam_month")),
            units_covered=[int(u) for u in (m.get("units_covered") or []) if str(u).isdigit()],
            faculty_id=str(m.get("faculty_id") or "")[:60],
            feedback_for_prediction_id=_parse_int(m.get("feedback_for_prediction_id")),
        )
        db.add(d)
        db.commit()
        pipeline.process_document(db, d)
        db.refresh(d)
        out.append({**document_out(d), "evaluation": _auto_feedback(db, user, d)})
    return out


def _auto_feedback(db: Session, user, d: models.Document):
    """If this upload is the actual paper for a stored prediction, compare them straight away."""
    if not d.feedback_for_prediction_id or not d.questions:
        return None
    from .insights import _eval_out, evaluate_prediction
    p = db.get(models.Prediction, d.feedback_for_prediction_id)
    if not p or p.user_id != user.id or p.subject_id != d.subject_id:
        return None
    return _eval_out(evaluate_prediction(db, p, d), db)


class PasteIn(BaseModel):
    text: str
    title: str = "Pasted paper"
    kind: str = "question_paper"
    exam_type: str = "NA"
    academic_year: str = ""
    exam_year: int | None = None
    exam_month: int | None = None
    units_covered: list[int] = []
    faculty_id: str = ""
    feedback_for_prediction_id: int | None = None


@router.post("/subjects/{sid}/documents/text")
def paste_document(sid: int, body: PasteIn, user=Depends(current_user), db: Session = Depends(get_db)):
    """For scanned papers without OCR: paste or type the paper text."""
    s = get_subject(db, user, sid)
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}.txt"
    dest.write_text(body.text, encoding="utf-8")
    d = models.Document(subject_id=s.id, uploaded_by=user.id, filename=body.title or "Pasted paper",
                        stored_path=str(dest), mime="text/plain", kind=body.kind,
                        exam_type=body.exam_type if body.kind == "question_paper" else "NA",
                        academic_year=body.academic_year, exam_year=body.exam_year, exam_month=body.exam_month,
                        units_covered=body.units_covered, faculty_id=body.faculty_id[:60],
                        feedback_for_prediction_id=body.feedback_for_prediction_id)
    db.add(d)
    db.commit()
    pipeline.process_document(db, d)
    db.refresh(d)
    return {**document_out(d), "evaluation": _auto_feedback(db, user, d)}


@router.get("/documents/{did}")
def get_doc(did: int, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    return {**document_out(d, with_text=True),
            "questions": [question_out(q) for q in sorted(d.questions, key=lambda q: (int(q.number or 0) if (q.number or "").isdigit() else 999, q.choice, q.sub))]}


class DocPatch(BaseModel):
    filename: str | None = None
    kind: str | None = None
    exam_type: str | None = None
    academic_year: str | None = None
    exam_year: int | None = None
    exam_month: int | None = None
    units_covered: list[int] | None = None
    faculty_id: str | None = None


@router.patch("/documents/{did}")
def patch_doc(did: int, body: DocPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    data = body.model_dump(exclude_unset=True)
    reprocess = any(k in data and data[k] != getattr(d, k) for k in ("kind", "exam_type"))
    for k, v in data.items():
        setattr(d, k, v)
    db.commit()
    if reprocess and d.stored_path:
        pipeline.process_document(db, d)
    elif "units_covered" in data:
        pipeline.remap_subject(db, d.subject)
    db.refresh(d)
    return document_out(d)


@router.post("/documents/{did}/reprocess")
def reprocess(did: int, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    if not d.stored_path or not Path(d.stored_path).exists():
        raise HTTPException(400, "Original file is not available")
    pipeline.process_document(db, d)
    db.refresh(d)
    return document_out(d)


@router.get("/documents/{did}/file")
def download_doc(did: int, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    if not d.stored_path or not Path(d.stored_path).exists():
        raise HTTPException(404, "File not available")
    return FileResponse(d.stored_path, filename=d.filename, media_type=d.mime or None)


@router.delete("/documents/{did}")
def delete_doc(did: int, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    path, subject, was_syllabus = d.stored_path, d.subject, d.kind == "syllabus"
    db.delete(d)
    db.commit()
    if path:
        Path(path).unlink(missing_ok=True)
    if was_syllabus:
        db.refresh(subject)
    return {"ok": True}


# ------------------------------------------------------------------ questions
@router.get("/subjects/{sid}/questions")
def list_questions(sid: int, q: str = "", unit: int | None = None, marks: int | None = None,
                   exam_type: str | None = None, document_id: int | None = None, needs_review: bool = False,
                   user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, sid)
    query = db.query(models.Question).join(models.Document).filter(models.Question.subject_id == sid)
    if unit:
        query = query.filter(models.Question.unit == unit)
    if marks:
        query = query.filter(models.Question.category == marks)
    if exam_type:
        query = query.filter(models.Document.exam_type == exam_type)
    if document_id:
        query = query.filter(models.Question.document_id == document_id)
    if needs_review:
        query = query.filter(models.Question.verified.is_(False), models.Question.confidence < 0.6)
    rows = query.all()
    if q.strip():
        # keyword OR semantic search
        needle = q.lower()
        sims = semantic.similarity_matrix([q], [r.text for r in rows])[0] if rows else []
        scored = [(r, float(s)) for r, s in zip(rows, sims) if needle in r.text.lower() or s >= 0.25]
        scored.sort(key=lambda x: -x[1])
        rows = [r for r, _ in scored]
    else:
        rows.sort(key=lambda r: (-(r.document.exam_year or 0), r.document_id,
                                 int(r.number) if (r.number or "").isdigit() else 999, r.choice, r.sub))
    return [question_out(r) for r in rows]


class QuestionIn(BaseModel):
    text: str
    number: str = ""
    choice: str = ""
    sub: str = ""
    section: str = ""
    marks: int | None = None
    category: int | None = None
    unit: int | None = None
    topic: str = ""
    qtype: str | None = None


class QuestionPatch(BaseModel):
    text: str | None = None
    number: str | None = None
    choice: str | None = None
    sub: str | None = None
    section: str | None = None
    marks: int | None = None
    category: int | None = None
    unit: int | None = None
    topic: str | None = None
    subtopic: str | None = None
    qtype: str | None = None
    verified: bool | None = None
    excluded: bool | None = None


@router.post("/documents/{did}/questions")
def add_question(did: int, body: QuestionIn, user=Depends(current_user), db: Session = Depends(get_db)):
    d = get_document(db, user, did)
    cfg = merged_config(d.subject.exam_config)
    cat = body.category or (body.marks if body.marks in cfg["mark_categories"] else None) or (2 if (body.marks or 0) <= 3 else 13)
    q = models.Question(subject_id=d.subject_id, document_id=d.id, number=body.number, choice=body.choice,
                        sub=body.sub, section=body.section, text=body.text.strip(), marks=body.marks, category=cat,
                        qtype=body.qtype or extraction.classify_qtype(body.text), unit=body.unit, topic=body.topic,
                        topic_confidence=1.0 if body.unit else 0.0, confidence=1.0, verified=bool(body.unit))
    db.add(q)
    db.commit()
    if not body.unit:
        pipeline.remap_subject(db, d.subject)
    db.refresh(q)
    return question_out(q)


@router.patch("/questions/{qid}")
def patch_question(qid: int, body: QuestionPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    q = get_question(db, user, qid)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(q, k, v)
    if "text" in data and "qtype" not in data:
        q.qtype = extraction.classify_qtype(q.text)
    if any(k in data for k in ("text", "unit", "topic", "category", "marks")):
        q.verified = data.get("verified", True)
        q.confidence = 1.0
        if "unit" in data or "topic" in data:
            q.topic_confidence = 1.0
            q.topic_source = "manual"
    if "text" in data:
        q.normalized_text = semantic.normalized_text(q.text)
    db.commit()
    return question_out(q)


@router.delete("/questions/{qid}")
def delete_question(qid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    q = get_question(db, user, qid)
    db.delete(q)
    db.commit()
    return {"ok": True}


@router.get("/subjects/{sid}/duplicates")
def duplicates(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    """Concept groups that contain more than one question (repeated / reworded questions)."""
    s = get_subject(db, user, sid)
    rows = [q for q in db.query(models.Question).filter(models.Question.subject_id == s.id).all() if not q.excluded]
    if len(rows) < 2:
        return []
    labels = semantic.cluster([r.text for r in rows], groups=[r.unit for r in rows])
    groups = defaultdict(list)
    for r, lab in zip(rows, labels):
        groups[lab].append(r)
    out = []
    for members in groups.values():
        if len(members) < 2:
            continue
        docs = {m.document_id for m in members}
        exact = any(semantic.exact_match(a.text, b.text) for i, a in enumerate(members) for b in members[i + 1:]
                    if a.document_id != b.document_id)
        out.append({"size": len(members), "papers": len(docs), "exact": exact,
                    "unit": members[0].unit, "topic": next((m.topic for m in members if m.topic), ""),
                    "questions": [question_out(m) for m in members]})
    out.sort(key=lambda g: (-g["papers"], -g["size"]))
    return out
