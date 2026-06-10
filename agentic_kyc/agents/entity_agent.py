from __future__ import annotations

import json

from mcp_tools.identity_tools import (
    compare_identity_evidence,
    normalize_name,
)

from services.llm_service import LLMService


def run_entity_agent(state: dict) -> dict:

    extracted = state.get(
        "extracted_data",
        {},
    )

    pan_data = state.get(
        "pan_data",
        {},
    )

    aadhaar_data = state.get(
        "aadhaar_data",
        {},
    )

    #
    # MCP deterministic evidence.
    #

    tool_result = compare_identity_evidence(
        pan_data,
        aadhaar_data,
    )

    llm = LLMService()

    prompt = f"""
You are a KYC Identity Resolution Agent.

Determine whether the PAN holder and Aadhaar holder
represent the same individual.

PAN Name:
{pan_data.get("name", "")}

AADHAAR Name:
{aadhaar_data.get("name", "")}

DOB:
{extracted.get("dob", "")}

MCP Evidence:
{json.dumps(tool_result["evidence"], indent=2)}

Return STRICT JSON only:

{{
    "same_entity": true,
    "confidence": 95,
    "reasoning": [
        "reason 1",
        "reason 2"
    ]
}}
"""

    try:

        response = llm.invoke(
            prompt
        )

        llm_result = json.loads(
            response
        )

    except Exception:

        llm_result = {
            "same_entity":
                tool_result[
                    "identity_match_score"
                ]
                >= 80,

            "confidence":
                tool_result[
                    "identity_match_score"
                ],

            "reasoning": [
                "Fallback deterministic identity resolution used."
            ],
        }

    confidence = int(
        llm_result.get(
            "confidence",
            tool_result[
                "identity_match_score"
            ],
        )
    )

    confidence = max(
        0,
        min(100, confidence),
    )

    canonical_name = normalize_name(
        pan_data.get(
            "name",
            "",
        )
        or aadhaar_data.get(
            "name",
            "",
        )
    )

    result = {

        "canonical_name":
            canonical_name,

        "same_entity":
            llm_result.get(
                "same_entity",
                confidence >= 80,
            ),

        "confidence":
            confidence,

        "dob":
            extracted.get(
                "dob",
                "",
            ),

        "primary_identifier":
            extracted.get(
                "pan_number",
                "",
            )
            or extracted.get(
                "aadhaar_number",
                "",
            ),

        "reasoning":
            llm_result.get(
                "reasoning",
                [],
            ),

        "tool_evidence":
            tool_result,
    }

    timeline = state.get(
        "timeline",
        [],
    )

    timeline.append(
        {
            "agent":
                "Entity Resolution Agent",

            "status":
                "completed",

            "summary":
                (
                    f"Resolved entity with "
                    f"{confidence}% confidence."
                ),
        }
    )

    return {
        **state,

        "entity_result":
            result,

        "timeline":
            timeline,
    }