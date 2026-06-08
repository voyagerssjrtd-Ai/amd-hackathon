from __future__ import annotations


def run_decision_agent(state: dict) -> dict:
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
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Decision Agent",
            "status": "completed",
            "summary": f"Recommended {recommendation}.",
        }
    )
    return {**state, "decision_result": result, "timeline": timeline}
