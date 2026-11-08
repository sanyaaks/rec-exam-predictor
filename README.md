# REC Exam Predictor

Upload a subject's previous CAT and semester question papers, its syllabus and faculty question banks. The app ranks the **topics** most likely to be tested in the next CAT 1, CAT 2 or end-semester exam, then the **questions** within those topics, and builds a predicted paper that follows your exam pattern. It is built around Rajalakshmi Engineering College (Anna University) patterns, and every pattern can be edited.

> Scores are **rankings** built from the evidence in your own uploads. They are not probabilities, and nothing is guaranteed to appear.

## Quick start

Requirements: Python 3.11+ and Node 18+.

```bash
# Backend (API on http://127.0.0.1:8000)
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Frontend (http://localhost:5173, proxies /api)
cd frontend && npm install && npm run dev
```

On first use, the Sentence-BERT model (`all-MiniLM-L6-v2`, about 90 MB) is downloaded from Hugging Face. Without internet access, or without `sentence-transformers` installed, the engine quietly falls back to TF-IDF similarity.

Click **Try the demo** for a guest account with a sample subject. For single-process mode, run `npm run build` in `frontend/` and start only the backend; it serves the built UI. Tests: `cd backend && .venv/Scripts/python -m pytest -q` (24 tests; they also pass with `ENGINE_EMBEDDINGS=tfidf`).

**The sample subject is synthetic.** "Computer Networks (Sample)" contains papers written for the demo. They are not real REC or Anna University papers, and they are labelled "Sample data" everywhere.

## Architecture

```
frontend/ (React + TS + Tailwind + Recharts)
    │ REST
backend/app/            FastAPI: auth, uploads, extraction, DB, routers  (the app)
    │ plain records in / plain dicts out (services/engine_adapter.py)
backend/prediction_engine/   independent package: no FastAPI or DB imports
    ├─ records.py        Paper / Corpus / topic keys, plus the leakage guard Corpus.before(t)
    ├─ embeddings.py     Sentence-BERT all-MiniLM-L6-v2 (cached), optional
    ├─ semantic.py       TF-IDF baseline + SBERT blend; duplicate detection; concept clustering
    ├─ topics.py         configurable syllabus classifier (keywords, acronyms, subtopics); topic discovery
    ├─ features.py       topic-level features at a cutoff date (frequency, recency, cycle, unit rotation…)
    ├─ ranking/statistical.py   frequency/recency six-factor topic ranker (default)
    ├─ ranking/ml.py     LightGBM (or XGBoost) topic ranker, used only behind a data gate
    ├─ predictor.py      question-level scoring, topic-score blending, paper assembly
    ├─ evaluation.py     rolling-origin backtest; metrics.py: P@K, R@K, NDCG@K
    ├─ generation.py     LLM question generation grounded in the syllabus and retrieved past questions
    ├─ dataset.py        structured training dataset (18 fields)
    ├─ registry.py       versioned model files (DATA_DIR/models/subject_<id>/v<N>/)
    └─ engine.py         facade: predict, paper, train, evaluate, compare_prediction
```

The engine can be retrained or replaced without rebuilding the frontend.

### Database

SQLite by default, or Postgres/Supabase via `DATABASE_URL`. New columns and tables are added automatically at startup (`app/migrate.py`, additive only).

`users`, `subjects` (+`syllabus_version`), `syllabus_units` (+`topic_meta`: keywords and subtopics per topic), `documents` (+`faculty_id`, `feedback_for_prediction_id`), `questions` (+`subtopic`, `topic_source`, `normalized_text`), `predictions` (+`model_version_id`, plus a topic-ranking snapshot), **`model_versions`**, **`prediction_evaluations`**, **`generated_questions`**, `saved_questions`, `topic_progress`, `exams`, `plan_items`.

## Prediction methodology

1. **Extraction and mapping.** Each question is parsed (number, (a)/(b), (i)/(ii), marks, CO/BL, part) and classified to a 2/11/13/15-mark slot and a question type. It is then mapped to a syllabus **unit → topic → subtopic**. The classifier is configurable per subject:
   - topic keywords you define (for example "three-way handshake" → *TCP Connection Management*)
   - automatic acronyms (*Virtual LAN* ↔ VLAN)
   - topic-name matches
   - semantic similarity, with a minimum-similarity threshold

   Anything below the threshold goes to the **Review** queue along with uncertain or OCR extractions.
2. **Semantic matching.** The TF-IDF baseline (word and character n-grams plus weighted key-term overlap) is blended with Sentence-BERT. Calibration showed MiniLM alone over-rates short questions that share a protocol name (it scores "TCP congestion control" vs "TCP connection management" at 0.82), so SBERT is a 30% signal. The merge threshold (0.51 with SBERT, 0.37 TF-IDF only) is pinned by must-merge and must-separate tests.
3. **Topic ranking first.** Separate configurations for **CAT 1, CAT 2 and Semester** (units in scope, pattern, weights, ranker mode). Students can override the units for a single prediction. Every syllabus topic in scope, plus every concept that maps to no syllabus topic, gets features computed only from earlier papers.
   - **Statistical ranker:** a weighted score from historical frequency, recency and repetition cycle, syllabus importance, unit rotation, marks pattern and variants.
   - **ML ranker (optional):** LightGBM, pooled across exam types, trained on rolling-origin rows. It is used only when the **data gate** passes (at least 8 dated papers, at least 5 origins, at least 25 topic appearances) **and** it beats the statistical ranker on NDCG@R over held-out later papers. Otherwise the app says it is using statistical ranking and why. ML output is shown as a rank-percentile score blended 50/50 with the statistical score, never as a probability.
