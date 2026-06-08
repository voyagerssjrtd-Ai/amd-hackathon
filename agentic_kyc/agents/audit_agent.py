from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT_DIR = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT_DIR / "reports"


def run_audit_agent(state: dict) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    extracted = state.get("extracted_data", {})
    safe_name = "".join(ch for ch in extracted.get("name", "customer") if ch.isalnum() or ch in ("-", "_"))
    filename = f"kyc_audit_{safe_name or 'customer'}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"
    report_path = REPORTS_DIR / filename
    build_report(report_path, state)
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Audit Agent",
            "status": "completed",
            "summary": "Generated downloadable PDF audit report.",
        }
    )
    return {**state, "report_path": str(report_path), "timeline": timeline}


def build_report(path: Path, state: dict) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story = [
        Paragraph("Agentic KYC Intelligence Platform - Audit Report", styles["Title"]),
        Spacer(1, 14),
        Paragraph("Customer Summary", styles["Heading2"]),
    ]

    extracted = state.get("extracted_data", {})
    add_table(story, [["Field", "Value"], *[[key, mask_if_sensitive(key, value)] for key, value in extracted.items()]])
    add_section(story, "Identity Verification", state.get("identity_result", {}))
    add_section(story, "Compliance Screening", state.get("compliance_result", {}))
    add_section(story, "Risk Scoring", state.get("risk_result", {}))
    add_section(story, "Final Decision", state.get("decision_result", {}))
    story.append(Paragraph("Agent Execution Timeline", styles["Heading2"]))
    add_table(
        story,
        [["Agent", "Status", "Summary"]]
        + [[item["agent"], item["status"], item["summary"]] for item in state.get("timeline", [])],
    )
    doc.build(story)


def add_section(story: list, title: str, payload: dict) -> None:
    styles = getSampleStyleSheet()
    story.append(Spacer(1, 10))
    story.append(Paragraph(title, styles["Heading2"]))
    rows = [["Key", "Value"]]
    for key, value in payload.items():
        rows.append([key, stringify(value)])
    add_table(story, rows)


def add_table(story: list, rows: list[list[str]]) -> None:
    table = Table(rows, colWidths=[140, 360])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324D")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7DEE8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 8))


def stringify(value: object) -> str:
    if isinstance(value, list):
        return "\n".join(stringify(item) for item in value) if value else "[]"
    if isinstance(value, dict):
        return "; ".join(f"{key}: {stringify(item)}" for key, item in value.items())
    return str(value)


def mask_if_sensitive(key: str, value: object) -> str:
    text = str(value)
    if "aadhaar" not in key.lower():
        return text
    digits = "".join(ch for ch in text if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else ""
