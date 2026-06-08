from __future__ import annotations


from services.llm_service import LLMService


def run_decision_agent(state: dict) -> dict:
    payload = {
        "extracted_data": state.get("extracted_data", {}),
        "pan_data": state.get("pan_data", {}),
        "aadhaar_data": state.get("aadhaar_data", {}),
        "identity_result": state.get("identity_result", {}),
        "compliance_result": state.get("compliance_result", {}),
        "risk_result": state.get("risk_result", {}),
    }
    try:
        result = enforce_decision_gates(LLMService().make_decision(payload), payload)
    except Exception:
        result = fallback_decision(state)
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Decision Agent",
            "status": "completed",
            "summary": f"Recommended {result['recommendation']}.",
        }
    )
    return {**state, "decision_result": result, "timeline": timeline}


def fallback_decision(state: dict) -> dict:
    risk = state.get("risk_result", {})
    compliance = state.get("compliance_result", {})
    identity = state.get("identity_result", {})
    score = int(risk.get("risk_score", 100))
    findings = compliance.get("findings", [])
    identity_score = int(identity.get("identity_match_score", 0))

    if any(item.get("source") == "blacklist" for item in findings) or score >= 80:
        recommendation = "ESCALATE"
        explanation = "High risk or blacklist evidence requires compliance escalation."
    elif findings or score >= 40 or identity_score < 85:
        recommendation = "REVIEW"
        explanation = "One or more identity, compliance, or risk indicators require human review."
    else:
        recommendation = "APPROVE"
        explanation = "Identity evidence is consistent and simulated compliance screening is clear."

    result = {
        "recommendation": recommendation,
        "explanation": explanation,
        "evidence": {
            "risk_score": score,
            "risk_level": risk.get("risk_level"),
            "identity_match_score": identity_score,
            "compliance_status": compliance.get("status"),
            "finding_count": len(findings),
        },
    }
    return enforce_decision_gates(
        result,
        {
            "extracted_data": state.get("extracted_data", {}),
            "pan_data": state.get("pan_data", {}),
            "compliance_result": compliance,
            "risk_result": risk,
            "identity_result": identity,
        },
    )


def enforce_decision_gates(result: dict, payload: dict) -> dict:
    extracted = payload.get("extracted_data", {})
    pan_data = payload.get("pan_data", {})
    findings = payload.get("compliance_result", {}).get("findings", [])
    risk = payload.get("risk_result", {})

    if any(item.get("source") == "blacklist" for item in findings):
        result["recommendation"] = "ESCALATE"
        result["explanation"] = "Blacklist evidence requires compliance escalation."
    elif not extracted.get("pan_number") or not pan_data.get("name"):
        result["recommendation"] = "REVIEW"
        result["explanation"] = "PAN extraction is incomplete; a human reviewer must validate the PAN document."
    elif int(risk.get("risk_score", 100)) >= 80:
        result["recommendation"] = "ESCALATE"
    elif int(risk.get("risk_score", 100)) >= 40:
        result["recommendation"] = "REVIEW"

    evidence = result.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {}
    evidence.update(
        {
            "pan_number_present": bool(extracted.get("pan_number")),
            "pan_name_present": bool(pan_data.get("name")),
            "risk_score": risk.get("risk_score"),
            "risk_level": risk.get("risk_level"),
        }
    )
    result["evidence"] = evidence
    return result
