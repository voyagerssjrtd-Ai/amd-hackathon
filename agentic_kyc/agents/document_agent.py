from __future__ import annotations

from services.llm_service import LLMService
from services.pdf_service import extract_text_from_pdf


def run_document_agent(state: dict) -> dict:
    pan_text = extract_text_from_pdf(state["pan_path"])
    aadhaar_text = extract_text_from_pdf(state["aadhaar_path"])
    llm = LLMService()
    pan_data = llm.extract_document_json("PAN", pan_text)
    aadhaar_data = llm.extract_document_json("AADHAAR", aadhaar_text)
    extracted = merge_document_data(pan_data, aadhaar_data)
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
        "pan_text": pan_text,
        "aadhaar_text": aadhaar_text,
        "pan_data": pan_data,
        "aadhaar_data": aadhaar_data,
        "extracted_data": extracted,
        "timeline": timeline,
    }


def merge_document_data(pan_data: dict, aadhaar_data: dict) -> dict:
    # Ensure PAN data is properly extracted and not lost
    pan_number = (pan_data.get("pan_number") or "").strip()
    aadhaar_number = (aadhaar_data.get("aadhaar_number") or "").strip()
    name = (pan_data.get("name") or aadhaar_data.get("name", "")).strip()
    dob = (pan_data.get("dob") or aadhaar_data.get("dob", "")).strip()
    
    return {
        "name": name,
        "dob": dob,
        "pan_number": pan_number,
        "aadhaar_number": aadhaar_number,
        "address": (aadhaar_data.get("address") or "").strip(),
        "pan_extraction_confidence": pan_data.get("extraction_confidence", 0),
        "aadhaar_extraction_confidence": aadhaar_data.get("extraction_confidence", 0),
    }
