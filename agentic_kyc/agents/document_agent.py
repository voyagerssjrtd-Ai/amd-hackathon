from __future__ import annotations

import re
from pathlib import Path

from services.llm_service import LLMService
from services.pdf_service import extract_text_from_pdf


def run_document_agent(state: dict) -> dict:
    document_paths = state.get("document_paths") or []
    if document_paths:
        classified = classify_uploaded_documents(document_paths)
        pan_path = classified.get("pan_path", "")
        aadhaar_path = classified.get("aadhaar_path", "")
        financial_path = classified.get("financial_path", state.get("financial_path", ""))
    else:
        classified = {}
        pan_path = state.get("pan_path", "")
        aadhaar_path = state.get("aadhaar_path", "")
        financial_path = state.get("financial_path", "")

    pan_text = extract_text_from_pdf(pan_path) if pan_path else ""
    aadhaar_text = extract_text_from_pdf(aadhaar_path) if aadhaar_path else ""
    llm = LLMService()
    pan_data = llm.extract_document_json("PAN", pan_text)
    aadhaar_data = llm.extract_document_json("AADHAAR", aadhaar_text)
    pan_authenticity = (
    llm.assess_document_authenticity(
        "PAN",
        pan_text,
    )
    if pan_text
    else {}
)

    aadhaar_authenticity = (
        llm.assess_document_authenticity(
            "AADHAAR",
            aadhaar_text,
        )
        if aadhaar_text
        else {}
    )
    pan_data = normalize_extraction_confidence(pan_data)
    aadhaar_data = normalize_extraction_confidence(aadhaar_data)
    extracted = merge_document_data(pan_data, aadhaar_data)
    document_evidence = build_document_evidence(classified, pan_data, aadhaar_data, pan_text, aadhaar_text)
    document_confidence = calculate_document_confidence(pan_data, aadhaar_data)
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Document Agent",
            "status": "completed",
            "summary": "Extracted PAN and Aadhaar as separate structured evidence objects.",
        }
    )
    return {
        **state,
        "pan_path": str(pan_path),
        "aadhaar_path": str(aadhaar_path),
        "financial_path": str(financial_path),
        "pan_text": pan_text,
        "aadhaar_text": aadhaar_text,
        "pan_data": pan_data,
        "aadhaar_data": aadhaar_data,
        "document_classification": classified,
        "document_texts": {
            "pan": preview_text(pan_text),
            "aadhaar": preview_text(aadhaar_text),
        },
        "document_evidence": document_evidence,
        "document_confidence": document_confidence,
        "extracted_data": extracted,
        "timeline": timeline,
        "document_integrity": {
        "PAN": pan_authenticity,
        "AADHAAR": aadhaar_authenticity,
},
    }


def merge_document_data(pan_data: dict, aadhaar_data: dict) -> dict:
    return {
        "name": pan_data.get("name") or aadhaar_data.get("name", ""),
        "dob": pan_data.get("dob") or aadhaar_data.get("dob", ""),
        "pan_number": pan_data.get("pan_number", ""),
        "aadhaar_number": aadhaar_data.get("aadhaar_number", ""),
        "address": aadhaar_data.get("address", ""),
        "pan_extraction_confidence": pan_data.get("extraction_confidence", 0),
        "aadhaar_extraction_confidence": aadhaar_data.get("extraction_confidence", 0),
    }


def classify_uploaded_documents(document_paths: list[str]) -> dict:
    classified: dict[str, str | list[dict]] = {"documents": []}
    for raw_path in document_paths:
        path = str(raw_path)
        text = extract_text_from_pdf(path)
        kind = infer_document_type(path, text)
        classified["documents"].append(
            {"path": path, "filename": Path(path).name, "type": kind, "text_preview": preview_text(text)}
        )
        if kind == "PAN" and not classified.get("pan_path"):
            classified["pan_path"] = path
        elif kind == "AADHAAR" and not classified.get("aadhaar_path"):
            classified["aadhaar_path"] = path
        elif kind == "FINANCIAL" and not classified.get("financial_path"):
            classified["financial_path"] = path

    # Filename fallback when OCR/VL text is partial.
    for item in classified["documents"]:
        filename = item["filename"].lower()
        if "pan" in filename and not classified.get("pan_path"):
            classified["pan_path"] = item["path"]
            item["type"] = "PAN"
        if ("aadhaar" in filename or "aadhar" in filename) and not classified.get("aadhaar_path"):
            classified["aadhaar_path"] = item["path"]
            item["type"] = "AADHAAR"
        if any(key in filename for key in ["bank", "salary", "payslip", "statement"]) and not classified.get("financial_path"):
            classified["financial_path"] = item["path"]
            item["type"] = "FINANCIAL"
    return classified


