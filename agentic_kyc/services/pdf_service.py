from __future__ import annotations

from pathlib import Path

import pdfplumber
from pypdf import PdfReader


def extract_text_from_pdf(path: str | Path) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        return pdf_path.read_text(encoding="utf-8", errors="ignore")

    text = extract_with_pdfplumber(pdf_path)
    if text.strip():
        return text
    return extract_with_pypdf(pdf_path)


def extract_with_pdfplumber(path: Path) -> str:
    chunks: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                chunks.append(page.extract_text() or "")
    except Exception:
        return ""
    return "\n".join(chunks).strip()


def extract_with_pypdf(path: Path) -> str:
    chunks: list[str] = []
    reader = PdfReader(str(path))
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()
