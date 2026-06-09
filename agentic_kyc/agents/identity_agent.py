from __future__ import annotations

from services.llm_service import LLMService
from services.scoring_service import identity_score
from mcp_tools.identity_tools import compare_identity_evidence


def run_identity_agent(state: dict) -> dict:
    tool_result = compare_identity_evidence(state.get("pan_data", {}), state.get("aadhaar_data", {}))
    try:
        result = LLMService().verify_identity(state.get("pan_data", {}), state.get("aadhaar_data", {}))
        result = enforce_identity_truth(result, tool_result)
    except Exception:
        result = identity_score(
            state.get("extracted_data", {}),
            state.get("pan_text", ""),
            state.get("aadhaar_text", ""),
            state.get("pan_data", {}),
            state.get("aadhaar_data", {}),
        )
        result = enforce_identity_truth(result, tool_result)
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Identity Agent",
            "status": "completed",
            "summary": f"Computed identity match score: {result['identity_match_score']}.",
        }
    )
    return {**state, "identity_result": result, "timeline": timeline}


def enforce_identity_truth(result: dict, tool_result: dict) -> dict:
    """Prevent LLM hallucinations from contradicting deterministic document evidence."""
    issues = list(result.get("issues", []))
    evidence = result.get("evidence", {})
    pan_valid = tool_result["evidence"]["pan_validation"]["valid"]
    dob_match = tool_result["evidence"]["dob_match"]
    name_similarity = tool_result["evidence"]["name_similarity"]

    if pan_valid:
        issues = [item for item in issues if "pan number" not in item.lower() or "missing" not in item.lower()]
    if dob_match:
        issues = [item for item in issues if "dob" not in item.lower() or "mismatch" not in item.lower()]

    floor = 0
    if pan_valid and dob_match and name_similarity >= 70:
        floor = 82
    if pan_valid and dob_match and name_similarity >= 88:
        floor = 92
    score = max(int(result.get("identity_match_score", 0)), tool_result["identity_match_score"], floor)
    evidence = evidence if isinstance(evidence, dict) else {}
    evidence["identity_tool"] = tool_result
    return {"identity_match_score": min(100, score), "issues": issues, "evidence": evidence}
