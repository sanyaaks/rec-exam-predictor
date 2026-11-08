from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now():
    return datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    department: Mapped[str] = mapped_column(String(80), default="")
    password_hash: Mapped[str] = mapped_column(String(255), default="")
    external_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # Supabase user id
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(40), default="")
    department: Mapped[str] = mapped_column(String(80), default="")
    regulation: Mapped[str] = mapped_column(String(20), default="2023")
    semester: Mapped[int] = mapped_column(Integer, default=1)
    syllabus_version: Mapped[str] = mapped_column(String(40), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    exam_config: Mapped[dict] = mapped_column(JSON, default=dict)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    units: Mapped[list["SyllabusUnit"]] = relationship(cascade="all, delete-orphan", order_by="SyllabusUnit.number")
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan", back_populates="subject")


class SyllabusUnit(Base):
    __tablename__ = "syllabus_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(300), default="")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # per-topic classification config: {topic: {"keywords": [...], "subtopics": [...]}}
    topic_meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    filename: Mapped[str] = mapped_column(String(300))
    stored_path: Mapped[str] = mapped_column(String(500), default="")
    mime: Mapped[str] = mapped_column(String(100), default="")
    # question_paper | syllabus | question_bank
    kind: Mapped[str] = mapped_column(String(30), default="question_paper")
    # CAT1 | CAT2 | SEMESTER | NA
    exam_type: Mapped[str] = mapped_column(String(20), default="NA")
    academic_year: Mapped[str] = mapped_column(String(20), default="")
    exam_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exam_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    units_covered: Mapped[list] = mapped_column(JSON, default=list)
    faculty_id: Mapped[str] = mapped_column(String(60), default="")
    # set when this is the actual paper uploaded after an exam to check a stored prediction
    feedback_for_prediction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|processing|done|needs_review|failed
    extraction_method: Mapped[str] = mapped_column(String(40), default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    subject: Mapped[Subject] = relationship(back_populates="documents")
    questions: Mapped[list["Question"]] = relationship(cascade="all, delete-orphan", back_populates="document")


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    number: Mapped[str] = mapped_column(String(10), default="")
    choice: Mapped[str] = mapped_column(String(4), default="")   # (a)/(b) either-or
    sub: Mapped[str] = mapped_column(String(6), default="")      # (i)/(ii)
    section: Mapped[str] = mapped_column(String(4), default="")  # A/B/C
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int | None] = mapped_column(Integer, nullable=True)       # marks printed for this item
    category: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 2 / 11 / 13 / 15 (question slot)
    qtype: Mapped[str] = mapped_column(String(30), default="theory")
    unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(String(300), default="")
    subtopic: Mapped[str] = mapped_column(String(200), default="")
    topic_source: Mapped[str] = mapped_column(String(20), default="")  # syllabus|keyword|manual|discovered
    topic_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    co: Mapped[str] = mapped_column(String(10), default="")
    bloom: Mapped[str] = mapped_column(String(10), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # extraction confidence
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)

    document: Mapped[Document] = relationship(back_populates="questions")


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    exam_type: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20), default="paper")  # paper | list
    title: Mapped[str] = mapped_column(String(200), default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SavedQuestion(Base):
    __tablename__ = "saved_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(String(300), default="")
    evidence: Mapped[str] = mapped_column(String(30), default="")
    priority: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20), default="not_started")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class TopicProgress(Base):
    __tablename__ = "topic_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    unit: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="not_started")  # not_started|studying|completed|revision
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Exam(Base):
    __tablename__ = "exams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    exam_type: Mapped[str] = mapped_column(String(20))
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    title: Mapped[str] = mapped_column(String(200), default="")


class PlanItem(Base):
    __tablename__ = "plan_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    date: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(300))
    unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minutes: Mapped[int] = mapped_column(Integer, default=60)
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class ModelVersion(Base):
    """A trained (or rejected) ML topic ranker for one subject. Files live under DATA_DIR/models."""
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))            # lightgbm | xgboost | none
    engine_version: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(20))          # active | candidate | rejected | archived
    gate: Mapped[dict] = mapped_column(JSON, default=dict)   # data gate + validation evidence
    train_paper_ids: Mapped[list] = mapped_column(JSON, default=list)
    train_cutoff: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_rows: Mapped[int] = mapped_column(Integer, default=0)
    artifact_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PredictionEvaluation(Base):
    """Feedback: a stored prediction compared with the paper that was actually set."""
    __tablename__ = "prediction_evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    forward: Mapped[bool] = mapped_column(Boolean, default=True)  # prediction was made before the paper was uploaded
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class GeneratedQuestion(Base):
    """AI/template-generated practice questions with provenance. Never treated as historical evidence."""
    __tablename__ = "generated_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    unit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    topic: Mapped[str] = mapped_column(String(300), default="")
    marks: Mapped[int] = mapped_column(Integer, default=13)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20), default="new_practice")   # variation | new_practice
    qtype: Mapped[str] = mapped_column(String(30), default="theory")
    source: Mapped[str] = mapped_column(String(20), default="template")     # llm | template
    model: Mapped[str] = mapped_column(String(60), default="")
    prompt_version: Mapped[str] = mapped_column(String(20), default="")
    grounding: Mapped[dict] = mapped_column(JSON, default=dict)             # retrieved past question ids/texts
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
