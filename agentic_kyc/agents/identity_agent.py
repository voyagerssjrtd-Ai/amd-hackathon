from __future__ import annotations

from services.llm_service import LLMService
from services.scoring_service import identity_score
from mcp_tools.identity_tools import compare_identity_evidence


def run_identity_agent(state: dict) -> dict:
    """
    Identity Verification Agent.

    Purpose:
    - Verify that PAN and Aadhaar belong to the same person.
    - Use MCP tools for deterministic evidence.
    - Use LLM reasoning for explainability.
    - Prevent LLM hallucinations from overriding evidence.
    """

    pan_data = state.get("pan_data", {})
    aadhaar_data = state.get("aadhaar_data", {})

    #
    # Step 1: MCP deterministic evidence.
    #

    tool_result = compare_identity_evidence(
        pan_data,
        aadhaar_data,
    )

    #
    # Step 2: LLM verification.
    #

    try:

        llm_result = LLMService().verify_identity(
            pan_data,
            aadhaar_data,
        )

        result = enforce_identity_truth(
            llm_result,
            tool_result,
        )

        result["verification_source"] = (
            "LLM + MCP"
        )

    #
    # Step 3: Fallback.
    #

    except Exception:

        fallback = identity_score(
            state.get(
                "extracted_data",
                {},
            ),
            state.get(
                "pan_text",
                "",
            ),
            state.get(
                "aadhaar_text",
                "",
            ),
            pan_data,
            aadhaar_data,
        )

        result = enforce_identity_truth(
            fallback,
            tool_result,
        )

        result["verification_source"] = (
            "Deterministic Fallback"
        )

    #
    # Step 4: Final verification flag.
    #

    score = result.get(
        "identity_match_score",
        0,
    )

    result["identity_verified"] = (
        score >= 85
    )

    #
    # Step 5: Timeline.
    #

    timeline = state.get(
        "timeline",
        [],
    )

    summary = (
        f"Identity score: {score}. "
        f"Verified: "
        f"{'YES' if result['identity_verified'] else 'NO'}."
    )

    timeline.append(
        {
            "agent":
                "Identity Agent",

            "status":
                "completed",

            "summary":
                summary,
        }
    )

    return {
        **state,

        "identity_result":
            result,

        "timeline":
            timeline,
    }


def enforce_identity_truth(
    result: dict,
    tool_result: dict,
) -> dict:
    """
    Prevent LLM hallucinations from contradicting
    deterministic MCP evidence.
    """

    issues = list(
        result.get(
            "issues",
            [],
        )
    )

    evidence = result.get(
        "evidence",
        {},
    )

    if not isinstance(
        evidence,
        dict,
    ):
        evidence = {}

    #
    # MCP evidence.
    #

    identity_tool = tool_result.get(
        "evidence",
        {},
    )

    pan_validation = identity_tool.get(
        "pan_validation",
        {},
    )

    pan_valid = pan_validation.get(
        "valid",
        False,
    )

    dob_match = identity_tool.get(
        "dob_match",
        False,
    )

    name_similarity = identity_tool.get(
        "name_similarity",
        0,
    )

    #
    # Remove false LLM issues.
    #

    if pan_valid:

        issues = [

            issue

            for issue in issues

            if (
                "pan" not in issue.lower()
            )
        ]

    if dob_match:

        issues = [

            issue

            for issue in issues

            if (
                "dob" not in issue.lower()
            )
        ]

    #
    # Determine minimum confidence floor.
    #

    floor = 0

    if (
        pan_valid
        and dob_match
        and name_similarity >= 70
    ):
        floor = 82

    if (
        pan_valid
        and dob_match
        and name_similarity >= 88
    ):
        floor = 92

    #
    # Final score consensus.
    #

    llm_score = int(
        result.get(
            "identity_match_score",
            0,
        )
    )

    tool_score = int(
        tool_result.get(
            "identity_match_score",
            0,
        )
    )

    final_score = max(
        llm_score,
        tool_score,
        floor,
    )

    final_score = min(
        100,
        final_score,
    )

    #
    # Evidence aggregation.
    #

    evidence[
        "identity_tool"
    ] = tool_result

    evidence[
        "verification_consensus"
    ] = {
        "llm_score":
            llm_score,

        "tool_score":
            tool_score,

        "minimum_floor":
            floor,

        "final_score":
            final_score,
    }

    #
    # Add reasoning.
    #

    reasoning = []

    if pan_valid:

        reasoning.append(
            "PAN passed deterministic validation."
        )

    if dob_match:

        reasoning.append(
            "DOB matched across PAN and Aadhaar."
        )

    if name_similarity >= 88:

        reasoning.append(
            f"Strong name similarity ({name_similarity})."
        )

    elif name_similarity >= 70:

        reasoning.append(
            f"Moderate name similarity ({name_similarity})."
        )

    else:

        reasoning.append(
            f"Low name similarity ({name_similarity})."
        )

    return {

        "identity_match_score":
            final_score,

        "identity_verified":
            final_score >= 85,

        "issues":
            issues,

        "reasoning":
            reasoning,

        "evidence":
            evidence,
    }