from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_user
from ..db import get_db
from ..deps import get_subject
from ..services import engine_adapter

router = APIRouter(prefix="/api", tags=["study"])
STATUSES = {"not_started", "studying", "completed", "revision"}


def _saved_out(r: models.SavedQuestion, names: dict) -> dict:
    return {"id": r.id, "subject_id": r.subject_id, "subject": names.get(r.subject_id, ""), "text": r.text,
            "marks": r.marks, "unit": r.unit, "topic": r.topic, "evidence": r.evidence, "priority": r.priority,
            "status": r.status, "note": r.note, "created_at": r.created_at.isoformat()}


def _names(db, user):
    return {s.id: s.name for s in db.query(models.Subject).filter_by(owner_id=user.id).all()}


# ------------------------------------------------------------------ saved questions
class SavedIn(BaseModel):
    subject_id: int
    text: str
    marks: int | None = None
    unit: int | None = None
    topic: str = ""
    evidence: str = ""
    priority: str = ""
    note: str = ""


class SavedPatch(BaseModel):
    status: str | None = None
    note: str | None = None


@router.get("/saved")
def list_saved(subject_id: int | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(models.SavedQuestion).filter_by(user_id=user.id)
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    names = _names(db, user)
    return [_saved_out(r, names) for r in q.order_by(models.SavedQuestion.created_at.desc()).all()]


@router.post("/saved")
def save_question(body: SavedIn, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, body.subject_id)
    existing = db.query(models.SavedQuestion).filter_by(user_id=user.id, subject_id=body.subject_id, text=body.text).first()
    if existing:
        return _saved_out(existing, _names(db, user))
    r = models.SavedQuestion(user_id=user.id, **body.model_dump())
    db.add(r)
    db.commit()
    return _saved_out(r, _names(db, user))


@router.patch("/saved/{rid}")
def patch_saved(rid: int, body: SavedPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(models.SavedQuestion, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Not found")
    if body.status is not None:
        if body.status not in STATUSES:
            raise HTTPException(400, "Invalid status")
        r.status = body.status
    if body.note is not None:
        r.note = body.note
    db.commit()
    return _saved_out(r, _names(db, user))


@router.delete("/saved/{rid}")
def delete_saved(rid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    r = db.get(models.SavedQuestion, rid)
    if not r or r.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(r)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ topic progress tracker
@router.get("/subjects/{sid}/progress")
def get_progress(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    rows = {(r.unit, r.topic): r.status for r in db.query(models.TopicProgress).filter_by(user_id=user.id, subject_id=sid)}
    units = []
    for u in s.units:
        topics = [{"topic": t, "status": rows.get((u.number, t), "not_started")} for t in (u.topics or [])]
        done = sum(1 for t in topics if t["status"] == "completed")
        units.append({"unit": u.number, "title": u.title, "topics": topics, "completed": done, "total": len(topics)})
    total = sum(u["total"] for u in units)
    done = sum(u["completed"] for u in units)
    return {"units": units, "completed": done, "total": total, "percent": round(100 * done / total) if total else 0}


class ProgressIn(BaseModel):
    unit: int
    topic: str
    status: str


@router.put("/subjects/{sid}/progress")
def set_progress(sid: int, body: ProgressIn, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, sid)
    if body.status not in STATUSES:
        raise HTTPException(400, "Invalid status")
    r = db.query(models.TopicProgress).filter_by(user_id=user.id, subject_id=sid, unit=body.unit, topic=body.topic).first()
    if not r:
        r = models.TopicProgress(user_id=user.id, subject_id=sid, unit=body.unit, topic=body.topic)
        db.add(r)
    r.status = body.status
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ exams
class ExamIn(BaseModel):
    subject_id: int
    exam_type: str
    date: str
    title: str = ""


def _exam_out(e: models.Exam, names: dict) -> dict:
    days = (date.fromisoformat(e.date) - date.today()).days
    return {"id": e.id, "subject_id": e.subject_id, "subject": names.get(e.subject_id, ""), "exam_type": e.exam_type,
            "date": e.date, "title": e.title, "days_left": days}


@router.get("/exams")
def list_exams(user=Depends(current_user), db: Session = Depends(get_db)):
    names = _names(db, user)
    rows = db.query(models.Exam).filter_by(user_id=user.id).order_by(models.Exam.date).all()
    return [_exam_out(e, names) for e in rows]


@router.post("/exams")
def add_exam(body: ExamIn, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, body.subject_id)
    try:
        date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD")
    e = models.Exam(user_id=user.id, **body.model_dump())
    db.add(e)
    db.commit()
    return _exam_out(e, _names(db, user))


@router.delete("/exams/{eid}")
def delete_exam(eid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    e = db.get(models.Exam, eid)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(e)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ study plan
class PlanIn(BaseModel):
    date: str
    title: str
    subject_id: int | None = None
    unit: int | None = None
    minutes: int = 60


class PlanPatch(BaseModel):
    done: bool | None = None
    date: str | None = None
    title: str | None = None
    minutes: int | None = None


def _plan_out(p: models.PlanItem, names: dict) -> dict:
    return {"id": p.id, "date": p.date, "title": p.title, "subject_id": p.subject_id,
            "subject": names.get(p.subject_id, ""), "unit": p.unit, "minutes": p.minutes, "done": p.done}


@router.get("/plan")
def list_plan(user=Depends(current_user), db: Session = Depends(get_db)):
    names = _names(db, user)
    return [_plan_out(p, names) for p in db.query(models.PlanItem).filter_by(user_id=user.id).order_by(models.PlanItem.date).all()]


@router.post("/plan")
def add_plan(body: PlanIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if body.subject_id:
        get_subject(db, user, body.subject_id)
    p = models.PlanItem(user_id=user.id, **body.model_dump())
    db.add(p)
    db.commit()
    return _plan_out(p, _names(db, user))


@router.patch("/plan/{pid}")
def patch_plan(pid: int, body: PlanPatch, user=Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(models.PlanItem, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    return _plan_out(p, _names(db, user))


@router.delete("/plan/{pid}")
def delete_plan(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(models.PlanItem, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


class AutoPlanIn(BaseModel):
    exam_id: int
    minutes_per_day: int = 120


@router.post("/plan/auto")
def auto_plan(body: AutoPlanIn, user=Depends(current_user), db: Session = Depends(get_db)):
    """Spread the exam's predicted questions over the days left, highest priority first,
    finishing with a revision day."""
    e = db.get(models.Exam, body.exam_id)
    if not e or e.user_id != user.id:
        raise HTTPException(404, "Exam not found")
    s = get_subject(db, user, e.subject_id)
    cfg = merged_config(s.exam_config)
    et = e.exam_type if e.exam_type in cfg else "SEMESTER"
    pred, _, cfg = engine_adapter.run_predict(db, s, e.exam_type if e.exam_type in ("CAT1", "CAT2", "SEMESTER") else "SEMESTER")
    items = pred["items"]
    items = [i for i in items if i["priority"] in ("very_high", "high", "moderate")][:40]
    start, end = date.today() + timedelta(days=1), date.fromisoformat(e.date) - timedelta(days=1)
    days = (end - start).days + 1
    if days < 1:
        raise HTTPException(400, "The exam is too close to plan for - revise the very-high-priority list instead.")
    study_days = max(1, days - 1)
    # rough effort estimate in minutes per question
    cost = lambda it: 15 if it["marks"] <= 2 else 45
    plan, day, used = [], 0, 0
    for it in items:
        if used + cost(it) > body.minutes_per_day and used > 0:
            day, used = day + 1, 0
        if day >= study_days:
            break
        plan.append((start + timedelta(days=day), it))
        used += cost(it)
    names = _names(db, user)
    created = []
    by_day: dict = {}
    for d, it in plan:
        by_day.setdefault((d, it["unit"]), []).append(it)
    for (d, unit), its in sorted(by_day.items(), key=lambda x: (x[0][0], x[0][1] or 0)):
        long_n = sum(1 for i in its if i["marks"] > 2)
        short_n = len(its) - long_n
        title = f"{s.name}: Unit {unit or '?'} - {long_n} long + {short_n} short predicted questions ({its[0]['topic'] or its[0]['text'][:40]}...)"
        p = models.PlanItem(user_id=user.id, subject_id=s.id, date=d.isoformat(), title=title, unit=unit,
                            minutes=sum(cost(i) for i in its))
        db.add(p)
        created.append(p)
    rev = models.PlanItem(user_id=user.id, subject_id=s.id, date=end.isoformat(),
                          title=f"{s.name}: revise all very-high-priority questions + 2-mark list", minutes=body.minutes_per_day)
    db.add(rev)
    created.append(rev)
    db.commit()
    return [_plan_out(p, names) for p in created]


# ------------------------------------------------------------------ dashboard
@router.get("/dashboard")
def dashboard(user=Depends(current_user), db: Session = Depends(get_db)):
    names = _names(db, user)
    subjects = db.query(models.Subject).filter_by(owner_id=user.id).all()
    subj_rows = []
    for s in subjects:
        topics = sum(len(u.topics or []) for u in s.units)
        done = db.query(models.TopicProgress).filter_by(user_id=user.id, subject_id=s.id, status="completed").count()
        papers = [d for d in s.documents if d.kind == "question_paper"]
        subj_rows.append({"id": s.id, "name": s.name, "code": s.code, "is_demo": s.is_demo, "papers": len(papers),
                          "progress": round(100 * done / topics) if topics else 0,
                          "updated_at": max([d.created_at for d in s.documents], default=s.created_at).isoformat()})
    subj_rows.sort(key=lambda r: r["updated_at"], reverse=True)
    docs = (db.query(models.Document).join(models.Subject).filter(models.Subject.owner_id == user.id)
            .order_by(models.Document.created_at.desc()).limit(6).all())
    exams = [_exam_out(e, names) for e in db.query(models.Exam).filter_by(user_id=user.id).order_by(models.Exam.date).all()
             if e.date >= date.today().isoformat()]
    today = date.today().isoformat()
    plan_today = [_plan_out(p, names) for p in db.query(models.PlanItem).filter_by(user_id=user.id, date=today).all()]
    preds = (db.query(models.Prediction).filter_by(user_id=user.id).order_by(models.Prediction.created_at.desc()).limit(5).all())
    saved = db.query(models.SavedQuestion).filter_by(user_id=user.id).all()
    return {
        "subjects": subj_rows,
        "recent_documents": [{"id": d.id, "subject_id": d.subject_id, "subject": names.get(d.subject_id, ""),
                              "filename": d.filename, "exam_type": d.exam_type, "kind": d.kind, "status": d.status,
                              "academic_year": d.academic_year, "created_at": d.created_at.isoformat()} for d in docs],
        "exams": exams[:5],
        "plan_today": plan_today,
        "recent_predictions": [{"id": p.id, "title": p.title, "subject": names.get(p.subject_id, ""),
                                "subject_id": p.subject_id, "exam_type": p.exam_type,
                                "created_at": p.created_at.isoformat()} for p in preds],
        "saved": {"total": len(saved), "completed": sum(1 for x in saved if x.status == "completed")},
    }
