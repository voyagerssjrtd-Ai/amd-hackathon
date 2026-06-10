from __future__ import annotations

from pathlib import Path

from mcp_tools.compliance_tools import run_compliance_screening
from services.llm_service import LLMService

ROOT_DIR = Path(__file__).resolve().parents[1]

def run_compliance_agent(state: dict) -> dict:
    data = state.get("extracted_data", {})
    tool_result = run_compliance_screening(
    customer_data=data,
    knowledge_dir=ROOT_DIR / "data",
)
    findings = tool_result["findings"]
    payload = {
    "customer": data,

    "candidate_findings": findings,

    "rag_context":
        tool_result.get(
            "rag_context",
            [],
        ),

    "tool_evidence":
        tool_result,
}
    try:
        result = enforce_compliance_gates(LLMService().assess_compliance(payload), findings)
    except Exception:
        result = {"status": "REVIEW" if findings else "CLEAR", "findings": findings, "tool_evidence": tool_result}
    result["tool_evidence"] = tool_result
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Compliance Agent",
            "status": "completed",
            "summary": "Screened customer against sample watchlist and blacklist datasets.",
        }
    )
    return {**state, "compliance_result": result, "timeline": timeline}


def enforce_compliance_gates(
    result: dict,
    findings: list[dict],
) -> dict:

    if any(
        item.get("source") == "blacklist"
        for item in findings
    ):
        result["status"] = "ESCALATE"

    elif findings:
        result["status"] = "REVIEW"

    else:
        result["status"] = "CLEAR"

    result["findings"] = findings

    return result
