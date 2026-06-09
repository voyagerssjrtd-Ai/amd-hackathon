from __future__ import annotations

from mcp_tools.financial_tools import analyze_financial_document


def run_financial_agent(state: dict) -> dict:
    result = analyze_financial_document(state.get("financial_path"))
    timeline = state.get("timeline", [])
    if result["status"] == "ANALYZED":
        summary = f"Financial profile analyzed: {result['financial_risk']} financial risk."
    else:
        summary = "No financial document supplied; financial risk marked UNKNOWN."
    timeline.append({"agent": "Financial Agent", "status": "completed", "summary": summary})
    return {**state, "financial_result": result, "timeline": timeline}
