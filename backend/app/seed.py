"""Sample subject so the platform can be explored without uploading anything.

IMPORTANT: every paper generated here is SYNTHETIC. The questions are typical
Computer Networks exam questions written for this demo; they are NOT real REC or
Anna University papers. Documents are flagged `is_sample=True` and the UI labels
them "Sample data" everywhere. The papers are rendered to real PDFs and pushed
through the normal extraction pipeline, so the demo exercises the real code path.
"""
from __future__ import annotations

import random
from pathlib import Path

from sqlalchemy.orm import Session

from . import models
from .config import DATA_DIR
from .services import pipeline
from .services.exam_config import DEFAULT_WEIGHTS

SAMPLE_DIR = DATA_DIR / "samples"

SYLLABUS = """COMPUTER NETWORKS (SAMPLE SYLLABUS FOR DEMO)
UNIT I INTRODUCTION AND APPLICATION LAYER 10
Data Communication – Networks – Network Types – Protocol Layering – TCP/IP Protocol Suite – OSI Model – Socket Programming – HTTP – FTP – Electronic Mail (SMTP, POP3, IMAP, MIME) – DNS – SNMP
UNIT II TRANSPORT LAYER 9
Transport Layer Services – UDP – TCP Segment Structure – TCP Connection Management – Flow Control – Sliding Window – Congestion Control – Congestion Avoidance (DECbit, RED) – SCTP – Quality of Service
UNIT III NETWORK LAYER 9
Packet Switching – Internet Protocol – IPv4 Header – IPv4 Addressing – Subnetting – CIDR – IPv6 – ARP – RARP – ICMP – DHCP – NAT
UNIT IV ROUTING 8
Unicast Routing – Distance Vector Routing – RIP – Link State Routing – Dijkstra Algorithm – OSPF – Path Vector Routing – BGP – Multicast Routing – DVMRP – PIM
UNIT V DATA LINK AND PHYSICAL LAYERS 9
Framing – Error Detection – CRC – Hamming Code – Flow Control – Stop and Wait – Go-Back-N – Selective Repeat – HDLC – PPP – Media Access Control – CSMA/CD – Ethernet – Virtual LAN – Wireless LAN IEEE 802.11 – Transmission Media
TOTAL: 45 PERIODS
"""

# (unit, [variants]) - variants are alternative wordings of the same concept.
SHORT = {
    1: [["What is a protocol? List its key elements.", "Define protocol and mention its elements."],
        ["Differentiate between LAN and WAN."],
        ["What is the role of DNS?", "State the purpose of the Domain Name System."],
        ["List the layers of the TCP/IP protocol suite."],
        ["What is a socket?", "Define socket address."],
        ["What is MIME?"],
        ["Compare persistent and non-persistent HTTP connections."],
        ["What are the functions of SNMP?"]],
    2: [["Differentiate between TCP and UDP."],
        ["What is the three-way handshake?", "Define three-way handshaking in TCP."],
        ["What is congestion?", "Define congestion in networks."],
        ["What is the use of the sliding window protocol?"],
        ["Mention the QoS parameters."],
        ["What is RED?"],
        ["List the services provided by the transport layer."],
        ["What is multihoming in SCTP?"]],
    3: [["What is subnetting?", "Define subnet mask with an example."],
        ["List the advantages of IPv6 over IPv4."],
        ["What is the purpose of ARP?", "State the function of Address Resolution Protocol."],
        ["What is ICMP?"],
        ["What is CIDR notation?"],
        ["What is NAT?"],
        ["What is DHCP?", "Define the role of DHCP server."],
        ["Find the class of the IP address 172.16.4.9."]],
    4: [["What is count-to-infinity problem?"],
        ["Differentiate distance vector and link state routing."],
        ["What is OSPF?"],
        ["What is BGP?", "State the purpose of Border Gateway Protocol."],
        ["What is multicast routing?"],
        ["What is split horizon?"],
        ["Define autonomous system."],
        ["What is PIM?"]],
    5: [["What is CRC?", "Define cyclic redundancy check."],
        ["What is framing?", "Define framing in the data link layer."],
        ["What is CSMA/CD?"],
        ["What is a VLAN?", "Define virtual LAN."],
        ["Differentiate Go-Back-N and Selective Repeat."],
        ["What is bit stuffing?"],
        ["What is the hidden terminal problem?"],
        ["List the guided transmission media."]],
}

