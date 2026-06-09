from __future__ import annotations

from pathlib import Path

from services.llm_service import LLMService
from mcp_tools.screening_tools import search_watchlists


ROOT_DIR = Path(__file__).resolve().parents[1]


def run_compliance_agent(state: dict) -> dict:
    data = state.get("extracted_data", {})
    tool_result = search_watchlists(data, ROOT_DIR / "data")
    findings = tool_result["findings"]
    payload = {"customer": data, "candidate_findings": findings, "tool_evidence": tool_result}
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


def enforce_compliance_gates(result: dict, findings: list[dict]) -> dict:
    if findings:
        return {"status": "REVIEW", "findings": findings}
    return {"status": "CLEAR", "findings": []}
