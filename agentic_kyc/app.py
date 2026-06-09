from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, TypedDict

import streamlit as st
from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.audit_agent import run_audit_agent
from agents.compliance_agent import run_compliance_agent
from agents.decision_agent import run_decision_agent
from agents.document_agent import run_document_agent
from agents.identity_agent import run_identity_agent
from agents.risk_agent import run_risk_agent
from database.models import init_db, list_cases, save_case, save_reviewer_decision


load_dotenv()
UPLOADS_DIR = ROOT_DIR / "uploads"
SAMPLES_DIR = ROOT_DIR / "data" / "sample_documents"


class KYCState(TypedDict, total=False):
    pan_path: str
    aadhaar_path: str
    pan_text: str
    aadhaar_text: str
    pan_data: dict[str, Any]
    aadhaar_data: dict[str, Any]
    extracted_data: dict[str, str]
    identity_result: dict[str, Any]
    compliance_result: dict[str, Any]
    risk_result: dict[str, Any]
    decision_result: dict[str, Any]
    report_path: str
    timeline: list[dict[str, str]]


@st.cache_resource
def build_workflow():
    workflow = StateGraph(KYCState)
    workflow.add_node("document_agent", run_document_agent)
    workflow.add_node("identity_agent", run_identity_agent)
    workflow.add_node("compliance_agent", run_compliance_agent)
    workflow.add_node("risk_agent", run_risk_agent)
    workflow.add_node("decision_agent", run_decision_agent)
    workflow.add_node("audit_agent", run_audit_agent)
    workflow.set_entry_point("document_agent")
    workflow.add_edge("document_agent", "identity_agent")
    workflow.add_edge("identity_agent", "compliance_agent")
    workflow.add_edge("compliance_agent", "risk_agent")
    workflow.add_edge("risk_agent", "decision_agent")
    workflow.add_edge("decision_agent", "audit_agent")
    workflow.add_edge("audit_agent", END)
    return workflow.compile()


def main() -> None:
    init_db()
    ensure_directories()
    ensure_sample_pdfs()
    st.set_page_config(page_title="Agentic KYC Intelligence", page_icon="KYC", layout="wide")
    render_styles()
    
    # Initialize session state early to prevent file upload issues
    if "kyc_state" not in st.session_state:
        st.session_state["kyc_state"] = None

    st.title("Agentic KYC Intelligence Platform")
    st.caption("Multi-agent customer due diligence with simulated identity, compliance, risk, and audit workflows.")

    left, right = st.columns([0.38, 0.62], gap="large")
    with left:
        render_onboarding()
    with right:
        render_results()

    render_case_history()


def render_onboarding() -> None:
    st.subheader("Customer Onboarding")
    supported_types = ["pdf", "png", "jpg", "jpeg", "webp"]
    
    st.info("📄 Upload PAN and Aadhaar documents (PDF or image), or use bundled samples")
    
    pan_file = st.file_uploader("Upload PAN document", type=supported_types, key="pan_pdf")
    aadhaar_file = st.file_uploader("Upload Aadhaar document", type=supported_types, key="aadhaar_pdf")

    sample_pan = SAMPLES_DIR / "sample_pan.pdf"
    sample_aadhaar = SAMPLES_DIR / "sample_aadhaar.pdf"
    use_sample = st.toggle("Use bundled sample documents", value=not pan_file and not aadhaar_file)

    st.info(
        f"LLM endpoint: {os.getenv('BASE_URL', 'http://localhost:8000/v1')} | "
        f"Model: {os.getenv('MODEL_NAME', 'Qwen/Qwen2.5-7B-Instruct')}"
    )
    if "vl" not in os.getenv("MODEL_NAME", "").lower():
        st.warning(
            "For scanned PDFs or image uploads, run a vision-capable vLLM model such as "
            "Qwen/Qwen2.5-VL-7B-Instruct. Text PDFs still work with the current model."
        )

    if st.button("Run KYC Analysis", type="primary", use_container_width=True):
        with st.spinner("Agents are collaborating on the KYC case..."):
            try:
                if use_sample:
                    pan_path, aadhaar_path = sample_pan, sample_aadhaar
                else:
                    if not pan_file or not aadhaar_file:
                        st.error("Upload both PAN and Aadhaar PDF files, or enable bundled sample documents.")
                        return
                    pan_path = save_upload(pan_file, "pan")
                    aadhaar_path = save_upload(aadhaar_file, "aadhaar")

                graph = build_workflow()
                state = graph.invoke({"pan_path": str(pan_path), "aadhaar_path": str(aadhaar_path), "timeline": []})
                case_id = save_case(state)
                state["case_id"] = case_id
                st.session_state["kyc_state"] = state
                st.success(f"KYC analysis complete. Case #{case_id} created.")
            except Exception as e:
                st.error(f"Error during KYC analysis: {str(e)}")
                import traceback
                st.error(traceback.format_exc())