LONG = {
    1: [["Explain the OSI reference model with a neat diagram.", "Describe the functions of each layer of the OSI model.",
         "Draw the OSI model and explain the role of each layer."],
        ["Explain the working of HTTP with request and response message formats.", "Describe HTTP request and response message formats."],
        ["Explain the electronic mail architecture with SMTP, POP3 and IMAP.", "Describe the working of SMTP, POP3 and IMAP in email."],
        ["Explain DNS in detail with name resolution process.", "Describe the domain name system and recursive name resolution."],
        ["Explain FTP and its connection types."],
        ["Write a client-server program using TCP sockets."]],
    2: [["Explain TCP congestion control mechanisms.", "Describe slow start, congestion avoidance and fast recovery in TCP."],
        ["Explain TCP connection establishment and termination with diagrams.", "Describe TCP connection management with state transition diagram."],
        ["Explain the TCP segment structure.", "Draw the TCP header format and explain each field."],
        ["Explain UDP datagram format and its applications."],
        ["Explain congestion avoidance using DECbit and RED."],
        ["Explain SCTP services and features."],
        ["Explain the techniques to improve Quality of Service."]],
    3: [["Explain the IPv4 header format with a neat diagram.", "Describe the IPv4 datagram format."],
        ["Explain the architecture of IPv6.", "Describe the IPv6 packet header format.", "Draw and explain the structure of an IPv6 packet."],
        ["Explain subnetting with an example.", "A network has the address 192.168.10.0/24. Divide it into 4 subnets and find the subnet addresses."],
        ["Explain ARP and RARP in detail."],
        ["Explain ICMP message types."],
        ["Explain DHCP operation with a neat diagram."]],
    4: [["Explain distance vector routing with an example.", "Describe distance vector routing and the count-to-infinity problem."],
        ["Explain link state routing with Dijkstra's algorithm.", "Describe link state routing and find the shortest path using Dijkstra's algorithm."],
        ["Explain OSPF in detail."],
        ["Explain BGP and path vector routing.", "Describe path vector routing with BGP."],
        ["Explain multicast routing protocols DVMRP and PIM."],
        ["Explain RIP with its message format."]],
    5: [["Explain CRC error detection with an example.", "Find the CRC for the data 1101011011 using the generator 10011."],
        ["Explain Go-Back-N and Selective Repeat ARQ protocols.", "Describe sliding window ARQ protocols with diagrams."],
        ["Explain CSMA/CD with a flowchart.", "Describe the CSMA/CD media access method."],
        ["Explain the IEEE 802.11 wireless LAN architecture.", "Describe the architecture of IEEE 802.11."],
        ["Explain HDLC frame format and its modes."],
        ["Explain Hamming code for error correction."]],
}

SAMPLE_KEYWORDS = {
    "TCP Connection Management": ["three-way handshake", "connection establishment", "connection termination"],
    "Distance Vector Routing": ["count-to-infinity", "split horizon"],
    "Quality of Service": ["QoS"],
    "DNS": ["domain name system", "name resolution"],
    "Congestion Control": ["slow start", "fast recovery"],
}

