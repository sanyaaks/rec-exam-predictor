import csv
import io
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..auth import current_user
from ..db import get_db
from ..deps import get_subject, subject_out
import prediction_engine as engine
from prediction_engine import evaluation, semantic
from prediction_engine.predictor import build_clusters, confidence_level, priority_for

from ..services import engine_adapter, pdf, pipeline, study
from ..services.exam_config import EXAM_TYPES, WEIGHT_LABELS, merged_config, normalized_weights

router = APIRouter(prefix="/api", tags=["predictions"])


def _check_type(exam_type: str):
    if exam_type not in EXAM_TYPES:
        raise HTTPException(400, "exam_type must be CAT1, CAT2 or SEMESTER")


def _engine_info(subject, exam_type: str = "SEMESTER") -> dict:
    return {"similarity": semantic.backend_name(), "engine_version": engine.ENGINE_VERSION,
            "weights": normalized_weights(subject.weights, exam_type),
            "weight_labels": WEIGHT_LABELS,
            "disclaimer": ("Scores rank questions by evidence from your uploaded papers and syllabus. They are not "
                           "probabilities and no question is guaranteed to appear.")}


# ------------------------------------------------------------------ analysis dashboard
@router.get("/subjects/{sid}/analysis")
def analysis(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    corpus = pipeline.load_corpus(db, s)
    cfg = merged_config(s.exam_config)
    papers = {p.id: p for p in corpus.papers}
    qs = corpus.questions
    units = [u["number"] for u in corpus.units] or list(range(1, cfg.get("units_count", 5) + 1))

    unit_freq = Counter(q["unit"] for q in qs if q["unit"])
    unit_by_type = {u: {"CAT1": 0, "CAT2": 0, "SEMESTER": 0} for u in units}
    marks_by_type = defaultdict(Counter)
    qtype_counts = Counter(q["qtype"] for q in qs)
    year_type = defaultdict(lambda: {"CAT1": 0, "CAT2": 0, "SEMESTER": 0})
    for q in qs:
        p = papers[q["paper_id"]]
        if q["unit"] in unit_by_type:
            unit_by_type[q["unit"]][p.exam_type] += 1
        marks_by_type[p.exam_type][q["category"]] += 1
        if p.year:
            year_type[p.year][p.exam_type] += 1

    clusters = build_clusters(engine.Corpus(papers=corpus.papers, questions=qs, units=corpus.units))
    topic_rows = []
    for c in clusters:
        if not c["members"]:
            continue
        pids = {m["paper_id"] for m in c["members"]}
        topic_rows.append({
            "label": c["members"][0]["text"][:90], "topic": c["topic"], "unit": c["unit"],
            "papers": len(pids), "questions": len(c["members"]),
            "cat": sum(1 for pid in pids if papers[pid].exam_type in ("CAT1", "CAT2")),
            "semester": sum(1 for pid in pids if papers[pid].exam_type == "SEMESTER"),
            "example": c["members"][0]["text"],
        })
    topic_rows.sort(key=lambda r: (-r["papers"], -r["questions"]))

    # unit priority: mean of the top-3 semester topic scores per unit
    unit_priority = []
    if qs or corpus.units:
        pred, _, _ = engine_adapter.run_predict(db, s, "SEMESTER", units)
        best = defaultdict(list)
        for t in pred["topics"]:
            if t["unit"]:
                best[t["unit"]].append(t["score"])
        for u in units:
            top = sorted(best.get(u, []), reverse=True)[:3]
            sc = round(sum(top) / len(top), 1) if top else 0
            unit_priority.append({"unit": u, "score": sc, "priority": priority_for(sc, cfg)})

    syllabus_topics = {(u["number"], t) for u in corpus.units for t in u["topics"]}
    asked = {(q["unit"], q["topic"]) for q in qs if q["topic"]}
    unit_titles = {u["number"]: u["title"] for u in corpus.units}
    return {
        "papers": [{"id": p.id, "label": p.label, "exam_type": p.exam_type, "year": p.year,
                    "questions": sum(1 for q in qs if q["paper_id"] == p.id)} for p in corpus.papers],
        "totals": {"papers": len(corpus.papers), "questions": len(qs), "bank_questions": len(corpus.bank_questions),
                   "syllabus_topics": len(syllabus_topics), "topics_asked": len(asked & syllabus_topics),
                   "concepts": len(topic_rows), "repeated_concepts": sum(1 for r in topic_rows if r["papers"] >= 2)},
        "units": [{"unit": u, "title": unit_titles.get(u, ""), "questions": unit_freq.get(u, 0), **unit_by_type[u]}
                  for u in units],
        "unassigned_unit": sum(1 for q in qs if not q["unit"]),
        "marks_by_type": {et: {str(k): v for k, v in c.items() if k} for et, c in marks_by_type.items()},
        "qtypes": [{"qtype": k, "count": v} for k, v in qtype_counts.most_common()],
        "by_year": [{"year": y, **v} for y, v in sorted(year_type.items())],
        "top_topics": topic_rows[:15],
        "unit_priority": unit_priority,
        "untested_topics": [{"unit": u, "topic": t} for (u, t) in sorted(syllabus_topics - asked)][:40],
        "confidence": confidence_level(len(corpus.papers), len(corpus.papers)),
    }



# ------------------------------------------------------------------ predictions
def _units_param(units: str | None) -> list[int] | None:
    if not units:
        return None
    try:
        return sorted({int(u) for u in units.split(",") if u.strip()})
    except ValueError:
        raise HTTPException(400, "units must be a comma-separated list of unit numbers")


@router.get("/subjects/{sid}/predictions")
def predictions(sid: int, exam_type: str = "SEMESTER", units: str | None = None,
                user=Depends(current_user), db: Session = Depends(get_db)):
    """Topic ranking first, then question ranking. `units` overrides the exam's configured units."""
    _check_type(exam_type)
    s = get_subject(db, user, sid)
    pred, rinfo, cfg = engine_adapter.run_predict(db, s, exam_type, _units_param(units))
    items = pred["items"]
    return {"exam_type": exam_type, "items": items, "topics": pred["topics"], "confidence": pred["confidence"],
            "unit_stats": pred["unit_stats"], "units": pred["scope"], "configured_units": cfg[exam_type]["units"],
            "ranker": rinfo, "engine": _engine_info(s, exam_type), "counts": dict(Counter(i["priority"] for i in items))}


@router.get("/subjects/{sid}/predictions/export")
def export_predictions(sid: int, exam_type: str = "SEMESTER", format: str = "pdf", units: str | None = None,
                       user=Depends(current_user), db: Session = Depends(get_db)):
    _check_type(exam_type)
    s = get_subject(db, user, sid)
    pred, _, cfg = engine_adapter.run_predict(db, s, exam_type, _units_param(units))
    items = pred["items"]
    name = f"{(s.code or s.name).replace(' ', '_')}_{exam_type}_predictions"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["question", "marks", "unit", "topic", "priority", "priority_score", "topic_score", "question_score",
                    "evidence", "wording", "papers_asked", "years", "reasons"])
        for it in items:
            w.writerow([it["text"], it["marks"], it["unit"] or "", it["topic"], it["priority_label"], it["score"],
                        it.get("topic_score"), it.get("question_score"), it["evidence_label"], it["wording"],
                        it["frequency"]["papers"], " ".join(map(str, it["years"])), " | ".join(it["reasons"])])
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    data = pdf.render_list(items, subject_out(s), f"Predicted questions - {cfg[exam_type]['label']}")
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


