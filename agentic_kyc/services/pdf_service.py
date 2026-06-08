from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import fitz
import pdfplumber
from PIL import Image
from pypdf import PdfReader

from services.llm_service import LLMService


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def extract_text_from_pdf(path: str | Path) -> str:
    return extract_text_from_document(path)


def extract_text_from_document(path: str | Path) -> str:
    document_path = Path(path)
    if not document_path.exists():
        raise FileNotFoundError(f"File not found: {document_path}")
    suffix = document_path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return extract_text_from_image(document_path)
    if suffix != ".pdf":
        return document_path.read_text(encoding="utf-8", errors="ignore")

    text = extract_with_pdfplumber(document_path)
    if text.strip():
        return text
    text = extract_with_pypdf(document_path)
    if text.strip():
        return text
    return extract_scanned_pdf_text(document_path)


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


def extract_scanned_pdf_text(path: Path) -> str:
    chunks: list[str] = []
    with fitz.open(path) as document:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(BytesIO(pixmap.tobytes("png")))
            chunks.append(extract_text_from_pil_image(image))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def extract_text_from_image(path: Path) -> str:
    image = Image.open(path)
    return extract_text_from_pil_image(image)


def extract_text_from_pil_image(image: Image.Image) -> str:
    image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
    text = LLMService().extract_text_from_image(image_b64, "image/png")
    if text.strip():
        return text.strip()
    return extract_with_optional_ocr(image)


def extract_with_optional_ocr(image: Image.Image) -> str:
    try:
        import easyocr
    except Exception:
        return ""

    reader = easyocr.Reader(["en"], gpu=False)
    rows = reader.readtext(image, detail=0, paragraph=True)
    return "\n".join(str(row) for row in rows).strip()