# Papers: (filename, exam_type, academic_year, exam_year, exam_month, seed)
PAPERS = [
    ("sample_sem_nov2022.pdf", "SEMESTER", "2022-23", 2022, 11, 11),
    ("sample_cat1_aug2023.pdf", "CAT1", "2023-24", 2023, 8, 21),
    ("sample_cat2_oct2023.pdf", "CAT2", "2023-24", 2023, 10, 22),
    ("sample_sem_nov2023.pdf", "SEMESTER", "2023-24", 2023, 11, 12),
    ("sample_cat1_aug2024.pdf", "CAT1", "2024-25", 2024, 8, 23),
    ("sample_cat2_oct2024.pdf", "CAT2", "2024-25", 2024, 10, 24),
    ("sample_sem_nov2024.pdf", "SEMESTER", "2024-25", 2024, 11, 13),
    ("sample_cat1_aug2025.pdf", "CAT1", "2025-26", 2025, 8, 25),
]
# Concepts the synthetic "faculty" favours, to create realistic repetition
FAVOURITES = {1: [0, 3], 2: [0, 1], 3: [1, 2], 4: [0, 1], 5: [0, 1]}


def _pick(pool: list[list[str]], unit: int, k: int, rng: random.Random, used: set) -> list[str]:
    idx = list(range(len(pool)))
    weights = [3.0 if i in FAVOURITES.get(unit, []) else 1.0 for i in idx]
    chosen = []
    while len(chosen) < k and idx:
        i = rng.choices(idx, weights=weights, k=1)[0]
        j = idx.index(i)
        idx.pop(j)
        weights.pop(j)
        if (id(pool), i) in used:
            continue
        used.add((id(pool), i))
        chosen.append(rng.choice(pool[i]))
    return chosen


def _semester_lines(seed: int) -> list[tuple]:
    rng = random.Random(seed)
    used: set = set()
    rows = [("h", "B.E. DEGREE EXAMINATION - SAMPLE PAPER (SYNTHETIC, FOR DEMO ONLY)"),
            ("h", "Computer Networks"), ("h", "Time: Three hours    Maximum: 100 marks"),
            ("h", "Answer ALL questions."), ("h", "PART A — (10 × 2 = 20 marks)")]
    n = 1
    for u in range(1, 6):
        for q in _pick(SHORT[u], u, 2, rng, used):
            rows.append(("q", f"{n}. {q}"))
            n += 1
    rows.append(("h", "PART B — (5 × 13 = 65 marks)"))
    for u in range(1, 6):
        a, b = _pick(LONG[u], u, 2, rng, used)
        rows.append(("q", f"{n}. (a) {a} (13)"))
        rows.append(("h", "Or"))
        rows.append(("q", f"(b) {b} (13)"))
        n += 1
    rows.append(("h", "PART C — (1 × 15 = 15 marks)"))
    ua, ub = rng.sample([1, 2, 3, 4, 5], 2)
    a = _pick(LONG[ua], ua, 1, rng, used) or ["Design a network for a campus and justify the choice of protocols."]
    b = _pick(LONG[ub], ub, 1, rng, used) or ["Analyse the performance of TCP over wireless links."]
    rows.append(("q", f"{n}. (a) {a[0]} Justify your answer with a case study. (15)"))
    rows.append(("h", "Or"))
    rows.append(("q", f"(b) {b[0]} Analyse with a suitable scenario. (15)"))
    return rows


def _cat_rows(seed: int, units: list[int]) -> list[tuple]:
    rng = random.Random(seed)
    used: set = set()
    rows = []
    n = 1
    for u in units:
        for q in _pick(SHORT[u], u, 3, rng, used):
            rows.append((str(n), q, f"CO{u}", "K2", "2"))
            n += 1
    for u in units:
        for _ in range(2):
            a, b = _pick(LONG[u], u, 2, rng, used)
            rows.append((str(n), f"(a) {a}", f"CO{u}", "K3", "11"))
            rows.append(("", "(OR)", "", "", ""))
            rows.append(("", f"(b) {b}", f"CO{u}", "K3", "11"))
            n += 1
    return rows