class PaperIn(BaseModel):
    exam_type: str
    seed: int = 0
    title: str = ""
    units: list[int] | None = None


@router.post("/subjects/{sid}/papers")
def generate_paper(sid: int, body: PaperIn, user=Depends(current_user), db: Session = Depends(get_db)):
    _check_type(body.exam_type)
    s = get_subject(db, user, sid)
    pred, rinfo, cfg = engine_adapter.run_predict(db, s, body.exam_type, body.units)
    if not pred["scored"]["candidates"]:
        raise HTTPException(400, "Nothing to predict from yet - upload past papers or add the syllabus first.")
    paper = engine.paper(pred, body.exam_type, cfg, seed=body.seed)
    paper["ranker_info"] = rinfo
    n = db.query(models.Prediction).filter_by(subject_id=s.id, user_id=user.id, exam_type=body.exam_type).count()
    p = models.Prediction(subject_id=s.id, user_id=user.id, exam_type=body.exam_type, kind="paper",
                          title=body.title or f"{paper['label']} prediction #{n + 1}",
                          params={"seed": body.seed, "units": pred["scope"],
                                  "weights": normalized_weights(s.weights, body.exam_type),
                                  "engine_version": engine.ENGINE_VERSION, "ranker": rinfo},
                          result=paper, model_version_id=rinfo.get("model_version_id"))
    db.add(p)
    db.commit()
    return {"id": p.id, "title": p.title, "created_at": p.created_at.isoformat(), "paper": paper,
            "subject": subject_out(s), "engine": _engine_info(s, body.exam_type)}


