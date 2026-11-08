"""'Prepare this question': exam-oriented answers and outlines.

With an API key, Claude writes the answer, grounded in the subject's syllabus.
Without one, a rule-based outline (structure, keywords, length guide) is produced
and clearly labelled as such - it does not pretend to be a model answer.
"""
from __future__ import annotations

import re

from prediction_engine import semantic

from . import llm

LENGTH_GUIDE = {
    2: "About 40-60 words (3-4 lines). Definition + one key point or example.",
    11: "About 2-2.5 pages. 5-6 subheadings, one diagram if relevant.",
    13: "About 2.5-3 pages. 6-7 subheadings, a labelled diagram and an example.",
    15: "About 3-4 pages. Analytical answer: approach, diagram, worked example/case, evaluation.",
}

SYSTEM = (
    "You are an experienced Anna University / Rajalakshmi Engineering College faculty member helping a student "
    "prepare exam answers. Write accurate, exam-oriented answers in Markdown. Use the subject syllabus provided "
    "for scope and terminology. Never invent textbook names, page numbers, citations or claim a question is "
    "official. If something is uncertain, say so briefly. Use ASCII/Mermaid-free text diagrams (a simple labelled "
    "block diagram in a code block) when a diagram is expected."
)


def _keywords(question: str, topic: str, related: list[str]) -> list[str]:
    words = semantic.concept_text(" ".join([question, topic] + related[:3])).split()
    seen, out = {topic.lower()} if topic else set(), []
    for w in words:
        if w.lower() not in seen and len(w) > 2:
            seen.add(w.lower())
            out.append(w)
    phrases = [topic] if topic else []
    return phrases + out[:10]


def _outline(marks: int, qtype: str, core: str) -> list[dict]:
    if marks <= 2:
        return [{"heading": "Definition", "points": [f"One precise sentence defining {core}."]},
                {"heading": "Key point / example", "points": ["One feature, property or example that shows understanding."]}]
    sections = [
        {"heading": "Introduction", "points": [f"What {core} is and where it is used (2-3 lines)."]},
        {"heading": "Definition / basic concept", "points": ["Formal definition; key terms underlined."]},
    ]
    if qtype in ("diagram", "theory", "comparison"):
        sections.append({"heading": "Diagram", "points": ["Neat, labelled block/architecture diagram placed early in the answer."]})
    if qtype == "derivation":
        sections.append({"heading": "Derivation", "points": ["State assumptions", "Step-by-step derivation", "Final result boxed"]})
    if qtype == "numerical":
        sections.append({"heading": "Given / Formula / Solution", "points": ["List given data with units", "Write the formula", "Substitute step by step", "Final answer with units"]})
    if qtype == "programming":
        sections.append({"heading": "Algorithm & program", "points": ["Algorithm in steps", "Program with comments", "Sample input/output", "Time complexity if relevant"]})
    if qtype == "comparison":
        sections.append({"heading": "Comparison table", "points": ["6-8 rows: basis of comparison | item 1 | item 2"]})
    sections += [
        {"heading": "Working / explanation", "points": ["Explain each component or step under its own sub-heading."]},
        {"heading": "Advantages & limitations", "points": ["3-4 advantages", "2-3 limitations"]},
        {"heading": "Applications", "points": ["2-3 real-world applications."]},
    ]
    if marks >= 15:
        sections.append({"heading": "Analysis / case study", "points": ["Apply the concept to a scenario; justify design choices."]})
    sections.append({"heading": "Conclusion", "points": ["2-line summary of the key idea."]})
    return sections


def prepare(question: str, marks: int, qtype: str, topic: str, unit: int | None,
            subject_name: str, syllabus_units: list[dict], related: list[str]) -> dict:
    core = semantic.RE_INSTR.sub("", question).strip(" .?:") or question
    base = {
        "question": question, "marks": marks, "unit": unit, "topic": topic,
        "keywords": _keywords(question, topic, related),
        "outline": _outline(marks, qtype, core),
        "length_guide": LENGTH_GUIDE.get(marks, LENGTH_GUIDE[13] if marks > 2 else LENGTH_GUIDE[2]),
        "diagram_expected": qtype in ("diagram",) or bool(re.search(r"architecture|structure|model|layer|format|block", question, re.I)),
        "related_questions": related[:5],
    }
    unit_ctx = ""
    for u in syllabus_units:
        if unit is None or u["number"] == unit:
            unit_ctx += f"Unit {u['number']}: {u['title']} - {', '.join(u.get('topics') or [])}\n"
    prompt = (
        f"Subject: {subject_name}\nSyllabus context:\n{unit_ctx or '(no syllabus uploaded)'}\n"
        f"Question ({marks} marks): {question}\n"
        f"Related past wordings: {'; '.join(related[:4]) or 'none'}\n\n"
        f"Write an exam-ready answer worth {marks} marks. Target length: {base['length_guide']}\n"
        "Structure: start with a 1-line summary, then subheadings. For long answers include: important keywords "
        "in bold, a labelled diagram in a code block where applicable, relevant formulas, and a short conclusion. "
        "End with a section '### Keywords to underline' listing 6-10 terms."
    )
    answer = llm.complete(SYSTEM, prompt)
    if answer:
        return {**base, "mode": "ai", "answer_markdown": answer,
                "disclaimer": "AI-written answer. Cross-check with your class notes and prescribed textbook."}
    return {**base, "mode": "rule_based", "answer_markdown": None,
            "disclaimer": ("AI answers are not enabled on this server (no ANTHROPIC_API_KEY). Showing a rule-based "
                           "answer structure, keywords and length guide - fill it in from your notes.")}