def infer_document_type(path: str, text: str) -> str:
    haystack = f"{Path(path).name}\n{text}".lower()
    if re.search(r"\b[a-z]{5}[0-9]{4}[a-z]\b", haystack) or "permanent account number" in haystack:
        return "PAN"
    if "aadhaar" in haystack or re.search(r"\b[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}\b", haystack):
        return "AADHAAR"
    if re.search(r"bank statement|salary|payslip|credited|debit|credit|balance|emi|loan", haystack):
        return "FINANCIAL"
    return "UNKNOWN"


def normalize_extraction_confidence(data: dict) -> dict:
    present = sum(1 for key in ["name", "dob", "pan_number", "aadhaar_number", "address"] if data.get(key))
    data["extraction_confidence"] = max(int(data.get("extraction_confidence") or 0), min(100, present * 25))
    return data


def build_document_evidence(
    classified: dict,
    pan_data: dict,
    aadhaar_data: dict,
    pan_text: str,
    aadhaar_text: str,
) -> list[dict]:
    rows: list[dict] = []
    for item in classified.get("documents", []):
        rows.append(
            {
                "document": item.get("filename", ""),
                "type": item.get("type", "UNKNOWN"),
                "evidence_type": "classification",
                "confidence": confidence_for_type(item.get("type", ""), pan_data, aadhaar_data),
                "evidence": item.get("text_preview", ""),
            }
        )
    rows.extend(
        [
            {
                "document": "PAN",
                "type": "PAN",
                "evidence_type": "fields",
                "confidence": pan_data.get("extraction_confidence", 0),
                "evidence": ", ".join(fields_found(pan_data)) or "No PAN fields extracted",
            },
            {
                "document": "PAN",
                "type": "PAN",
                "evidence_type": "ocr_preview",
                "confidence": pan_data.get("extraction_confidence", 0),
                "evidence": preview_text(pan_text),
            },
            {
                "document": "AADHAAR",
                "type": "AADHAAR",
                "evidence_type": "fields",
                "confidence": aadhaar_data.get("extraction_confidence", 0),
                "evidence": ", ".join(fields_found(aadhaar_data)) or "No Aadhaar fields extracted",
            },
            {
                "document": "AADHAAR",
                "type": "AADHAAR",
                "evidence_type": "ocr_preview",
                "confidence": aadhaar_data.get("extraction_confidence", 0),
                "evidence": preview_text(aadhaar_text),
            },
        ]
    )
    return rows


def calculate_document_confidence(pan_data: dict, aadhaar_data: dict) -> dict:
    pan_confidence = int(pan_data.get("extraction_confidence") or 0)
    aadhaar_confidence = int(aadhaar_data.get("extraction_confidence") or 0)
    values = [value for value in [pan_confidence, aadhaar_confidence] if value]
    overall = round(sum(values) / len(values)) if values else 0
    return {"PAN": pan_confidence, "AADHAAR": aadhaar_confidence, "OVERALL": overall}


def confidence_for_type(document_type: str, pan_data: dict, aadhaar_data: dict) -> int:
    if document_type == "PAN":
        return int(pan_data.get("extraction_confidence") or 0)
    if document_type == "AADHAAR":
        return int(aadhaar_data.get("extraction_confidence") or 0)
    return 0


def fields_found(data: dict) -> list[str]:
    return [field for field in ["name", "dob", "pan_number", "aadhaar_number", "address"] if data.get(field)]


def preview_text(text: str, limit: int = 1200) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]
