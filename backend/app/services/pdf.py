"""ReportLab rendering for predicted papers and prediction lists."""
from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

NAVY = colors.HexColor("#1f2440")
MUTED = colors.HexColor("#6b6f86")
LAV = colors.HexColor("#ece9fb")

_ss = getSampleStyleSheet()
S = {
    "title": ParagraphStyle("t", parent=_ss["Title"], fontName="Helvetica-Bold", fontSize=14, textColor=NAVY, spaceAfter=2),
    "sub": ParagraphStyle("s", parent=_ss["Normal"], fontSize=9.5, alignment=TA_CENTER, textColor=NAVY),
    "sec": ParagraphStyle("sec", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=11, alignment=TA_CENTER,
                          textColor=NAVY, spaceBefore=10, spaceAfter=2),
    "inst": ParagraphStyle("i", parent=_ss["Normal"], fontSize=8.5, alignment=TA_CENTER, textColor=MUTED, spaceAfter=6),
    "q": ParagraphStyle("q", parent=_ss["Normal"], fontSize=10, leading=13.5, textColor=colors.black),
    "meta": ParagraphStyle("m", parent=_ss["Normal"], fontSize=7.5, leading=9.5, textColor=MUTED),
    "small": ParagraphStyle("sm", parent=_ss["Normal"], fontSize=8, textColor=MUTED, alignment=TA_CENTER),
    "or": ParagraphStyle("or", parent=_ss["Normal"], fontName="Helvetica-Bold", fontSize=9.5, alignment=TA_CENTER),
}
PR_COLOR = {"very_high": "#5b4bd6", "high": "#3f6fd8", "moderate": "#7a8199", "lower": "#a3a7b8"}
PR_SHORT = {"very_high": "VERY HIGH", "high": "HIGH", "moderate": "MODERATE", "lower": "LOWER"}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(15 * mm, 10 * mm, "PREDICTED PAPER - generated from past-paper analysis. Not an official "
                                         "examination paper. Predictions are not guaranteed.")
    canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _meta_line(opt: dict) -> str:
    bits = [f"<font color='{PR_COLOR[opt['priority']]}'><b>{PR_SHORT[opt['priority']]}</b></font>",
            f"score {opt['score']:.0f}"]
    if opt.get("unit"):
        bits.append(f"Unit {opt['unit']}")
    if opt.get("topic"):
        bits.append(_esc(opt["topic"])[:60])
    fr = opt["frequency"]
    if fr["papers"]:
        bits.append(f"asked in {fr['papers']}/{fr['total_papers']} papers" + (f" ({', '.join(map(str, opt['years']))})" if opt["years"] else ""))
    bits.append(_esc(opt["evidence_label"].split(" - ")[0]))
    return " · ".join(bits)


def render_paper(paper: dict, subject: dict, include_notes: bool = True) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=18 * mm, title=f"Predicted {paper['label']} - {subject['name']}")
    story = [
        Paragraph("PREDICTED QUESTION PAPER", S["small"]),
        Paragraph(_esc(f"{subject.get('code') or ''} {subject['name']}".strip()), S["title"]),
        Paragraph(_esc(f"{paper['label']} · Regulation {subject.get('regulation', '')} · Semester {subject.get('semester', '')}"
                       f" · {subject.get('department', '')}"), S["sub"]),
        Spacer(1, 4),
    ]
    hdr = Table([[f"Time: {paper.get('duration', '')}", f"Units: {', '.join(map(str, paper['units']))}",
                  f"Maximum: {paper['total_marks']} marks"]], colWidths=[60 * mm, 58 * mm, 60 * mm])
    hdr.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (-1, -1), NAVY),
                             ("ALIGN", (1, 0), (1, 0), "CENTER"), ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                             ("LINEBELOW", (0, 0), (-1, 0), 0.6, NAVY), ("LINEABOVE", (0, 0), (-1, 0), 0.6, NAVY)]))
    story += [hdr, Spacer(1, 2)]
    conf = paper.get("confidence") or {}
    if conf.get("level") == "low":
        story.append(Paragraph(f"<b>Low confidence:</b> {_esc(conf.get('message', ''))}", S["inst"]))

    for sec in paper["sections"]:
        story.append(Paragraph(f"{sec['title']} — ({sec['count']} × {sec['marks_each']} = {sec['total']} marks)", S["sec"]))
        if sec.get("instruction"):
            story.append(Paragraph(_esc(sec["instruction"]), S["inst"]))
        for q in sec["questions"]:
            rows = []
            for k, opt in enumerate(q["options"]):
                label = f"{q['number']}." if k == 0 else ""
                letter = f"({'ab'[k]})" if len(q["options"]) > 1 else ""
                body = [Paragraph(_esc(opt["text"]), S["q"])]
                if include_notes:
                    body.append(Paragraph(_meta_line(opt), S["meta"]))
                rows.append([label, letter, body, f"({opt['marks']})"])
                if k == 0 and len(q["options"]) > 1:
                    rows.append(["", "", Paragraph("OR", S["or"]), ""])
            t = Table(rows, colWidths=[9 * mm, 8 * mm, 148 * mm, 13 * mm])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 10),
                                   ("ALIGN", (3, 0), (3, -1), "RIGHT"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
            story.append(KeepTogether(t))
    if include_notes:
        story += [Spacer(1, 10), Paragraph(
            "How to read this: each question shows its priority, prediction score (a ranking heuristic, not a "
            "probability), unit/topic, how often the concept appeared in your uploaded papers, and whether it is a "
            "real past question, a repeated concept, or a generated practice question.", S["meta"])]
    story.append(Paragraph(f"Generated {date.today().isoformat()}", S["meta"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def render_list(items: list[dict], subject: dict, title: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=18 * mm)
    story = [Paragraph(_esc(title), S["title"]), Paragraph(_esc(subject["name"]), S["sub"]), Spacer(1, 8)]
    rows = [["#", "Question", "Marks", "Unit", "Priority", "Score"]]
    for i, it in enumerate(items, 1):
        rows.append([str(i), [Paragraph(_esc(it["text"]), S["q"]), Paragraph(_esc(it["evidence_label"]), S["meta"])],
                     str(it["marks"]), str(it.get("unit") or "-"), PR_SHORT[it["priority"]], f"{it['score']:.0f}"])
    t = Table(rows, colWidths=[8 * mm, 118 * mm, 13 * mm, 11 * mm, 20 * mm, 12 * mm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LAV), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                           ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddde8"))]))
    story.append(t)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
