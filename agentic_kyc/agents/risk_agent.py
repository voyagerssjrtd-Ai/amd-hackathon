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
        "financial_result": state.get("financial_result", {}),
        "document_evidence": state.get("document_evidence", []),
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
            state.get("financial_result", {}),
        )
    result = add_factor_breakdown(result, payload)
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
    reasons = result.get("reasons", [])
    score = int(result.get("risk_score", 100))
    financial = payload.get("financial_result", {})
    if financial.get("status") == "TAMPERED":
        score = max(score, 95)
        reasons.extend(
            financial.get("evidence", [])
        )
    extracted = payload.get("extracted_data", {})
    pan_data = payload.get("pan_data", {})
    findings = payload.get("compliance_result", {}).get("findings", [])
    document_evidence = payload.get("document_evidence", [])
    fraud_indicators = [
        "not a valid id",
        "sample only",
        "test data",
        "fake",
        "tampered",
        "demo document",
        "specimen",
        "training data",
        "illustrative",
    ]

    for evidence in document_evidence:
        text = str(evidence.get("evidence", "")).lower()

        for indicator in fraud_indicators:
            if indicator in text:
                score = max(score, 95)

                reasons.append(
                    f"Fraud indicator detected: '{indicator}'."
                )
                break

    if extracted.get("pan_number"):
        reasons = [
            item
            for item in reasons
            if not ("pan" in item.lower() and ("missing" in item.lower() or "not found" in item.lower()))
        ]
    else:
        score = max(score, 75)
        reasons.append("PAN number missing; approval is blocked pending reviewer validation")
    if not pan_data.get("name") and not extracted.get("pan_number"):
        score = max(score, 70)
        reasons.append("PAN document image/text was not reliably extracted")
    if any(item.get("source") == "watchlist" for item in findings):
        score = max(score, 65)
    if any(item.get("source") == "blacklist" for item in findings):
        score = max(score, 90)

    score = min(100, score)

    level = (
        "HIGH"
        if score >= 75
        else "MEDIUM"
        if score >= 40
        else "LOW"
    )
    return {"risk_score": score, "risk_level": level, "reasons": dedupe(reasons)}


def add_factor_breakdown(result: dict, payload: dict) -> dict:
    extracted = payload.get("extracted_data", {})
    identity = payload.get("identity_result", {})
    compliance = payload.get("compliance_result", {})
    financial = payload.get("financial_result", {})
    factors: list[dict] = []

    if extracted.get("pan_number"):
        factors.append({"factor": "Valid PAN extracted", "impact": -20, "evidence": extracted.get("pan_number")})
    else:
        factors.append({"factor": "PAN missing", "impact": 35, "evidence": "PAN number not available"})

    identity_score = int(identity.get("identity_match_score", 0))
    if identity_score >= 85:
        factors.append({"factor": "High identity confidence", "impact": -15, "evidence": identity_score})
    elif identity_score >= 60:
        factors.append({"factor": "Moderate identity confidence", "impact": 15, "evidence": identity_score})    
    elif identity_score < 85:
        factors.append({"factor": "Low identity confidence", "impact": 25, "evidence": identity_score})

    findings = compliance.get("findings", [])
    if findings:
        impact = 45 if any(item.get("source") == "blacklist" for item in findings) else 25
        factors.append({"factor": "Compliance screening match", "impact": impact, "evidence": findings})
    else:
        factors.append({"factor": "Compliance screening clear", "impact": -10, "evidence": "No watchlist or blacklist hits"})

    if financial.get("status") == "TAMPERED":

        factors.append(
            {
                "factor": "Tampered financial document",
                "impact": 50,
                "evidence": financial.get(
                    "evidence",
                    [],
                ),
            }
        )

    elif financial.get("status") == "ANALYZED":

        if financial.get("financial_risk") == "LOW":

            factors.append(
                {
                    "factor": "Stable financial profile",
                    "impact": -10,
                    "evidence": financial,
                }
            )

        elif financial.get("financial_risk") == "HIGH":

            factors.append(
                {
                    "factor": "High financial risk",
                    "impact": 20,
                    "evidence": financial,
                }
            )

        elif financial.get("financial_risk") == "MEDIUM":

            factors.append(
                {
                    "factor": "Moderate financial risk",
                    "impact": 10,
                    "evidence": financial,
                }
            )

    else:

        factors.append(
            {
                "factor": "Financial document not provided",
                "impact": 0,
                "evidence": "Optional for this MVP",
            }
        )
    factor_score = calculate_factor_score(
    factors,
    compliance,
)

    score = max(
        int(result.get("risk_score", 0)),
        factor_score,
    )
    result["risk_score"] = score
    result["risk_level"] = "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"
    result["factors"] = factors
    clean_reasons = remove_contradictory_reasons(result.get("reasons", []), bool(extracted.get("pan_number")))
    result["reasons"] = dedupe(clean_reasons + [f"{item['factor']} ({item['impact']:+})" for item in factors])
    return result


def calculate_factor_score(factors: list[dict], compliance: dict) -> int:
    score = 50 + sum(int(item.get("impact", 0)) for item in factors)

    findings = compliance.get("findings", [])

    if any(item.get("source") == "blacklist" for item in findings):
        score = max(score, 90)

    elif any(item.get("source") == "watchlist" for item in findings):
        score = max(score, 65)

    if any(item.get("factor") == "PAN missing" for item in factors):
        score = max(score, 75)

    if any(
        item.get("factor") == "Tampered financial document"
        for item in factors
    ):
        score = max(score, 90)

    return max(0, min(100, score))

def remove_contradictory_reasons(reasons: list[str], pan_present: bool) -> list[str]:
    if not pan_present:
        return reasons
    blocked_terms = ["pan number missing", "missing pan", "pan not found", "pan extraction is incomplete"]
    return [reason for reason in reasons if not any(term in reason.lower() for term in blocked_terms)]


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output
