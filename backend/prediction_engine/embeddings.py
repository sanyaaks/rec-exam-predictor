"""Sentence embeddings.

Default: Sentence-BERT `all-MiniLM-L6-v2` (sentence-transformers) when installed and the model
can be loaded. Otherwise the engine silently uses the TF-IDF baseline in semantic.py.

ENGINE_EMBEDDINGS = auto (default) | sbert | tfidf
EMBEDDING_MODEL   = all-MiniLM-L6-v2 (default)
"""
from __future__ import annotations

import logging
import os
import threading

import numpy as np

log = logging.getLogger(__name__)

MODE = os.getenv("ENGINE_EMBEDDINGS", "auto").lower()
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "") or "all-MiniLM-L6-v2"

_model = None
_load_failed = False
_lock = threading.Lock()
_cache: dict[str, np.ndarray] = {}
_CACHE_MAX = 50_000


def _load():
    global _model, _load_failed
    if _model is not None or _load_failed or MODE == "tfidf":
        return _model
    with _lock:
        if _model is not None or _load_failed:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(MODEL_NAME, device="cpu")
            log.info("Loaded sentence embedding model %s", MODEL_NAME)
        except Exception as e:  # not installed, no network on first download, etc.
            _load_failed = True
            log.warning("Sentence-BERT unavailable (%s); using TF-IDF similarity only", e)
    return _model


def available() -> bool:
    return _load() is not None


def status() -> dict:
    ok = available()
    return {"backend": f"sbert:{MODEL_NAME}" if ok else "tfidf", "sbert": ok, "model": MODEL_NAME if ok else None,
            "mode": MODE}


def encode(texts: list[str]) -> np.ndarray | None:
    """L2-normalised embeddings, or None when SBERT is unavailable."""
    model = _load()
    if model is None:
        return None
    missing = [t for t in dict.fromkeys(texts) if t not in _cache]
    if missing:
        vecs = model.encode(missing, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        if len(_cache) + len(missing) > _CACHE_MAX:
            _cache.clear()
        for t, v in zip(missing, vecs):
            _cache[t] = np.asarray(v, dtype=np.float32)
    return np.vstack([_cache[t] for t in texts]) if texts else np.zeros((0, 384), dtype=np.float32)