def _render_pdf(path: Path, title: str, rows: list, table: bool):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    ss = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm)
    story = [Paragraph(title, ss["Title"]),
             Paragraph("SAMPLE DATA - synthetic paper generated for the demo. Not a real REC / Anna University paper.", ss["Italic"]),
             Spacer(1, 8)]
    if table:
        story.append(Paragraph("PART A (6 x 2 = 12 marks)", ss["Heading4"]))
        data = [["Q.No", "Question", "CO", "BL", "Marks"]]
        part_b_started = False
        for r in rows:
            if r[4] == "11" and not part_b_started:
                t = Table(data, colWidths=[12 * mm, 120 * mm, 12 * mm, 10 * mm, 14 * mm])
                t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, "grey"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
                story += [t, Spacer(1, 6), Paragraph("PART B (4 x 11 = 44 marks)", ss["Heading4"])]
                data = []
                part_b_started = True
            data.append([r[0], Paragraph(r[1], ss["BodyText"]), r[2], r[3], r[4]])
        t = Table(data, colWidths=[12 * mm, 120 * mm, 12 * mm, 10 * mm, 14 * mm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, "grey"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    else:
        for kind, text in rows:
            style = ss["Heading4"] if kind == "h" else ss["BodyText"]
            story.append(Paragraph(text, style))
    doc.build(story)


def ensure_sample_files() -> dict[str, Path]:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    files = {}
    syl = SAMPLE_DIR / "sample_syllabus.txt"
    syl.write_text(SYLLABUS, encoding="utf-8")
    files["syllabus"] = syl
    for fname, et, ay, year, month, seed in PAPERS:
        p = SAMPLE_DIR / fname
        if not p.exists():
            if et == "SEMESTER":
                _render_pdf(p, f"Sample End Semester Paper - Nov/Dec {year}", _semester_lines(seed), table=False)
            else:
                units = [1, 2] if et == "CAT1" else [3, 4]
                _render_pdf(p, f"Sample {et[:3]} {et[3]} Paper - {ay}", _cat_rows(seed, units), table=True)
        files[fname] = p
    bank = SAMPLE_DIR / "sample_question_bank.txt"
    lines = ["SAMPLE FACULTY QUESTION BANK (synthetic)"]
    for u in range(1, 6):
        lines.append(f"UNIT {['I', 'II', 'III', 'IV', 'V'][u - 1]}")
        lines.append("PART A")
        for i, v in enumerate(SHORT[u][:3], 1):
            lines.append(f"{i}. {v[0]}")
        lines.append("PART B")
        for i, v in enumerate(LONG[u][:3], 4):
            lines.append(f"{i}. {v[-1]} (13)")
    bank.write_text("\n".join(lines), encoding="utf-8")
    files["bank"] = bank
    return files


def seed_demo_subject(db: Session, user: models.User) -> models.Subject:
    import shutil
    import uuid

    from .config import UPLOAD_DIR

    files = ensure_sample_files()
    s = models.Subject(owner_id=user.id, name="Computer Networks (Sample)", code="SAMPLE-CN",
                       department="CSE", regulation="2023", semester=5, is_demo=True,
                       exam_config={}, weights=dict(DEFAULT_WEIGHTS))
    db.add(s)
    db.commit()

    def add(path: Path, filename: str, kind: str, et="NA", ay="", year=None, month=None):
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}{path.suffix}"
        shutil.copy(path, dest)
        d = models.Document(subject_id=s.id, uploaded_by=user.id, filename=filename, stored_path=str(dest),
                            mime="application/pdf" if path.suffix == ".pdf" else "text/plain", kind=kind,
                            exam_type=et, academic_year=ay, exam_year=year, exam_month=month, is_sample=True)
        db.add(d)
        db.commit()
        pipeline.process_document(db, d)

    add(files["syllabus"], "Sample syllabus.txt", "syllabus")
    # Demonstrates configurable topic classification: student-defined keywords per syllabus topic
    db.refresh(s)
    s.syllabus_version = "R2023 sample v1"
    for u in s.units:
        meta = {t: {"keywords": kw} for t, kw in SAMPLE_KEYWORDS.items() if t in (u.topics or [])}
        if meta:
            u.topic_meta = meta
    db.commit()
    for fname, et, ay, year, month, _ in PAPERS:
        add(files[fname], fname, "question_paper", et, ay, year, month)
    add(files["bank"], "Sample question bank.txt", "question_bank")
    db.refresh(s)
    return s
