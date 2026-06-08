from __future__ import annotations

from services.llm_service import LLMService
from services.pdf_service import extract_text_from_pdf


def run_document_agent(state: dict) -> dict:
    pan_text = extract_text_from_pdf(state["pan_path"])
    aadhaar_text = extract_text_from_pdf(state["aadhaar_path"])
    extracted = LLMService().extract_json(pan_text, aadhaar_text)
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Document Agent",
            "status": "completed",
            "summary": "Extracted text and structured KYC fields from PAN and Aadhaar documents.",
        }
    )
    return {
        **state,
        "pan_text": pan_text,
        "aadhaar_text": aadhaar_text,
        "extracted_data": extracted,
        "timeline": timeline,
    }