@router.get("/subjects/{sid}/papers")
def list_papers(sid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    get_subject(db, user, sid)
    rows = (db.query(models.Prediction).filter_by(subject_id=sid, user_id=user.id)
            .order_by(models.Prediction.created_at.desc()).all())
    evals = {e.prediction_id for e in db.query(models.PredictionEvaluation).join(models.Prediction)
             .filter(models.Prediction.subject_id == sid).all()}
    return [{"id": p.id, "title": p.title, "exam_type": p.exam_type, "created_at": p.created_at.isoformat(),
             "total_marks": p.result.get("total_marks"), "confidence": (p.result.get("confidence") or {}).get("level"),
             "ranker": p.result.get("ranker", "statistical"), "evaluated": p.id in evals}
            for p in rows]


def _get_paper(db, user, pid) -> models.Prediction:
    p = db.get(models.Prediction, pid)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Prediction not found")
    return p


@router.get("/papers/{pid}")
def get_paper(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _get_paper(db, user, pid)
    s = db.get(models.Subject, p.subject_id)
    return {"id": p.id, "title": p.title, "created_at": p.created_at.isoformat(), "paper": p.result,
            "subject": subject_out(s), "engine": _engine_info(s, p.exam_type)}


@router.delete("/papers/{pid}")
def delete_paper(pid: int, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _get_paper(db, user, pid)
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/papers/{pid}/pdf")
def paper_pdf(pid: int, notes: bool = True, user=Depends(current_user), db: Session = Depends(get_db)):
    p = _get_paper(db, user, pid)
    s = db.get(models.Subject, p.subject_id)
    data = pdf.render_paper(p.result, subject_out(s), include_notes=notes)
    fname = f"{(s.code or s.name).replace(' ', '_')}_{p.exam_type}_predicted_paper.pdf"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ------------------------------------------------------------------ validation
@router.get("/subjects/{sid}/backtest")
def run_backtest(sid: int, include_ml: bool = True, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    cfg = merged_config(s.exam_config)
    corpus = pipeline.load_corpus(db, s)
    res = engine.evaluate(corpus, cfg, engine_adapter.weights_for(s), include_ml=include_ml)
    undated = [p.label for p in corpus.papers if not p.dated]
    res["undated_papers"] = undated
    return res


@router.get("/subjects/{sid}/backtest/weights")
def compare_weight_presets(sid: int, exam_type: str | None = None, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    cfg = merged_config(s.exam_config)
    current = normalized_weights(s.weights, exam_type) if exam_type else normalized_weights(s.weights, "SEMESTER")
    res = evaluation.compare_weights(pipeline.load_corpus(db, s), cfg, current, exam_type)
    res["exam_type"] = exam_type
    return res


# ------------------------------------------------------------------ study material
class PrepareIn(BaseModel):
    text: str
    marks: int = 13
    qtype: str = "theory"
    topic: str = ""
    unit: int | None = None
    related: list[str] = []


@router.post("/subjects/{sid}/prepare")
def prepare(sid: int, body: PrepareIn, user=Depends(current_user), db: Session = Depends(get_db)):
    s = get_subject(db, user, sid)
    return study.prepare(body.text, body.marks, body.qtype, body.topic, body.unit, s.name,
                         pipeline.subject_units(s), body.related)
