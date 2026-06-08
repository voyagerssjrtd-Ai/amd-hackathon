from __future__ import annotations

from services.scoring_service import identity_score


def run_identity_agent(state: dict) -> dict:
    result = identity_score(
        state.get("extracted_data", {}),
        state.get("pan_text", ""),
        state.get("aadhaar_text", ""),
    )
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Identity Agent",
            "status": "completed",
            "summary": f"Computed identity match score: {result['identity_match_score']}.",
        }
    )
    return {**state, "identity_result": result, "timeline": timeline}
