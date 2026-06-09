from __future__ import annotations

from mcp_tools.identity_tools import normalize_name


def run_entity_agent(state: dict) -> dict:
    extracted = state.get("extracted_data", {})
    pan_data = state.get("pan_data", {})
    aadhaar_data = state.get("aadhaar_data", {})
    result = {
        "canonical_name": normalize_name(extracted.get("name", "")),
        "name_sources": {
            "pan": pan_data.get("name", ""),
            "aadhaar": aadhaar_data.get("name", ""),
        },
        "dob": extracted.get("dob", ""),
        "primary_identifier": extracted.get("pan_number") or extracted.get("aadhaar_number", ""),
        "evidence": [
            "Resolved customer entity from separately extracted PAN and Aadhaar evidence.",
            "PAN remains the primary KYC identifier when available.",
        ],
    }
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Entity Resolution Agent",
            "status": "completed",
            "summary": f"Resolved canonical entity: {result['canonical_name'] or 'UNKNOWN'}.",
        }
    )
    return {**state, "entity_result": result, "timeline": timeline}
