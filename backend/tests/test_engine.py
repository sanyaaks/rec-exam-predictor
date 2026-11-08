"""Tests for the standalone prediction engine: metrics, leakage guards, ML gate, topic
classification/discovery, grounded generation, dataset export and feedback comparison."""
import math
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="recpred_engine_"))
os.environ["DISABLE_LLM"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.exam_config import DEFAULT_EXAM_CONFIG  # noqa: E402
from prediction_engine import dataset, evaluation, generation, metrics, semantic, topics  # noqa: E402
from prediction_engine.config import normalize  # noqa: E402
from prediction_engine.engine import compare_prediction, paper, predict, train  # noqa: E402
from prediction_engine.features import topic_table  # noqa: E402
from prediction_engine.ranking import ml  # noqa: E402
from prediction_engine.records import Corpus, Paper  # noqa: E402

CFG = dict(DEFAULT_EXAM_CONFIG)
W = normalize(None)
UNITS = [
    {"number": 1, "title": "Application layer", "topics": ["DNS", "HTTP", "Electronic Mail (SMTP, POP3)"], "hours": 9,
     "topic_meta": {}},
    {"number": 2, "title": "Transport layer", "topics": ["TCP Connection Management", "Congestion Control", "UDP"],
     "hours": 9, "topic_meta": {"TCP Connection Management": {"keywords": ["three-way handshake"]}}},
    {"number": 3, "title": "Network layer", "topics": ["IPv6", "Subnetting", "ARP"], "hours": 9, "topic_meta": {}},
    {"number": 4, "title": "Routing", "topics": ["Distance Vector Routing", "Link State Routing", "BGP"], "hours": 9,
     "topic_meta": {}},
    {"number": 5, "title": "Data link", "topics": ["CRC", "Virtual LAN", "CSMA/CD"], "hours": 9, "topic_meta": {}},
]


# ---------------------------------------------------------------- metrics
def test_ranking_metrics_hand_computed():
    ranked = ["a", "b", "c", "d"]
    gains = {"a": 2, "c": 1, "novel:x": 1}       # 3 relevant topics, one unretrievable
    assert metrics.precision_at_k(ranked, gains, 2) == 0.5
    assert math.isclose(metrics.recall_at_k(ranked, gains, 4), 2 / 3)
    dcg = (2 ** 2 - 1) / math.log2(2) + (2 ** 1 - 1) / math.log2(4)
    idcg = (2 ** 2 - 1) / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert math.isclose(metrics.ndcg_at_k(ranked, gains, 4), dcg / idcg)
    rep = metrics.ranking_report(ranked, gains)
    assert rep["relevant_topics"] == 3 and rep["novel_topics"] == 1


# ---------------------------------------------------------------- semantic calibration
MERGE = [("Explain the architecture of IPv6.", "Describe the IPv6 packet header format."),
         ("Explain the architecture of IPv6.", "Draw and explain the structure of an IPv6 packet."),
         ("Explain the TCP segment structure.", "Draw the TCP header format and explain each field.")]
SEPARATE = [("Explain distance vector routing with an example.", "Explain link state routing."),
            ("Explain TCP congestion control.", "Explain TCP connection management."),
            ("Describe the IPv6 packet header format.", "Explain the IPv4 header format with a neat diagram."),
            ("Differentiate between TCP and UDP.", "Explain UDP datagram format and its applications.")]


def test_semantic_pairs_merge_and_separate():
    th = semantic.same_concept()
    for a, b in MERGE:
        assert semantic.similarity_matrix([a], [b])[0, 0] >= th, (a, b)
    for a, b in SEPARATE:
        assert semantic.similarity_matrix([a], [b])[0, 0] < th, (a, b)


# ---------------------------------------------------------------- topic classification & discovery
def test_classifier_keywords_acronyms_and_unmapped():
    qs = ["What is the three-way handshake?", "What is a VLAN?", "Explain the architecture of IPv6.",
          "Discuss the ethics of artificial intelligence in journalism."]
    out = topics.classify(qs, UNITS)
    assert out[0]["topic"] == "TCP Connection Management" and out[0]["source"] == "keyword"
    assert out[1]["topic"] == "Virtual LAN"
    assert out[2]["topic"] == "IPv6" and out[2]["unit"] == 3
    assert out[3]["topic"] == "" and out[3]["alternatives"] is not None
    sub = topics.classify(["Explain how SMTP delivers mail."], UNITS)[0]
    assert sub["topic"].startswith("Electronic Mail") and sub["subtopic"] == "SMTP"
    strict = topics.classify(["What is a VLAN?"], UNITS, cfg={"min_similarity": 0.99, "keyword_score": 0.5,
                                                              "name_match_score": 0.5})[0]
    assert strict["topic"] == ""   # configurable threshold


def test_topic_discovery_groups_unmapped_questions():
    qs = [{"id": 1, "text": "Explain the count-to-infinity problem.", "unit": 4},
          {"id": 2, "text": "How is the count-to-infinity problem solved?", "unit": 4},
          {"id": 3, "text": "What is split horizon with poisoned reverse?", "unit": 4},
          {"id": 4, "text": "Explain split horizon.", "unit": 4},
          {"id": 5, "text": "Explain the Nyquist theorem.", "unit": 5}]
    res = topics.discover(qs, UNITS)
    groups = [set(t["question_ids"]) for t in res["topics"]]
    assert {1, 2} in groups and {3, 4} in groups
    assert 5 in res["unclustered"]
    assert all(t["keywords"] for t in res["topics"])


# ---------------------------------------------------------------- corpus helpers
def _corpus(n_years=4):
    papers, qs, qid = [], [], 0
    plan = {  # exam_type, month, questions [(text, cat, unit, topic)]
        "SEMESTER": [("Explain the architecture of IPv6.", 13, 3, "IPv6"), ("Explain distance vector routing.", 13, 4, "Distance Vector Routing"),
                     ("What is CRC?", 2, 5, "CRC"), ("What is the role of DNS?", 2, 1, "DNS"),
                     ("Explain TCP congestion control.", 13, 2, "Congestion Control")],
        "CAT1": [("What is the role of DNS?", 2, 1, "DNS"), ("Explain HTTP message formats.", 11, 1, "HTTP"),
                 ("Explain TCP congestion control.", 11, 2, "Congestion Control")],
        "CAT2": [("Explain the architecture of IPv6.", 11, 3, "IPv6"), ("Explain subnetting with an example.", 11, 3, "Subnetting"),
                 ("Explain link state routing.", 11, 4, "Link State Routing")],
    }
    pid = 0
    for y in range(2020, 2020 + n_years):
        for et, month in (("CAT1", 8), ("CAT2", 10), ("SEMESTER", 11)):
            pid += 1
            papers.append(Paper(pid, et, y, month, f"{et} {y}", units_covered=[1, 2] if et == "CAT1" else ([3, 4] if et == "CAT2" else [])))
            for i, (t, cat, u, tp) in enumerate(plan[et]):
                if (y + i) % 3 == 0 and i > 0:   # some rotation so not everything repeats every year
                    continue
                qid += 1
                qs.append({"id": qid, "text": t, "category": cat, "unit": u, "topic": tp, "subtopic": "",
                           "qtype": "theory", "paper_id": pid, "number": str(i + 1)})
    return Corpus(papers=papers, questions=qs, units=UNITS)


# ---------------------------------------------------------------- leakage guards
def test_rolling_origins_never_see_the_future():
    corpus = _corpus()
    units = evaluation.build_units(corpus, CFG)
    assert units
    for u in units:
        o = u["origin"]
        assert all(p.t < o.t for p in u["train"].papers)
        train_ids = {q["id"] for q in u["train"].questions}
        assert not train_ids & {q["id"] for q in u["hidden"]}
        assert not u["train"].bank_questions   # undated question banks never used for evaluation


def test_features_unchanged_by_future_papers():
    corpus = _corpus()
    cutoff = corpus.papers[5].t
    past = corpus.before(cutoff)
    future_only = Corpus(papers=[p for p in corpus.papers if p.t < cutoff], questions=[q for q in corpus.questions
                         if q["paper_id"] in {p.id for p in corpus.papers if p.t < cutoff}], units=UNITS)
    a = {r["key"]: r["features"] for r in topic_table(past, "SEMESTER", [1, 2, 3, 4, 5])}
    b = {r["key"]: r["features"] for r in topic_table(future_only.before(cutoff), "SEMESTER", [1, 2, 3, 4, 5])}
    assert a == b


def test_ml_ranker_only_sees_earlier_origins_in_backtest():
    corpus = _corpus(5)
    res = evaluation.run(corpus, CFG, lambda _et: W, include_ml=True)
    assert res["folds"]
    for f in res["folds"]:
        target = next(p for p in corpus.papers if p.id == f["paper_id"])
        assert f["train_papers"] == sum(1 for p in corpus.papers if p.t < target.t)
        for name in ("frequency_baseline", "statistical"):
            for k in ("precision@5", "recall@10", "ndcg@10", "exact_match_rate", "semantic_topic_match_rate", "unit_coverage"):
                assert k in f[name]
    assert set(res["by_exam_type"]) <= {"CAT1", "CAT2", "SEMESTER"}


# ---------------------------------------------------------------- ML gate
def test_small_dataset_falls_back_to_statistical():
    small = _corpus(1)            # 3 papers only
    res = train(small, CFG, lambda _et: W)
    assert res["gate"]["use_ml"] is False and "statistical" in res["gate"]["reason"].lower()


def test_ml_fit_and_apply_produce_rank_scores_not_probabilities():
    corpus = _corpus(5)
    units = evaluation.build_units(corpus, CFG)
    bundle = ml.fit(units)
    assert bundle is not None and bundle["kind"] in ("lightgbm", "xgboost")
    pred = predict(corpus, "SEMESTER", CFG, W, ml_bundle=bundle)
    assert pred["ranker"] == "ml"
    scores = [t["ml_rank_score"] for t in pred["topics"]]
    assert max(scores) == 100.0 and min(scores) == 0.0   # rank percentile, explicitly not a probability


def test_separate_exam_configs_and_unit_scope():
    corpus = _corpus()
    cat1 = predict(corpus, "CAT1", CFG, W)
    assert {t["unit"] for t in cat1["topics"]} <= {1, 2}
    override = predict(corpus, "SEMESTER", CFG, W, scope_override=[3])
    assert {t["unit"] for t in override["topics"]} <= {3}
    assert all(it["unit"] in (3, None) for it in override["items"])


# ---------------------------------------------------------------- generation
def test_generation_is_grounded_labelled_and_deduplicated():
    pool = [{"id": 1, "text": "Explain the architecture of IPv6.", "unit": 3, "qtype": "theory"},
            {"id": 2, "text": "List the advantages of IPv6 over IPv4.", "unit": 3, "qtype": "definition"},
            {"id": 3, "text": "Explain CSMA/CD.", "unit": 5, "qtype": "theory"}]
    retrieved = generation.retrieve("IPv6 IPv6", pool, unit=3)
    assert [r["id"] for r in retrieved][:2] == [1, 2] or {r["id"] for r in retrieved[:2]} == {1, 2}

    def fake_llm(system, prompt, schema):
        assert "IPv6" in prompt and "Explain the architecture of IPv6." in prompt
        return {"questions": [
            {"text": "Explain the architecture of IPv6.", "kind": "variation", "question_type": "theory", "based_on": [0]},
            {"text": "Compare IPv6 extension headers with IPv4 options.", "kind": "new_practice",
             "question_type": "comparison", "based_on": [0, 9]}]}

    res = generation.generate("IPv6", 3, "Network layer", 13, 2, retrieved, ["IPv6", "ARP"], "CN", llm_json=fake_llm)
    assert res["source"] == "llm"
    assert len(res["questions"]) == 1 and res["questions"][0]["based_on"] == [retrieved[0]["id"]]  # bad index dropped
    assert res["discarded"] and res["discarded"][0]["reason"] == "Duplicates a past question"
    tmpl = generation.generate("IPv6", 3, "Network layer", 13, 3, retrieved, ["IPv6"], "CN")
    assert tmpl["source"] == "template" and all(q["source"] == "template" for q in tmpl["questions"])


# ---------------------------------------------------------------- dataset
def test_dataset_fields_and_leakage_free_appearance_count():
    papers = [{"id": 1, "exam_type": "SEMESTER", "exam_year": 2022, "exam_month": 11, "academic_year": "2022-23"},
              {"id": 2, "exam_type": "SEMESTER", "exam_year": 2023, "exam_month": 11, "academic_year": "2023-24"},
              {"id": 3, "exam_type": "CAT1", "exam_year": None, "exam_month": None, "academic_year": ""}]
    qs = [{"id": 1, "paper_id": 1, "text": "Explain the architecture of IPv6.", "category": 13, "unit": 3, "topic": "IPv6"},
          {"id": 2, "paper_id": 2, "text": "Explain the architecture of IPv6.", "category": 13, "unit": 3, "topic": "IPv6"},
          {"id": 3, "paper_id": 3, "text": "Explain the architecture of IPv6.", "category": 11, "unit": 3, "topic": "IPv6"}]
    rows = dataset.build({"code": "CS1", "name": "CN"}, papers, qs)
    assert list(rows[0].keys()) == dataset.FIELDS
    assert [r["previous_appearance_count"] for r in rows] == [0, 1, None]   # undated -> unknown, never guessed


# ---------------------------------------------------------------- feedback
def test_compare_prediction_with_actual_paper():
    corpus = _corpus()
    pred = predict(corpus, "SEMESTER", CFG, W)
    snap = paper(pred, "SEMESTER", CFG)
    actual = [{"id": 900, "text": "Explain the architecture of IPv6.", "unit": 3, "topic": "IPv6"},
              {"id": 901, "text": "Explain the Nyquist theorem.", "unit": 5, "topic": ""}]
    res = compare_prediction(snap, actual)
    assert res["counts"]["exact"] >= 1 and res["novel_topics"] >= 1 and res["actual_questions"] == 2


# ---------------------------------------------------------------- API-level
def test_api_readiness_units_override_training_and_feedback_upload():
    c = TestClient(app)
    H = {"Authorization": "Bearer " + c.post("/api/auth/guest").json()["token"]}
    sid = c.get("/api/subjects", headers=H).json()[0]["id"]
    r = c.get(f"/api/subjects/{sid}/readiness?exam_type=CAT1", headers=H).json()
    assert {ch["key"] for ch in r["checks"]} >= {"syllabus", "units", "pattern", "same_type", "banks", "regulation", "code", "review"}
    p = c.get(f"/api/subjects/{sid}/predictions?exam_type=SEMESTER&units=2", headers=H).json()
    assert p["units"] == [2] and p["topics"] and p["ranker"]["used"] in ("statistical", "ml")
    t = c.post(f"/api/subjects/{sid}/models/train", headers=H).json()
    assert t["model"]["status"] in ("active", "rejected") and t["message"]
    paper_ = c.post(f"/api/subjects/{sid}/papers", headers=H, json={"exam_type": "SEMESTER"}).json()
    assert paper_["paper"]["topic_ranking"]
    text = "PART A (2 x 2 = 4 marks)\n1. What is the purpose of ARP?\n2. What is a VLAN?\n"
    doc = c.post(f"/api/subjects/{sid}/documents/text", headers=H, json={
        "text": text, "exam_type": "SEMESTER", "exam_year": 2025, "exam_month": 11,
        "feedback_for_prediction_id": paper_["id"], "title": "Actual Nov 2025"}).json()
    assert doc["evaluation"] and doc["evaluation"]["forward"] is True
    assert c.get(f"/api/papers/{paper_['id']}/evaluations", headers=H).json()
    ds = c.get(f"/api/subjects/{sid}/dataset?format=csv", headers=H)
    assert ds.status_code == 200 and ds.text.splitlines()[0].startswith("subject_code,subject_name")
