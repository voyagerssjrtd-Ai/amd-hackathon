from __future__ import annotations

from services.scoring_service import calculate_risk


def run_risk_agent(state: dict) -> dict:
    result = calculate_risk(
        state.get("extracted_data", {}),
        state.get("identity_result", {}),
        state.get("compliance_result", {}),
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
