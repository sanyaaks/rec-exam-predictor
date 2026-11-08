"""ML/engine endpoints: readiness checklist, review queue, topic discovery, grounded generation,
dataset export, versioned models and post-exam feedback."""
import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

import prediction_engine as engine
from prediction_engine import dataset, generation, registry, topics
from prediction_engine.records import EXAM_LABEL

from .. import models
from ..auth import current_user
from ..config import ANTHROPIC_MODEL
from ..db import get_db
from ..deps import get_subject, question_out
from ..services import engine_adapter, llm, pipeline
from ..services.exam_config import EXAM_TYPES, merged_config

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/engine")
def engine_info():
    return {**engine.info(), "llm_enabled": llm.enabled()}


# ------------------------------------------------------------------ readiness
def _review_counts(db: Session, s: models.Subject, cfg: dict) -> tuple[int, int]:
    qs = db.query(models.Question).filter(models.Question.subject_id == s.id, models.Question.excluded.is_(False)).all()
    min_sim = cfg["classification"]["min_similarity"]
    unmapped = sum(1 for q in qs if not q.verified and (not q.topic or q.topic_confidence < min_sim))
    uncertain = sum(1 for q in qs if not q.verified and q.confidence < 0.6)
    return unmapped, uncertain


@router.get("/subjects/{sid}/readiness")
def readiness(sid: int, exam_type: str = "SEMESTER", user=Depends(current_user), db: Session = Depends(get_db)):
    """Checklist of the inputs a good prediction needs, before predictions are shown."""
    if exam_type not in EXAM_TYPES:
        raise HTTPException(400, "exam_type must be CAT1, CAT2 or SEMESTER")
    s = get_subject(db, user, sid)
    cfg = merged_config(s.exam_config)
    docs = [d for d in s.documents if d.status in ("done", "needs_review")]
    papers = [d for d in docs if d.kind == "question_paper"]
    same = [d for d in papers if d.exam_type == exam_type]
    other = [d for d in papers if d.exam_type != exam_type and d.exam_type in EXAM_TYPES]
    banks = [d for d in docs if d.kind == "question_bank"]
    undated = [d for d in papers if not d.exam_year]
    topics_n = sum(len(u.topics or []) for u in s.units)
    unmapped, uncertain = _review_counts(db, s, cfg)
    _, rinfo = engine_adapter.ranker_choice(db, s, exam_type)
    label = EXAM_LABEL[exam_type]
    other_label = "semester" if exam_type != "SEMESTER" else "CAT"

    def item(key, label_, status, detail, action=None):
        return {"key": key, "label": label_, "status": status, "detail": detail, "action": action}

    checks = [
        item("syllabus", "Current syllabus", "ok" if topics_n else "missing",
             f"{len(s.units)} units, {topics_n} topics" + (f" (version {s.syllabus_version})" if s.syllabus_version else "")
             if topics_n else "Upload or paste the syllabus so questions can be mapped to topics.", "syllabus"),
        item("units", f"Units included in {label}", "ok" if cfg[exam_type]["units"] else "missing",
             "Units " + ", ".join(map(str, cfg[exam_type]["units"])) + " (change per prediction or in Settings)", "settings"),
        item("pattern", "Exact examination pattern", "ok" if cfg[exam_type].get("confirmed") else "warn",
             " + ".join(f"{x['count']}×{x['marks_each']}" for x in cfg[exam_type]["sections"]) +
             ("" if cfg[exam_type].get("confirmed") else " - default pattern, please confirm it matches your paper"), "settings"),
        item("same_type", f"Previous {label} papers", "ok" if len(same) >= 3 else ("warn" if same else "missing"),
             f"{len(same)} uploaded" + ("" if len(same) >= 3 else " - 3 or more give much better rankings"), "upload"),
        item("other_type", f"Previous {other_label} papers", "ok" if other else "warn", f"{len(other)} uploaded", "upload"),
        item("banks", "Faculty question banks (optional)", "ok" if banks else "info", f"{len(banks)} uploaded", "upload"),
        item("regulation", "Academic regulation", "ok" if s.regulation else "missing", s.regulation or "Not set", "settings"),
        item("code", "Subject code", "ok" if s.code else "warn", s.code or "Not set", "settings"),
        item("dates", "Exam dates on papers", "ok" if not undated else "warn",
             "All papers dated" if not undated else f"{len(undated)} paper(s) have no exam year - they are left out of "
                                                     "trend analysis, training and backtests", "documents"),
        item("review", "Topic mapping & extraction review", "ok" if not (unmapped or uncertain) else "warn",
             "Nothing waiting" if not (unmapped or uncertain) else f"{unmapped} unmapped, {uncertain} uncertain extractions", "review"),
        item("ranker", "Prediction model", "ok" if rinfo["used"] == "ml" else "info",
             ("ML-assisted ranking, model v%s. " % rinfo.get("model_version") if rinfo["used"] == "ml" else "Statistical ranking. ")
             + rinfo["reason"], "accuracy"),
    ]
    blocking = [c for c in checks if c["status"] == "missing"]
    return {"exam_type": exam_type, "checks": checks, "ready": not blocking,
            "summary": "Ready to predict" if not blocking else f"{len(blocking)} required input(s) missing"}


