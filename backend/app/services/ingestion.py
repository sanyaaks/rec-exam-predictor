"""Document ingestion: turn PDFs, DOCX files and images into plain text.

Order of attempts for PDFs: PyMuPDF text layer -> pdfplumber -> OCR (for scanned
pages with no text layer). OCR uses Tesseract (pytesseract) or RapidOCR when one
is installed; otherwise the document is flagged so the student can type or paste
the questions in manually.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

SUPPORTED = {".pdf", ".docx", ".png", ".jpg", ".jpeg", ".txt"}


@dataclass
class ExtractResult:
    text: str
    method: str
    pages: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- OCR backends
def _ocr_backend():
    try:
        import pytesseract  # noqa: F401
        import shutil
        if shutil.which("tesseract"):
            return "tesseract"
    except ImportError:
        pass
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return "rapidocr"
    except ImportError:
        pass
    return None


def ocr_available() -> str | None:
    return _ocr_backend()


def _ocr_image_bytes(data: bytes) -> str:
    backend = _ocr_backend()
    if backend is None:
        raise RuntimeError("no OCR engine installed")
    from PIL import Image

    img = Image.open(io.BytesIO(data)).convert("RGB")
    if backend == "tesseract":
        import pytesseract
        return pytesseract.image_to_string(img, config="--psm 6")
    from rapidocr_onnxruntime import RapidOCR
    import numpy as np

    engine = RapidOCR()
    result, _ = engine(np.array(img))
    if not result:
        return ""
    # group boxes into lines by vertical position
    rows: list[tuple[float, float, str]] = [((b[0][1] + b[2][1]) / 2, b[0][0], t) for b, t, _ in result]
    rows.sort()
    lines, current, last_y = [], [], None
    for y, x, t in rows:
        if last_y is not None and abs(y - last_y) > 12:
            lines.append(" ".join(s for _, s in sorted(current)))
            current = []
        current.append((x, t))
        last_y = y
    if current:
        lines.append(" ".join(s for _, s in sorted(current)))
    return "\n".join(lines)


# ---------------------------------------------------------------- extractors
def _page_lines(page) -> str:
    """Rebuild visual lines from word boxes so table rows (Q.No | Question | CO | Marks)
    come out as one line. Wide horizontal gaps become double spaces (column breaks)."""
    words = page.get_text("words")
    if not words:
        return ""
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    for w in words:
        yc = (w[1] + w[3]) / 2
        h = max(w[3] - w[1], 1)
        if lines and abs(lines[-1][0] - yc) <= h * 0.45:
            lines[-1][1].append(w)
        else:
            lines.append([yc, [w]])
    out = []
    for _, ws in lines:
        ws.sort(key=lambda w: w[0])
        parts, prev = [], None
        for w in ws:
            if prev is not None:
                gap = w[0] - prev[2]
                parts.append("   " if gap > 14 else " ")
            parts.append(w[4])
            prev = w
        out.append("".join(parts))
    return "\n".join(out)


def _extract_pdf(path: Path) -> ExtractResult:
    import fitz  # PyMuPDF

    warnings: list[str] = []
    doc = fitz.open(path)
    pages = doc.page_count
    texts: list[str] = []
    scanned_pages: list[int] = []
    for i, page in enumerate(doc):
        t = _page_lines(page)
        if len(t.strip()) < 25:
            scanned_pages.append(i)
        texts.append(t)
    method = "pymupdf"

    if sum(len(t.strip()) for t in texts) < 40:
        # Try pdfplumber in case PyMuPDF missed an odd encoding
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                alt = [(p.extract_text() or "") for p in pdf.pages]
            if sum(len(t.strip()) for t in alt) > sum(len(t.strip()) for t in texts):
                texts, method = alt, "pdfplumber"
                scanned_pages = [i for i, t in enumerate(texts) if len(t.strip()) < 25]
        except Exception as e:  # pragma: no cover
            log.warning("pdfplumber failed: %s", e)

    if scanned_pages:
        if ocr_available():
            for i in scanned_pages:
                pix = doc[i].get_pixmap(dpi=250)
                try:
                    texts[i] = _ocr_image_bytes(pix.tobytes("png"))
                except Exception as e:
                    warnings.append(f"OCR failed on page {i + 1}: {e}")
            method += f"+ocr({_ocr_backend()})"
        else:
            warnings.append(
                f"{len(scanned_pages)} page(s) look scanned but no OCR engine is installed. "
                "Install Tesseract (and `pip install pytesseract`) or `pip install rapidocr-onnxruntime`, "
                "or add the questions manually."
            )
    doc.close()
    return ExtractResult("\n".join(texts), method, pages, warnings)


def _extract_docx(path: Path) -> ExtractResult:
    import docx

    d = docx.Document(str(path))
    lines = [p.text for p in d.paragraphs]
    # Question papers are often laid out as tables (Q.No | Question | CO | Marks)
    for table in d.tables:
        for row in table.rows:
            cells = []
            for c in row.cells:
                t = c.text.strip()
                if t and (not cells or cells[-1] != t):  # merged cells repeat text
                    cells.append(t)
            lines.append("  ".join(cells))
    return ExtractResult("\n".join(lines), "python-docx", 1)


def _extract_image(path: Path) -> ExtractResult:
    if not ocr_available():
        return ExtractResult("", "none", 1, [
            "Image uploads need an OCR engine. Install Tesseract (+ `pip install pytesseract`) "
            "or `pip install rapidocr-onnxruntime`, or add the questions manually."
        ])
    return ExtractResult(_ocr_image_bytes(path.read_bytes()), f"ocr({_ocr_backend()})", 1)


def extract_text(path: str | Path) -> ExtractResult:
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext in {".png", ".jpg", ".jpeg"}:
        return _extract_image(path)
    if ext == ".txt":
        return ExtractResult(path.read_text(encoding="utf-8", errors="ignore"), "plain-text", 1)
    raise ValueError(f"Unsupported file type: {ext}")
