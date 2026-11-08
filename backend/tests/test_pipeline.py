"""End-to-end and unit tests for the checklist in the product spec:
uploads, PDF extraction, classification, semantic duplicates, scoring,
paper generation, PDF export, the full workflow, and leakage-free backtesting."""
import io
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="recpred_test_")
os.environ["DATA_DIR"] = _tmp
os.environ["DISABLE_LLM"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import extraction  # noqa: E402
from prediction_engine import evaluation, predictor, semantic  # noqa: E402
from app.services.exam_config import DEFAULT_EXAM_CONFIG, DEFAULT_WEIGHTS, normalized_weights  # noqa: E402

client = TestClient(app)

AU_PAPER = """B.E./B.Tech. DEGREE EXAMINATION, NOVEMBER/DECEMBER 2023
Fifth Semester
Computer Science and Engineering
Time : Three hours Maximum : 100 marks
Answer ALL questions.
PART A — (10 × 2 = 20 marks)
1. Define protocol.
2. What is the role of DNS?
3. Differentiate TCP and UDP.
4. What is congestion?
5. What is subnetting?
6. List the advantages of IPv6.
7. What is BGP?
8. What is split horizon?
9. What is CRC?
10. What is a VLAN?
PART B — (5 × 13 = 65 marks)
11. (a) (i) Explain the OSI model with a neat diagram. (7)
(ii) Compare OSI and TCP/IP models. (6)
Or
(b) Explain DNS name resolution in detail. (13)
12. (a) Explain TCP congestion control. (13)
Or
(b) Explain TCP connection management. (13)
13. (a) Explain the architecture of IPv6. (13)
Or
(b) Explain subnetting with an example. (13)
14. (a) Explain distance vector routing. (13)
Or
(b) Explain link state routing. (13)
15. (a) Explain CSMA/CD. (13)
Or
(b) Explain the IEEE 802.11 architecture. (13)
PART C — (1 × 15 = 15 marks)
16. (a) Design a campus network and justify the protocols used. (15)
Or
(b) Find the CRC for the data 1101011011 using the generator 10011. (15)
"""

CAT_TABLE = """RAJALAKSHMI ENGINEERING COLLEGE
CONTINUOUS ASSESSMENT TEST - I
Q.No   Question   CO   BL   Marks
PART A
1   Define protocol and list its elements.   CO1   K1   2
2   What is a socket?   CO1   K1   2
3   What is the three-way handshake?   CO2   K2   2
PART B
4   (a) Explain HTTP request and response message formats.   CO1   K2   11
(OR)
(b) Explain the OSI model with a neat diagram.   CO1   K2   11
"""


def _auth():
    r = client.post("/api/auth/register", json={"email": f"t{os.urandom(3).hex()}@rec.edu", "password": "secret123",
                                                "name": "Test", "department": "CSE"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def _pdf_bytes(text: str) -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    y = 40
    for line in text.splitlines():
        if y > 800:
            page, y = doc.new_page(), 40
        page.insert_text((40, y), line, fontsize=9)
        y += 13
    return doc.tobytes()


def _docx_bytes(text: str) -> bytes:
    import docx
    d = docx.Document()
    for line in text.splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------- extraction / classification
def test_au_paper_extraction_and_classification():
    qs = extraction.parse_questions(AU_PAPER, "SEMESTER", DEFAULT_EXAM_CONFIG)
    by = {(q.number, q.choice, q.sub): q for q in qs}
    assert sum(1 for q in qs if q.category == 2) == 10
    assert by[("11", "a", "i")].marks == 7 and by[("11", "a", "i")].category == 13
    assert by[("11", "a", "ii")].category == 13
    assert by[("13", "a", "")].text == "Explain the architecture of IPv6."
    assert by[("16", "b", "")].category == 15
    assert extraction.classify_qtype(by[("16", "b", "")].text) == "numerical"
    assert extraction.classify_qtype(by[("11", "a", "i")].text) == "diagram"
    assert extraction.classify_qtype("Compare OSI and TCP/IP models.") == "comparison"
    assert extraction.classify_qtype("Write a C program to implement CRC.") == "programming"


def test_cat_table_extraction():
    qs = extraction.parse_questions(CAT_TABLE, "CAT1", DEFAULT_EXAM_CONFIG)
    assert [q.number for q in qs] == ["1", "2", "3", "4", "4"]
    assert [q.category for q in qs] == [2, 2, 2, 11, 11]
    assert qs[0].co == "CO1" and qs[0].text == "Define protocol and list its elements."
    assert qs[4].choice == "b"


def test_syllabus_parsing():
    text = "UNIT I INTRODUCTION 9\nNetworks – OSI Model – Electronic Mail (SMTP, POP3) – DNS\nUNIT II TRANSPORT 9\nUDP – TCP\nTOTAL: 45 PERIODS"
    units = extraction.parse_syllabus(text)
    assert [u["number"] for u in units] == [1, 2]
    assert "Electronic Mail (SMTP, POP3)" in units[0]["topics"]
    assert units[1]["hours"] == 9


# ---------------------------------------------------------------- semantic matching
def test_semantic_duplicates_ipv6_example():
    texts = ["Explain the architecture of IPv6.", "Describe the IPv6 packet header format.",
             "Draw and explain the structure of an IPv6 packet.", "Explain CSMA/CD with a flowchart.",
             "Explain distance vector routing with an example."]
    labels = semantic.cluster(texts)
    assert labels[0] == labels[1] == labels[2]
    assert labels[3] != labels[0] and labels[4] != labels[0] and labels[3] != labels[4]
    assert semantic.exact_match("What is the role of DNS?", "What is the role of DNS ?")
    assert not semantic.exact_match("Explain the architecture of IPv6.", "Describe the IPv6 packet header format.")


# ---------------------------------------------------------------- scoring
def _toy_corpus():
    P = predictor.Paper
    papers = [P(1, "SEMESTER", 2021, 11, "Sem 2021"), P(2, "SEMESTER", 2022, 11, "Sem 2022"),
              P(3, "SEMESTER", 2023, 11, "Sem 2023"), P(4, "SEMESTER", 2024, 11, "Sem 2024")]
    qs, qid = [], 0

    def add(pid, text, cat, unit):
        nonlocal qid
        qid += 1
        qs.append({"id": qid, "text": text, "category": cat, "unit": unit, "topic": "", "qtype": "theory", "paper_id": pid})

    for pid in (1, 2, 3, 4):
        add(pid, "Explain the architecture of IPv6.", 13, 3)       # asked every time
    add(1, "Explain distance vector routing.", 13, 4)
    add(3, "Explain distance vector routing with an example.", 13, 4)
    add(2, "Explain HDLC frame format.", 13, 5)                        # asked once, long ago
    add(4, "What is CRC?", 2, 5)
    units = [{"number": 3, "title": "Network layer", "topics": ["IPv6"], "hours": 9},
             {"number": 4, "title": "Routing", "topics": ["Distance vector routing", "BGP"], "hours": 9},
             {"number": 5, "title": "Data link", "topics": ["HDLC", "CRC"], "hours": 9}]
    return predictor.Corpus(papers=papers, questions=qs, units=units)


def test_scoring_ranks_frequent_concepts_and_labels_evidence():
    cfg = dict(DEFAULT_EXAM_CONFIG)
    scored = predictor.score_candidates(_toy_corpus(), "SEMESTER", cfg, normalized_weights(DEFAULT_WEIGHTS))
    items = predictor.ranked_list(scored, cfg)
    top = items[0]
    assert "IPv6" in top["text"] and top["evidence"] == "exact_repeat" and top["frequency"]["papers"] == 4
    dvr = next(i for i in items if "distance vector" in i["text"].lower())
    assert dvr["evidence"] == "concept_repeat" and dvr["frequency"]["papers"] == 2
    hdlc = next(i for i in items if "HDLC" in i["text"])
    assert hdlc["score"] < top["score"]
    # untested syllabus topic -> generated practice question, clearly flagged
    bgp = next(i for i in items if i["topic"] == "BGP")
    assert bgp["evidence"] == "practice_new" and bgp["is_generated"] and not bgp["appearances"]
    # no item that is not generated may lack a real appearance
    assert all(i["appearances"] for i in items if not i["is_generated"])
    assert scored["confidence"]["level"] in ("low", "moderate")


def test_weights_change_ranking():
    cfg = dict(DEFAULT_EXAM_CONFIG)
    only_syl = {k: (1.0 if k == "syllabus" else 0.0) for k in DEFAULT_WEIGHTS}
    a = predictor.ranked_list(predictor.score_candidates(_toy_corpus(), "SEMESTER", cfg, normalized_weights(DEFAULT_WEIGHTS)), cfg)
    b = predictor.ranked_list(predictor.score_candidates(_toy_corpus(), "SEMESTER", cfg, normalized_weights(only_syl)), cfg)
    assert [i["id"] for i in a] != [i["id"] for i in b]


def test_backtest_has_no_leakage():
    corpus = _toy_corpus()
    w = normalized_weights(DEFAULT_WEIGHTS)
    res = evaluation.run(corpus, dict(DEFAULT_EXAM_CONFIG), lambda _et: w)
    assert res["folds"], "expected at least one fold"
    for f in res["folds"]:
        target = next(p for p in corpus.papers if p.id == f["paper_id"])
        assert f["train_papers"] == sum(1 for p in corpus.papers if p.t < target.t)
    # The 2023 paper's distance-vector question was seen in 2021 -> semantic match is possible,
    # but HDLC (only in 2022) can't be "predicted" for 2022 itself.
    f2022 = [f for f in res["folds"] if f["year"] == 2022]
    if f2022:
        rows = f2022[0]["rows"]
        hdlc = next(r for r in rows if "HDLC" in r["text"])
        assert hdlc["match"] in ("miss", "topic")


# ---------------------------------------------------------------- full API workflow
def test_full_workflow_upload_to_paper_pdf():
    H = _auth()
    sid = client.post("/api/subjects", headers=H, json={"name": "Computer Networks", "code": "CS23501",
                                                         "department": "CSE", "regulation": "2023", "semester": 5}).json()["id"]
    syl = client.post(f"/api/subjects/{sid}/documents/text", headers=H, json={
        "text": "UNIT I INTRODUCTION 9\nProtocol Layering – OSI Model – DNS – HTTP\nUNIT II TRANSPORT 9\nUDP – TCP – Congestion Control\n"
                "UNIT III NETWORK 9\nIPv6 – Subnetting\nUNIT IV ROUTING 9\nDistance Vector Routing – Link State Routing\n"
                "UNIT V DATA LINK 9\nCRC – CSMA/CD – IEEE 802.11", "kind": "syllabus", "title": "syllabus"}).json()
    assert syl["status"] == "done"

    # multi-file upload: PDF + DOCX in one request
    files = [("files", ("sem2023.pdf", _pdf_bytes(AU_PAPER), "application/pdf")),
             ("files", ("sem2024.docx", _docx_bytes(AU_PAPER.replace("Define protocol.", "Define a network protocol.")),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))]
    meta = '[{"kind":"question_paper","exam_type":"SEMESTER","academic_year":"2023-24","exam_year":2023,"exam_month":11},' \
           '{"kind":"question_paper","exam_type":"SEMESTER","academic_year":"2024-25","exam_year":2024,"exam_month":11}]'
    r = client.post(f"/api/subjects/{sid}/documents", headers=H, files=files, data={"meta": meta})
    assert r.status_code == 200, r.text
    docs = r.json()
    assert [d["question_count"] for d in docs] == [23, 23]
    assert docs[0]["extraction_method"].startswith("pymupdf")
    assert docs[1]["extraction_method"] == "python-docx"

    # unsupported type is rejected
    bad = client.post(f"/api/subjects/{sid}/documents", headers=H, files=[("files", ("x.exe", b"MZ", "application/octet-stream"))])
    assert bad.status_code == 400

    qs = client.get(f"/api/subjects/{sid}/questions", headers=H).json()
    ipv6 = next(q for q in qs if "IPv6" in q["text"] and q["category"] == 13)
    assert ipv6["unit"] == 3
    # edit a question
    e = client.patch(f"/api/questions/{ipv6['id']}", headers=H, json={"text": "Explain the architecture of IPv6 in detail."}).json()
    assert e["verified"] and e["text"].endswith("in detail.")
    dups = client.get(f"/api/subjects/{sid}/duplicates", headers=H).json()
    assert any(g["exact"] and g["papers"] == 2 for g in dups)

    preds = client.get(f"/api/subjects/{sid}/predictions?exam_type=SEMESTER", headers=H).json()
    assert preds["items"] and preds["confidence"]["level"] == "low"
    paper = client.post(f"/api/subjects/{sid}/papers", headers=H, json={"exam_type": "SEMESTER"}).json()
    secs = paper["paper"]["sections"]
    assert [s["name"] for s in secs] == ["A", "B", "C"]
    assert len(secs[0]["questions"]) == 10 and all(len(q["options"]) == 2 for q in secs[1]["questions"])
    assert paper["paper"]["total_marks"] == 100
    pdf = client.get(f"/api/papers/{paper['id']}/pdf", headers=H)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    alt = client.post(f"/api/subjects/{sid}/papers", headers=H, json={"exam_type": "SEMESTER", "seed": 42}).json()
    assert alt["id"] != paper["id"]
    assert len(client.get(f"/api/subjects/{sid}/papers", headers=H).json()) == 2

    csv = client.get(f"/api/subjects/{sid}/predictions/export?exam_type=SEMESTER&format=csv", headers=H)
    assert csv.status_code == 200 and "question,marks" in csv.text
    prep = client.post(f"/api/subjects/{sid}/prepare", headers=H, json={"text": ipv6["text"], "marks": 13, "topic": "IPv6", "unit": 3}).json()
    assert prep["mode"] == "rule_based" and prep["outline"]

    saved = client.post("/api/saved", headers=H, json={"subject_id": sid, "text": ipv6["text"], "marks": 13}).json()
    assert client.patch(f"/api/saved/{saved['id']}", headers=H, json={"status": "completed"}).json()["status"] == "completed"
    assert client.put(f"/api/subjects/{sid}/progress", headers=H, json={"unit": 3, "topic": "IPv6", "status": "studying"}).status_code == 200
    assert client.get(f"/api/subjects/{sid}/analysis", headers=H).json()["totals"]["papers"] == 2

    # delete a document removes its questions
    client.delete(f"/api/documents/{docs[1]['id']}", headers=H)
    assert len(client.get(f"/api/subjects/{sid}/questions", headers=H).json()) == 23


def test_other_users_cannot_access_subject():
    H1, H2 = _auth(), _auth()
    sid = client.post("/api/subjects", headers=H1, json={"name": "Private"}).json()["id"]
    assert client.get(f"/api/subjects/{sid}", headers=H2).status_code == 404
    assert client.get(f"/api/subjects/{sid}").status_code == 401


def test_demo_subject_is_seeded_and_labelled():
    H = _auth()
    subs = client.get("/api/subjects", headers=H).json()
    demo = next(s for s in subs if s["is_demo"])
    docs = client.get(f"/api/subjects/{demo['id']}/documents", headers=H).json()
    assert docs and all(d["is_sample"] for d in docs)
    assert sum(1 for d in docs if d["kind"] == "question_paper") == 8
    bt = client.get(f"/api/subjects/{demo['id']}/backtest", headers=H).json()
    assert bt["enough_data"] and bt["summary"]["statistical"]["semantic_topic_match_rate"] > 0