# ------------------------------------------------------------------ review queue
@router.get("/subjects/{sid}/review")
def review_queue(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    """Questions that need a human: missing/weak syllabus mapping and uncertain (often OCR) extractions."""
    s = get_subject(db, user, sid)
    cfg = merged_config(s.exam_config)
    min_sim = cfg["classification"]["min_similarity"]
    qs = db.query(models.Question).filter(models.Question.subject_id == s.id, models.Question.excluded.is_(False)).all()
    unmapped = [q for q in qs if not q.verified and (not q.topic or q.topic_confidence < min_sim)]
    uncertain = [q for q in qs if not q.verified and q.confidence < 0.6]
    units = pipeline.subject_units(s)
    sugg = topics.classify([q.text for q in unmapped], units, None, None, {**cfg["classification"], "min_similarity": 0}) if unmapped and units else []
    return {
        # suggestions below 0.03 similarity are noise, not evidence
        "unmapped": [{**question_out(q), "suggestions": [a for a in (sugg[i]["alternatives"] if sugg else []) if a["score"] >= 0.03]}
                     for i, q in enumerate(unmapped)],
        "uncertain": [{**question_out(q), "ocr": "ocr" in (q.document.extraction_method or "")} for q in uncertain],
        "has_syllabus": bool(units),
    }


# ------------------------------------------------------------------ topic discovery
@router.post("/subjects/{sid}/discover")
def discover_topics(sid: int, method: str = "auto", user=Depends(current_user), db: Session = Depends(get_db)):
    if method not in ("auto", "bertopic", "builtin"):
        raise HTTPException(400, "method must be auto, bertopic or builtin")
    s = get_subject(db, user, sid)
    qs = [q for q in db.query(models.Question).filter(models.Question.subject_id == s.id).all()
          if not q.excluded and not q.topic]
    res = topics.discover([{"id": q.id, "text": q.text, "unit": q.unit} for q in qs], pipeline.subject_units(s), method=method)
    res["unclassified"] = len(qs)
    return res


class DiscoveryApply(BaseModel):
    question_ids: list[int]
    unit: int
    topic: str
    create_topic: bool = False
    keywords: list[str] = []


@router.post("/subjects/{sid}/discover/apply")
def apply_discovery(sid: int, body: DiscoveryApply, user=Depends(current_user), db: Session = Depends(get_db)):
    """Accept a discovered topic: optionally add it to the syllabus, then assign the questions."""
    s = get_subject(db, user, sid)
    unit = next((u for u in s.units if u.number == body.unit), None)
    if unit is None:
        raise HTTPException(400, f"Unit {body.unit} is not in the syllabus")
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(400, "Topic name required")
    if body.create_topic and topic not in (unit.topics or []):
        unit.topics = list(unit.topics or []) + [topic]
    if body.keywords:
        meta = dict(unit.topic_meta or {})
        entry = dict(meta.get(topic, {}))
        entry["keywords"] = sorted(set(entry.get("keywords", []) + [k for k in body.keywords if k.strip()]))
        meta[topic] = entry
        unit.topic_meta = meta
    n = 0
    for qid in body.question_ids:
        q = db.get(models.Question, qid)
        if q and q.subject_id == s.id:
            q.unit, q.topic, q.topic_source, q.topic_confidence, q.verified = body.unit, topic, "discovered", 1.0, True
            n += 1
    db.commit()
    return {"ok": True, "assigned": n, "topic": topic, "unit": body.unit}


# ------------------------------------------------------------------ grounded generation
class GenerateIn(BaseModel):
    topic: str
    unit: int | None = None
    marks: int = 13
    count: int = 4


def _generated_out(g: models.GeneratedQuestion) -> dict:
    return {"id": g.id, "unit": g.unit, "topic": g.topic, "marks": g.marks, "text": g.text, "kind": g.kind,
            "qtype": g.qtype, "source": g.source, "model": g.model, "prompt_version": g.prompt_version,
            "grounding": g.grounding, "created_at": g.created_at.isoformat(), "is_generated": True,
            "label": "AI-generated" if g.source == "llm" else "Template-generated"}


@router.post("/subjects/{sid}/generate")
def generate_questions(sid: int, body: GenerateIn, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    corpus = pipeline.load_corpus(db, s)
    papers = {p.id: p for p in corpus.papers}
    pool = [{**q, "paper": papers[q["paper_id"]].label if q["paper_id"] in papers else "question bank",
             "marks": q.get("category")} for q in corpus.questions + corpus.bank_questions]
    unit_row = next((u for u in corpus.units if u["number"] == body.unit), None)
    retrieved = generation.retrieve(f"{body.topic} {body.topic}", pool, body.unit, k=6)
    res = generation.generate(body.topic, body.unit, unit_row["title"] if unit_row else "", body.marks, body.count,
                              retrieved, unit_row["topics"] if unit_row else [], s.name,
                              llm_json=llm.complete_json if llm.enabled() else None)
    saved = []
    for q in res["questions"]:
        g = models.GeneratedQuestion(subject_id=s.id, user_id=user.id, unit=body.unit, topic=body.topic,
                                     marks=body.marks, text=q["text"], kind=q["kind"], qtype=q.get("qtype", "theory"),
                                     source=q["source"], model=ANTHROPIC_MODEL if q["source"] == "llm" else "",
                                     prompt_version=res["prompt_version"],
                                     grounding={"based_on": q.get("based_on", []), "retrieved": res["retrieved"]})
        db.add(g)
        saved.append(g)
    db.commit()
    return {"questions": [_generated_out(g) for g in saved], "discarded": res["discarded"], "source": res["source"],
            "retrieved": res["retrieved"],
            "note": ("Generated practice questions - grounded in the syllabus topic and the past questions listed. "
                     "They have never appeared in an exam." +
                     ("" if res["source"] == "llm" else " (Template mode: set ANTHROPIC_API_KEY for AI-written questions.)"))}


@router.get("/subjects/{sid}/generated")
def list_generated(sid: int, topic: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, sid)
    q = db.query(models.GeneratedQuestion).filter_by(subject_id=sid, user_id=user.id)
    if topic:
        q = q.filter_by(topic=topic)
    return [_generated_out(g) for g in q.order_by(models.GeneratedQuestion.created_at.desc()).all()]


@router.delete("/generated/{gid}")
def delete_generated(gid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    g = db.get(models.GeneratedQuestion, gid)
    if not g or g.user_id != user.id:
        raise HTTPException(404, "Not found")
    db.delete(g)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ dataset
@router.get("/subjects/{sid}/dataset")
def export_dataset(sid: int, format: str = "json", user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    docs = [d for d in s.documents if d.kind == "question_paper" and d.status in ("done", "needs_review")]
    papers = [{"id": d.id, "exam_type": d.exam_type, "academic_year": d.academic_year, "exam_year": d.exam_year,
               "exam_month": d.exam_month, "faculty_id": d.faculty_id} for d in docs]
    qs = [{"id": q.id, "paper_id": d.id, "text": q.text, "category": q.category, "qtype": q.qtype, "unit": q.unit,
           "topic": q.topic, "subtopic": q.subtopic} for d in docs for q in d.questions if not q.excluded]
    rows = dataset.build({"code": s.code, "name": s.name, "regulation": s.regulation, "semester": s.semester,
                          "department": s.department, "syllabus_version": s.syllabus_version}, papers, qs)
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=dataset.FIELDS)
        w.writeheader()
        w.writerows(rows)
        name = f"{(s.code or s.name).replace(' ', '_')}_dataset.csv"
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
    return {"fields": dataset.FIELDS, "rows": rows, "count": len(rows)}


# ------------------------------------------------------------------ versioned models
def _model_out(m: models.ModelVersion) -> dict:
    return {"id": m.id, "version": m.version, "kind": m.kind, "status": m.status, "engine_version": m.engine_version,
            "gate": m.gate, "train_papers": len(m.train_paper_ids or []), "n_rows": m.n_rows,
            "created_at": m.created_at.isoformat()}


@router.get("/subjects/{sid}/models")
def list_models(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    rows = db.query(models.ModelVersion).filter_by(subject_id=s.id).order_by(models.ModelVersion.version.desc()).all()
    active = next((m for m in rows if m.status == "active"), None)
    return {"models": [_model_out(m) for m in rows], "active": _model_out(active) if active else None,
            "staleness": engine_adapter.model_staleness(db, s, active), "ml_backend": engine.info()["ml_backend"],
            "gate": engine.info()["ml_gate"]}


@router.post("/subjects/{sid}/models/train")
def train_model(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    """Train the optional ML topic ranker on rolling origins; activate it only if it passes the gate."""
    s = get_subject(db, user, sid)
    cfg = merged_config(s.exam_config)
    res = engine.train(pipeline.load_corpus(db, s), cfg, engine_adapter.weights_for(s))
    gate = res["gate"]
    status = "active" if gate.get("use_ml") and res["bundle"] is not None else "rejected"
    version, path = registry.save(engine_adapter.MODEL_DIR, f"subject_{s.id}", res["bundle"] if status == "active" else None,
                                  {"subject_id": s.id, "gate": gate, "train_paper_ids": res["train_paper_ids"],
                                   "train_cutoff_t": res["train_cutoff_t"], "engine_version": engine.ENGINE_VERSION})
    if status == "active":
        for m in db.query(models.ModelVersion).filter_by(subject_id=s.id, status="active"):
            m.status = "archived"
    mv = models.ModelVersion(subject_id=s.id, version=version, kind=(res["bundle"] or {}).get("kind") or (gate.get("backend") or "none"),
                             engine_version=engine.ENGINE_VERSION, status=status, gate=gate,
                             train_paper_ids=res["train_paper_ids"], train_cutoff=res["train_cutoff_t"],
                             n_rows=res["n_rows"], artifact_path=path if status == "active" else "")
    db.add(mv)
    db.commit()
    return {"model": _model_out(mv), "message": gate.get("reason", "")}


@router.post("/models/{mid}/archive")
def archive_model(mid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    m = db.get(models.ModelVersion, mid)
    if not m:
        raise HTTPException(404, "Model not found")
    get_subject(db, user, m.subject_id)
    m.status = "archived"
    db.commit()
    return _model_out(m)


@router.post("/models/{mid}/activate")
def activate_model(mid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    """Re-activate an earlier model version that passed its gate (rollback)."""
    m = db.get(models.ModelVersion, mid)
    if not m:
        raise HTTPException(404, "Model not found")
    get_subject(db, user, m.subject_id)
    if not m.gate.get("use_ml") or not m.artifact_path:
        raise HTTPException(400, "This version did not pass validation and has no model to activate.")
    for other in db.query(models.ModelVersion).filter_by(subject_id=m.subject_id, status="active"):
        other.status = "archived"
    m.status = "active"
    db.commit()
    return _model_out(m)


# ------------------------------------------------------------------ feedback
class EvaluateIn(BaseModel):
    document_id: int


def evaluate_prediction(db: Session, p: models.Prediction, d: models.Document) -> models.PredictionEvaluation:
    actual = [{"id": q.id, "text": q.text, "unit": q.unit, "topic": q.topic, "category": q.category}
              for q in d.questions if not q.excluded]
    metrics = engine.compare_prediction(p.result, actual)
    ev = models.PredictionEvaluation(prediction_id=p.id, document_id=d.id, forward=d.created_at >= p.created_at,
                                     metrics=metrics)
    db.add(ev)
    db.commit()
    return ev


def _eval_out(e: models.PredictionEvaluation, db: Session) -> dict:
    d = db.get(models.Document, e.document_id)
    return {"id": e.id, "prediction_id": e.prediction_id, "document_id": e.document_id,
            "document": d.filename if d else "", "forward": e.forward, "metrics": e.metrics,
            "created_at": e.created_at.isoformat(),
            "note": ("Forward test: the prediction was made before this paper was uploaded." if e.forward else
                     "Retrospective: this paper was already uploaded when the prediction was made, so it may have "
                     "influenced the prediction. Treat these numbers with caution.")}


@router.post("/papers/{pid}/evaluate")
def evaluate_paper(pid: int, body: EvaluateIn, user=Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(models.Prediction, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Prediction not found")
    d = db.get(models.Document, body.document_id)
    if not d or d.subject_id != p.subject_id or d.kind != "question_paper":
        raise HTTPException(400, "Choose a question paper from the same subject")
    if not d.questions:
        raise HTTPException(400, "No questions were extracted from that paper yet")
    return _eval_out(evaluate_prediction(db, p, d), db)


@router.get("/papers/{pid}/evaluations")
def list_evaluations(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(models.Prediction, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Prediction not found")
    rows = db.query(models.PredictionEvaluation).filter_by(prediction_id=pid).order_by(models.PredictionEvaluation.created_at.desc()).all()
    return [_eval_out(e, db) for e in rows]