def render_results() -> None:
    st.subheader("Results Dashboard")
    state = st.session_state.get("kyc_state")
    if not state:
        st.write("Run a KYC analysis to see customer intelligence, risk evidence, and reviewer controls.")
        render_empty_timeline()
        return

    extracted = state.get("extracted_data", {})
    identity = state.get("identity_result", {})
    compliance = state.get("compliance_result", {})
    risk = state.get("risk_result", {})
    decision = state.get("decision_result", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Identity Match", f"{identity.get('identity_match_score', 0)}")
    m2.metric("Compliance", compliance.get("status", "UNKNOWN"))
    m3.metric("Risk Score", f"{risk.get('risk_score', 0)}", risk.get("risk_level", ""))
    m4.metric("Decision", decision.get("recommendation", "PENDING"))

    st.markdown("#### Customer Information")
    st.dataframe(
        [
            {"Field": "Name", "Value": extracted.get("name", "")},
            {"Field": "DOB", "Value": extracted.get("dob", "")},
            {"Field": "PAN", "Value": extracted.get("pan_number", "")},
            {"Field": "Aadhaar", "Value": mask_aadhaar(extracted.get("aadhaar_number", ""))},
            {"Field": "Address", "Value": extracted.get("address", "")},
        ],
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("#### Document Extraction Evidence")
    e1, e2 = st.columns(2)
    with e1:
        st.write("PAN extraction")
        st.json(mask_sensitive_payload(state.get("pan_data", {})))
    with e2:
        st.write("Aadhaar extraction")
        st.json(mask_sensitive_payload(state.get("aadhaar_data", {})))

    if not extracted.get("pan_number"):
        st.error("PAN number was not extracted. The case must be REVIEW until PAN is manually validated or re-uploaded.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Reasons")
        for reason in risk.get("reasons", []):
            st.write(f"- {reason}")
        st.markdown("#### Decision Explanation")
        st.write(decision.get("explanation", ""))
    with c2:
        st.markdown("#### Compliance Findings")
        findings = compliance.get("findings", [])
        if findings:
            st.dataframe(findings, hide_index=True, use_container_width=True)
        else:
            st.success("No simulated watchlist or blacklist matches.")

    render_timeline(state.get("timeline", []))
    render_human_review(state)
    render_report_download(state)


def render_timeline(timeline: list[dict[str, str]]) -> None:
    st.markdown("#### Agent Execution Timeline")
    cols = st.columns(len(timeline) or 1)
    for col, item in zip(cols, timeline):
        with col:
            st.markdown(
                f"""
                <div class="timeline-step">
                    <div class="timeline-check">✓</div>
                    <strong>{item['agent']}</strong>
                    <small>{item['summary']}</small>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_empty_timeline() -> None:
    steps = ["Document", "Identity", "Compliance", "Risk", "Decision", "Audit"]
    cols = st.columns(len(steps))
    for col, step in zip(cols, steps):
        with col:
            st.markdown(
                f"<div class='timeline-step pending'><div class='timeline-check'>•</div><strong>{step}</strong></div>",
                unsafe_allow_html=True,
            )


def render_human_review(state: dict) -> None:
    st.markdown("#### Human-in-the-Loop Review")
    notes = st.text_area("Reviewer notes", key=f"review_notes_{state.get('case_id')}", height=80)
    cols = st.columns(3)
    for col, decision in zip(cols, ["APPROVE", "REVIEW", "ESCALATE"]):
        with col:
            if st.button(decision.title(), use_container_width=True, key=f"manual_{decision}"):
                save_reviewer_decision(int(state["case_id"]), decision, notes)
                st.success(f"Reviewer decision saved: {decision}")


def render_report_download(state: dict) -> None:
    report_path = Path(state.get("report_path", ""))
    if report_path.exists():
        st.download_button(
            "Download Audit PDF",
            data=report_path.read_bytes(),
            file_name=report_path.name,
            mime="application/pdf",
            use_container_width=True,
        )


def render_case_history() -> None:
    st.divider()
    st.subheader("Recent Cases")
    cases = list_cases()
    if not cases:
        st.write("No stored cases yet.")
        return
    st.dataframe(
        [
            {
                "Case": case["id"],
                "Customer": case["customer_name"],
                "PAN": case["pan_number"],
                "Aadhaar": case["aadhaar_number_masked"],
                "Created": case["created_at"],
                "Reviewer Decision": case.get("reviewer_decision") or "",
            }
            for case in cases
        ],
        hide_index=True,
        use_container_width=True,
    )


def save_upload(uploaded_file, prefix: str) -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(ch for ch in uploaded_file.name if ch.isalnum() or ch in ("-", "_", "."))
    path = UPLOADS_DIR / f"{prefix}_{safe_name}"
    path.write_bytes(uploaded_file.getbuffer())
    return path


def ensure_directories() -> None:
    for path in [UPLOADS_DIR, ROOT_DIR / "reports", SAMPLES_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def ensure_sample_pdfs() -> None:
    samples = {
        SAMPLES_DIR / "sample_pan.pdf": [
            "INCOME TAX DEPARTMENT",
            "GOVT. OF INDIA",
            "Permanent Account Number Card",
            "Name: Ananya Rao",
            "Date of Birth: 1991-07-18",
            "PAN Number: AORPR2481F",
        ],
        SAMPLES_DIR / "sample_aadhaar.pdf": [
            "Government of India",
            "Aadhaar",
            "Name: Ananya Rao",
            "DOB: 1991-07-18",
            "Aadhaar Number: 4821 6630 9182",
            "Address: 42 Lake View Road, Indiranagar, Bengaluru, Karnataka 560038",
        ],
    }
    for path, lines in samples.items():
        if path.exists():
            continue
        c = canvas.Canvas(str(path), pagesize=A4)
        y = 790
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, y, lines[0])
        c.setFont("Helvetica", 12)
        for line in lines[1:]:
            y -= 28
            c.drawString(72, y, line)
        c.save()


def render_styles() -> None:
    st.markdown(
        """
        <style>
        .timeline-step {
            min-height: 118px;
            border: 1px solid #d8e0ea;
            border-radius: 8px;
            padding: 12px;
            background: #ffffff;
        }
        .timeline-step.pending {
            opacity: 0.55;
        }
        .timeline-check {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #0f766e;
            color: white;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .timeline-step small {
            display: block;
            margin-top: 6px;
            color: #4b5f73;
            line-height: 1.35;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def mask_aadhaar(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else ""


def mask_sensitive_payload(payload: dict[str, Any]) -> dict[str, Any]:
    masked = dict(payload)
    if masked.get("aadhaar_number"):
        masked["aadhaar_number"] = mask_aadhaar(str(masked["aadhaar_number"]))
    return masked


if __name__ == "__main__":
    main()
