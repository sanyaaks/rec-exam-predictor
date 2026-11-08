import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import prediction_engine
from prediction_engine import semantic

from . import models  # noqa: F401  (register tables)
from .config import CORS_ORIGINS, LLM_ENABLED
from .migrate import upgrade
from .routers import auth, insights, predict, study, subjects
from .services import ingestion
from .services.exam_config import DEFAULT_EXAM_CONFIG, DEFAULT_WEIGHTS, WEIGHT_LABELS

logging.basicConfig(level=logging.INFO)
upgrade()

app = FastAPI(title="REC Exam Predictor", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, subjects.router, predict.router, study.router, insights.router):
    app.include_router(r)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    ocr = ingestion.ocr_available()
    return {
        "llm_enabled": LLM_ENABLED,
        "ocr": ocr,
        "similarity": semantic.backend_name(),
        "engine": prediction_engine.info(),
        "default_exam_config": DEFAULT_EXAM_CONFIG,
        "default_weights": DEFAULT_WEIGHTS,
        "weight_labels": WEIGHT_LABELS,
        "limitations": [l for l in [
            None if LLM_ENABLED else "AI-written answers are off (no ANTHROPIC_API_KEY); 'Prepare' shows rule-based outlines.",
            None if ocr else "OCR engine not installed; scanned PDFs/images need Tesseract or RapidOCR, or pasted text.",
        ] if l],
    }


# Serve the built frontend (frontend/dist) when present, so one process runs everything.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
