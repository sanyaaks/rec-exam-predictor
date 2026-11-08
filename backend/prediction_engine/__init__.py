"""REC Exam Predictor - prediction engine (independent of the web app).

Hybrid architecture:
  * Sentence-BERT (all-MiniLM-L6-v2) + TF-IDF similarity          -> semantic.py, embeddings.py
  * configurable syllabus topic classification + topic discovery   -> topics.py
  * frequency/recency statistical topic ranking                    -> ranking/statistical.py
  * optional LightGBM/XGBoost topic ranker behind a data gate      -> ranking/ml.py
  * rolling-origin evaluation (P@K, R@K, NDCG@K, match rates)       -> evaluation.py, metrics.py
  * grounded question generation (LLM injected by the caller)      -> generation.py
  * structured dataset export and versioned model artifacts        -> dataset.py, registry.py
"""
from .engine import ENGINE_VERSION, compare_prediction, evaluate, info, paper, predict, train  # noqa: F401
from .records import Corpus, Paper, topic_key  # noqa: F401