4. **Then questions.** Priority = 0.6 × topic score + 0.4 × question score. Each item is labelled as one of: exact repeat, repeated concept (reworded), asked once, question bank only, or practice question (untested syllabus topic). The `wording` field (`past` / `past_other_marks` / `generated`) keeps real past wording separate from generated wording.
5. **Grounded generation.** AI practice questions for a topic are generated by Claude (`claude-opus-5-5`, structured output). The prompt contains the syllabus topic and the most similar past questions retrieved by similarity. Each result records which past questions it was based on. Outputs that duplicate a past question are discarded. Without an API key, deterministic templates are used and labelled as such.

## Validation

Validation uses chronological rolling-origin evaluation, never random splits. Each dated paper is predicted using only papers dated before it. Question banks are excluded because their dates are unknown, and at each origin the ML model is trained only on earlier origins. Results are reported per exam type and overall for the **frequency baseline, statistical and ML** rankers:

| Metric | Meaning |
|---|---|
| Precision@K | Of the top K predicted topics, the share that were actually asked |
| Recall@K | Of the topics actually asked, the share found in the top K |
| NDCG@K | Ranking quality, weighting topics by how many questions they got (K = 5, 10, and R = number of topics actually asked) |
| Exact question match rate | Actual questions that match a predicted question almost word for word |
| Semantic topic match rate | Actual questions matched by concept, or whose topic was in the top R |
| Unit coverage | Units of the actual paper that the predicted questions cover |

Topics in the actual paper that the ranking could never contain (marked `novel:`) still count against recall. On the bundled synthetic demo (6 evaluation origins), statistical ranking is roughly level with the frequency-only baseline: Precision@5 is 70% vs 67%, semantic topic match 73% vs 72%, and NDCG@R 0.53 vs 0.54. That is expected, because the synthetic papers were generated mostly from frequency. The LightGBM model is trained but **rejected by the gate**, because it does not beat statistical ranking on the held-out papers. That is the intended behaviour with little data. Real papers are needed to tell whether the extra signals help for a given subject.

**Feedback loop.** After an exam, upload the actual paper and tick "this is the actual paper for prediction X", or compare later from the paper page. The stored prediction snapshot is compared with the real paper and the paper joins the dataset. A comparison is labelled *forward* (the prediction was made before the paper was uploaded) or *retrospective*. Retraining creates a new model version; earlier versions can be re-activated.

## Main API additions

| Endpoint | Purpose |
|---|---|
| `GET /api/subjects/{id}/readiness?exam_type=` | Pre-prediction checklist: syllabus, units, pattern confirmed, past CAT/semester papers, question banks, regulation, subject code, undated papers, review queue, model status |
| `GET /api/subjects/{id}/predictions?exam_type=&units=` | Ranked topics, then ranked questions, plus ranker info |
| `GET /api/subjects/{id}/backtest` · `/backtest/weights` | Rolling-origin metrics · weight-preset comparison |
| `GET/POST /api/subjects/{id}/models[/train]`, `POST /api/models/{id}/activate\|archive` | Versioned ML models |
| `GET /api/subjects/{id}/review`, `POST …/discover[/apply]` | Review queue, topic discovery (BERTopic when installed and there are ≥ 50 unmapped questions; built-in clustering + c-TF-IDF otherwise) |
| `POST /api/subjects/{id}/generate`, `GET …/generated` | Grounded question generation |
| `GET /api/subjects/{id}/dataset?format=csv\|json` | Structured dataset |
| `POST /api/papers/{id}/evaluate`, `GET …/evaluations` | Post-exam feedback |

The dataset contains these fields: `subject_code, subject_name, regulation, semester, department, academic_year, examination_year, examination_type, faculty_id, question_text, normalized_question, marks, question_type, unit, topic, subtopic, syllabus_version, previous_appearance_count`. The last field counts earlier papers containing the same concept only; it is empty for undated papers.

## Configuration

| Variable | Effect |
|---|---|
| `JWT_SECRET` | **Set this in production** |
| `DATABASE_URL` | Postgres/Supabase (`postgresql+psycopg://…`, `pip install psycopg[binary]`) |
| `SUPABASE_JWT_SECRET` | Also accept Supabase Auth tokens |
| `ANTHROPIC_API_KEY` | AI answers and AI practice questions (Claude, with server-side refusal fallback). Without it, templates and outlines are used, and labelled. |
| `ENGINE_EMBEDDINGS` | `auto` (default) · `sbert` · `tfidf` |
| `EMBEDDING_MODEL` | Default `all-MiniLM-L6-v2` |

## Known limitations

- OCR needs Tesseract or `rapidocr-onnxruntime`. Without one, scanned pages are flagged and students can paste the text instead.
- MiniLM is a general-purpose model. Domain-specific synonyms still need topic keywords or a review in the Review tab.
- The ML ranker needs several years of dated papers per subject before it can pass its gate. Until then, ranking is statistical by design.
- Weights, thresholds and gates are heuristics checked against your own history. They are not proven constants.
