"""Question extraction from raw paper text.

Handles the layouts we see in REC CAT papers (often tables: Q.No | Question | CO | BL | Marks)
and Anna University end-semester papers (PART A/B/C, either-or (a)/(b), sub-parts (i)/(ii)
with marks in brackets). Nothing here assumes a single fixed pattern: section headers,
explicit marks and the subject's configured exam pattern are all used as evidence, and each
extracted item carries a confidence score so the student can review weak extractions.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .exam_config import nearest_category

ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}

RE_PART = re.compile(r"^\s*PART\s*[-–—:.]?\s*([A-C])\b(.*)$", re.I)
RE_PART_SPEC = re.compile(r"(\d{1,2})\s*[x×X*]\s*(\d{1,2})\s*=\s*(\d{1,3})")
RE_UNIT = re.compile(r"^\s*UNIT\s*[-–—:.]?\s*([IVX]{1,4}|\d)\b(.*)$", re.I)
RE_QNUM = re.compile(r"^\s*(?:Q\.?\s*(?:No\.?)?\s*)?(\d{1,2})\s*[.)]\s*(.*)$")
RE_QNUM_TABLE = re.compile(r"^\s*(\d{1,2})\s+(?=[A-Za-z(\[])(.*)$")
RE_CHOICE = re.compile(r"^\s*\(?\s*([abAB])\s*[).]\s*(.*)$")
RE_SUB = re.compile(r"^\s*\(\s*(i{1,3}|iv|v|vi{0,3}|ix|x)\s*\)\s*(.*)$", re.I)
RE_OR = re.compile(r"^\s*[\(\[]?\s*(or|OR|Or)\s*[\)\]]?\s*$")
RE_MARKS_BRACKET = re.compile(r"[\(\[]\s*(\d{1,2})\s*(?:marks?|m)?\s*[\)\]]\s*$", re.I)
RE_MARKS_WORD = re.compile(r"\b(\d{1,2})\s*marks?\s*$", re.I)
RE_TRAILING_TABLE = re.compile(
    r"\s+(?:(CO\s*-?\s*\d)\s*)?(?:(K[1-6]|BL\s*-?\s*[1-6]|L[1-6]|U|R|AP|AN|E|C)\s+)?(\d{1,2})\s*$"
)
RE_TABLE_MID = re.compile(
    r"\s{2,}(CO\s*-?\s*\d)\s+(?:(K[1-6]|BL\s*-?\s*[1-6]|L[1-6])\s+)?(\d{1,2})(?=\s{2,}|\s*$)", re.I)
RE_CO = re.compile(r"\bCO\s*-?\s*(\d)\b", re.I)
RE_BLOOM = re.compile(r"\b(K[1-6]|BL\s*-?\s*[1-6]|L[1-6])\b")

NOISE_PATTERNS = [
    r"^\s*(reg(ister)?\.?\s*no|roll\s*no|name\s*:|time\s*:|duration|max(imum)?\.?\s*marks|date\s*:|"
    r"answer\s+all|q\.?\s*no\.?\s+question|question\s+paper\s+code|rajalakshmi|anna\s+university|"
    r"department\s+of|b\.?\s*e\.?/?b\.?\s*tech|semester|regulation|continuous\s+assessment|"
    r"course\s+code|subject\s+code|academic\s+year|knowledge\s+level|bloom|page\s+\d|\*+|-{3,}|"
    r"[ivx]+\s*semester|cat\s*[-–]?\s*[12i]+\b|internal\s+assessment)",
    r"^\s*\d{1,3}\s*$",  # stray page numbers / table cells
    r"^\s*(co|bl|marks?|k[1-6])\s*$",
]
RE_NOISE = re.compile("|".join(NOISE_PATTERNS), re.I)


@dataclass
class ExtractedQuestion:
    number: str
    choice: str
    sub: str
    section: str
    text: str
    marks: int | None
    category: int | None
    co: str = ""
    bloom: str = ""
    unit_hint: int | None = None
    confidence: float = 0.9

    def to_dict(self):
        return asdict(self)


def _roman_to_int(s: str) -> int | None:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    return ROMAN.get(s)


def _strip_marks(text: str, allow_table: bool) -> tuple[str, int | None, str, str]:
    """Remove trailing mark/CO/BL annotations. Returns (text, marks, co, bloom)."""
    marks = None
    co = bloom = ""
    # table row whose question cell wrapped: "... text   CO1   K2   13   more text"
    m = RE_TABLE_MID.search(text) if allow_table else None
    if m:
        marks = int(m.group(3))
        co, bloom = m.group(1), m.group(2) or ""
        text = (text[: m.start()] + " " + text[m.end():]).strip()
        m = None
    m = None if marks is not None else RE_MARKS_BRACKET.search(text)
    if marks is not None:
        pass
    elif m:
        marks = int(m.group(1))
        text = text[: m.start()].rstrip()
    else:
        m = RE_MARKS_WORD.search(text)
        if m:
            marks = int(m.group(1))
            text = text[: m.start()].rstrip()
        elif allow_table:
            m = RE_TRAILING_TABLE.search(text)
            # only trust a bare trailing number if it is preceded by a CO/BL tag or a wide gap
            if m and (m.group(1) or m.group(2) or re.search(r"\s{2,}\d{1,2}\s*$", text)):
                val = int(m.group(3))
                if 1 <= val <= 20:
                    marks = val
                    co = m.group(1) or ""
                    bloom = m.group(2) or ""
                    text = text[: m.start()].rstrip()
    m = RE_CO.search(text)
    if m:
        co = co or f"CO{m.group(1)}"
        text = (text[: m.start()] + text[m.end():]).strip()
    m = RE_BLOOM.search(text)
    if m and text.rstrip().endswith(m.group(0)):
        bloom = bloom or m.group(1)
        text = text[: m.start()].rstrip()
    return text.strip(" \t:-–"), marks, co.replace(" ", "").replace("-", "").upper(), bloom.replace(" ", "")


def _section_defaults(exam_cfg: dict | None, exam_type: str) -> list[dict]:
    if not exam_cfg or exam_type not in exam_cfg:
        return []
    return exam_cfg[exam_type].get("sections", [])


def _category_from_number(num: int, sections: list[dict]) -> tuple[str, int | None]:
    """Map a question number onto the configured pattern, e.g. AU: 1-10 -> A(2), 11-15 -> B(13), 16 -> C(15)."""
    start = 1
    for s in sections:
        end = start + s["count"] - 1
        if start <= num <= end:
            return s["name"], s["marks_each"]
        start = end + 1
    return "", None


def parse_questions(text: str, exam_type: str = "NA", exam_cfg: dict | None = None,
                    ocr: bool = False) -> list[ExtractedQuestion]:
    lines = [re.sub(r"[ \t]{2,}", "   ", ln.replace("\t", "   ").replace("", "")).rstrip()
             for ln in text.splitlines()]
    sections = _section_defaults(exam_cfg, exam_type)
    section_marks: dict[str, int] = {}
    cur_section = ""
    cur_unit: int | None = None
    items: list[dict] = []
    cur: dict | None = None
    last_num = 0
    cur_choice = ""

    def flush():
        nonlocal cur
        if cur and cur["text"].strip():
            items.append(cur)
        cur = None

    def start_item(num: str, choice: str, sub: str, body: str):
        nonlocal cur
        flush()
        cur = {"number": num, "choice": choice, "sub": sub, "section": cur_section,
               "text": body, "unit_hint": cur_unit}

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        m = RE_PART.match(line)
        if m:
            flush()
            cur_section = m.group(1).upper()
            spec = RE_PART_SPEC.search(line)
            if spec:
                section_marks[cur_section] = int(spec.group(2))
            last_num = last_num if items else 0
            continue
        if RE_PART_SPEC.fullmatch(line.strip("() ")):
            spec = RE_PART_SPEC.search(line)
            if cur_section:
                section_marks[cur_section] = int(spec.group(2))
            continue
        m = RE_UNIT.match(line)
        if m and len(line) < 90:
            flush()
            cur_unit = _roman_to_int(m.group(1))
            continue
        if RE_OR.match(line):
            flush()
            continue
        if RE_NOISE.match(line) and not RE_QNUM.match(line):
            continue

        m = RE_QNUM.match(line)
        tm = None if m else RE_QNUM_TABLE.match(line)
        num_match = m or tm
        if num_match:
            n = int(num_match.group(1))
            body = num_match.group(2)
            plausible = (n == last_num + 1) or (n == 1) or (m is not None and 0 < n - last_num <= 3) \
                or (cur_unit is not None and m is not None)
            if plausible and n <= 40:
                last_num = n
                cur_choice = ""
                sub = ""
                cm = RE_CHOICE.match(body)
                if cm and len(cm.group(2)) > 0:
                    cur_choice, body = cm.group(1).lower(), cm.group(2)
                sm = RE_SUB.match(body)
                if sm:
                    sub, body = sm.group(1).lower(), sm.group(2)
                start_item(str(n), cur_choice, sub, body)
                continue

        cm = RE_CHOICE.match(line)
        if cm and last_num and cm.group(2):
            cur_choice = cm.group(1).lower()
            body, sub = cm.group(2), ""
            sm = RE_SUB.match(body)
            if sm:
                sub, body = sm.group(1).lower(), sm.group(2)
            start_item(str(last_num), cur_choice, sub, body)
            continue
        sm = RE_SUB.match(line)
        if sm and last_num:
            start_item(str(last_num), cur_choice, sm.group(1).lower(), sm.group(2))
            continue

        if cur is not None:
            cur["text"] += " " + line
    flush()

    # ---- post-process: marks, CO/BL, categories
    out: list[ExtractedQuestion] = []
    for it in items:
        text, marks, co, bloom = _strip_marks(it["text"].strip(), allow_table=True)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 6:
            continue
        it.update(text=text, marks=marks, co=co, bloom=bloom)
        out.append(it)

    # parent totals for sub-parts: "11 (a) (i) ... (7)  (ii) ... (6)" -> slot of 13
    totals: dict[tuple, int] = {}
    for it in out:
        key = (it["number"], it["choice"])
        if it["marks"]:
            totals[key] = totals.get(key, 0) + it["marks"]

    cats = (exam_cfg or {}).get("mark_categories", [2, 11, 13, 15])
    # a "PART B" header without "(5 x 13 = 65)" -> use the configured pattern's section of that name
    pattern = sections or ((exam_cfg or {}).get("SEMESTER", {}).get("sections", []))
    named_marks = {s["name"]: s["marks_each"] for s in pattern}
    results: list[ExtractedQuestion] = []
    for it in out:
        conf = 0.92
        num = int(it["number"]) if it["number"].isdigit() else 0
        section = it["section"]
        slot = None
        total = totals.get((it["number"], it["choice"]))
        if section and section in section_marks:
            slot = section_marks[section]
        elif section and section in named_marks:
            slot = named_marks[section]
            conf -= 0.05
        elif total and total in cats:
            slot = total
        elif it["marks"] and it["marks"] <= 3:
            slot = 2
        elif sections and it["unit_hint"] is None:
            sec_name, slot = _category_from_number(num, sections)
            section = section or sec_name
            conf -= 0.12
        if slot is None and it["marks"]:
            slot = nearest_category(it["marks"], {"mark_categories": cats})
            conf -= 0.1
        if slot is None:
            # last resort heuristic on the wording itself
            short = len(it["text"]) < 110 and re.match(r"^(define|what|list|state|mention|name|give|differentiate|why|how|write short)", it["text"], re.I)
            slot = 2 if short else max(cats)
            conf -= 0.25
        if slot not in cats:
            slot = nearest_category(slot, {"mark_categories": cats})
        if not section:
            section = "A" if slot == 2 else ("C" if slot == max(cats) and slot >= 15 else "B")
        marks = it["marks"] or (slot if not it["sub"] else None)
        if it["marks"] is None:
            conf -= 0.08
        if ocr:
            conf -= 0.15
        if len(it["text"]) < 15:
            conf -= 0.2
        results.append(ExtractedQuestion(
            number=it["number"], choice=it["choice"], sub=it["sub"], section=section,
            text=it["text"], marks=marks, category=slot, co=it["co"], bloom=it["bloom"],
            unit_hint=it["unit_hint"], confidence=round(max(0.05, min(conf, 0.99)), 2),
        ))
    return results


# ---------------------------------------------------------------- question type
QTYPE_RULES = [
    ("programming", r"\b(write a (c|c\+\+|java|python)?\s*program|program to|code (to|for)|implement(ation)? .*(in|using) (c|java|python)|pseudo ?code|function to)\b"),
    ("numerical", r"\b(calculate|compute|find the (value|number|total|average|efficiency|throughput)|determine the|solve|evaluate|(find|compute|determine)\b[^.]*\d{2,}|\d+\s*(kbps|mbps|bits?|bytes?|ms|hz|ohm|kg|m/s|%))\b"),
    ("derivation", r"\b(derive|derivation|prove that|show that|deduce)\b"),
    ("diagram", r"\b(draw|diagram|sketch|neat sketch|block diagram|flow ?chart|illustrate with)\b"),
    ("comparison", r"\b(differentiate|distinguish|compare|contrast|difference between|versus|vs\.?)\b"),
    ("definition", r"^(define|what is|what are|what do you mean|list|state|mention|name)\b"),
]


def classify_qtype(text: str) -> str:
    t = text.lower()
    for name, pat in QTYPE_RULES:
        if re.search(pat, t):
            return name
    return "theory"


# ---------------------------------------------------------------- syllabus parsing
STOP_SECTIONS = re.compile(r"^\s*(total\s*:?\s*\d+|text\s*books?|references?|course\s+outcomes?|outcomes?\s*:|"
                           r"list of experiments|practical|web\s*references?|co[-\s]?po)", re.I)


def _split_topics(body: str) -> list[str]:
    """Split on dashes / semicolons / commas, but never inside parentheses."""
    out, buf, depth = [], [], 0
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        sep = depth == 0 and (ch in ";,–—" or (ch == "-" and body[i - 1:i] == " " and body[i + 1:i + 2] == " ")
                              or (ch == "." and body[i + 1:i + 2] == " "))
        if sep:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    out.append("".join(buf))
    return out


def parse_syllabus(text: str) -> list[dict]:
    """Return [{number, title, topics[], hours}] from an Anna University style syllabus."""
    units: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if STOP_SECTIONS.match(line):
            if cur:
                units.append(cur)
                cur = None
            continue
        m = RE_UNIT.match(line)
        if m:
            if cur:
                units.append(cur)
            num = _roman_to_int(m.group(1)) or len(units) + 1
            rest = m.group(2).strip(" :-–—")
            hours = None
            hm = re.search(r"(\d{1,2})\s*(?:hrs?|hours|periods)?\s*$", rest, re.I)
            if hm:
                hours = int(hm.group(1))
                rest = rest[: hm.start()].strip()
            cur = {"number": num, "title": rest.title() if rest.isupper() else rest, "body": "", "hours": hours}
            continue
        if cur is not None:
            cur["body"] += " " + line
    if cur:
        units.append(cur)

    result = []
    for u in units:
        body = re.sub(r"\s+", " ", u["body"])
        parts = _split_topics(body)
        topics, seen = [], set()
        for p in parts:
            p = p.strip(" .:-–")
            if 3 <= len(p) <= 90 and not p.isdigit() and p.lower() not in seen:
                seen.add(p.lower())
                topics.append(p)
        if not u["title"] and topics:
            u["title"] = topics[0]
        result.append({"number": u["number"], "title": u["title"], "topics": topics, "hours": u["hours"]})
    return result
