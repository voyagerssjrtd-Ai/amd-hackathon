from __future__ import annotations

from services.llm_service import LLMService
from services.scoring_service import calculate_risk


def run_risk_agent(state: dict) -> dict:
    payload = {
        "extracted_data": state.get("extracted_data", {}),
        "pan_data": state.get("pan_data", {}),
        "aadhaar_data": state.get("aadhaar_data", {}),
        "identity_result": state.get("identity_result", {}),
        "compliance_result": state.get("compliance_result", {}),
    }
    try:
        result = enforce_risk_gates(LLMService().score_risk(payload), payload)
    except Exception:
        result = calculate_risk(
            state.get("extracted_data", {}),
            state.get("identity_result", {}),
            state.get("compliance_result", {}),
            state.get("pan_data", {}),
            state.get("aadhaar_data", {}),
        )
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Risk Agent",
            "status": "completed",
            "summary": f"Calculated {result['risk_level']} risk score: {result['risk_score']}.",
        }
    )
    return {**state, "risk_result": result, "timeline": timeline}


def enforce_risk_gates(result: dict, payload: dict) -> dict:
    extracted = payload.get("extracted_data", {})
    pan_data = payload.get("pan_data", {})
    findings = payload.get("compliance_result", {}).get("findings", [])
    reasons = result.get("reasons", [])
    score = int(result.get("risk_score", 100))

    # Check if PAN was successfully extracted to merged extracted_data
    has_pan = bool(extracted.get("pan_number"))
    has_pan_name = bool(pan_data.get("name"))
    has_pan_dob = bool(pan_data.get("dob"))
    
    if not has_pan:
        score = max(score, 55)
        reasons.append("PAN number missing; approval is blocked pending reviewer validation")
    
    # Only flag extraction failure if BOTH: no PAN extracted AND no name or DOB in PAN document
    if not has_pan and (not has_pan_name or not has_pan_dob):
        score = max(score, 70)
        reasons.append("PAN document image/text was not reliably extracted")
    
    if any(item.get("source") == "watchlist" for item in findings):
        score = max(score, 65)
    if any(item.get("source") == "blacklist" for item in findings):
        score = max(score, 90)

    level = "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"
    return {"risk_score": score, "risk_level": level, "reasons": dedupe(reasons)}


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output
