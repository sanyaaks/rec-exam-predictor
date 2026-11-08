"""Runtime configuration. Every secret comes from the environment, never from code."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Minimal .env support (KEY=VALUE lines); real environment variables win.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# SQLite by default; point at Supabase/Postgres with
# DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'rec_predictor.db').as_posix()}")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "168"))

# Optional Supabase Auth: when set, Supabase-issued access tokens are accepted.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

# Optional LLM. Without a key the app runs fully on the rule-based fallback.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-5-5")
LLM_ENABLED = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")) and os.getenv("DISABLE_LLM") != "1"

# Optional neural embeddings (pip install sentence-transformers). TF-IDF otherwise.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "25"))
