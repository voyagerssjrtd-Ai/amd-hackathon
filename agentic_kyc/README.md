# AGENTS_002 - Agentic KYC Intelligence Platform

Complete 5-day hackathon MVP for agentic customer due diligence using Streamlit, Python 3.12, LangGraph, SQLite, simulated compliance datasets, and an OpenAI-compatible LLM endpoint.

## What It Demonstrates

- PAN and Aadhaar PDF text extraction
- LLM-assisted structured JSON extraction with deterministic fallback parsing
- Identity comparison across documents
- Simulated watchlist and blacklist screening
- Explainable risk scoring
- Final agent recommendation: `APPROVE`, `REVIEW`, or `ESCALATE`
- Human reviewer override stored in SQLite
- Downloadable PDF audit report
- Agent execution timeline in the Streamlit dashboard

## Project Structure

```text
agentic_kyc/
├── app.py
├── agents/
│   ├── document_agent.py
│   ├── identity_agent.py
│   ├── compliance_agent.py
│   ├── risk_agent.py
│   ├── decision_agent.py
│   └── audit_agent.py
├── services/
│   ├── llm_service.py
│   ├── pdf_service.py
│   └── scoring_service.py
├── database/
│   ├── models.py
│   └── kyc.db
├── data/
│   ├── watchlist.csv
│   ├── blacklist.csv
│   └── sample_documents/
├── reports/
├── uploads/
├── requirements.txt
├── .env
└── README.md
```

## Quick Start

```bash
cd agentic_kyc
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app creates `database/kyc.db`, `uploads/`, `reports/`, and bundled sample PDFs automatically when needed.

## AMD vLLM / OpenAI-Compatible Configuration

The `.env` file is preconfigured for the hackathon endpoint:

```env
BASE_URL=http://localhost:8000/v1
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct
OPENAI_API_KEY=EMPTY
DATABASE_PATH=database/kyc.db
```

If your vLLM server is running locally, the Document Agent calls it through the OpenAI Python SDK. If it is unavailable during a demo, the app falls back to deterministic extraction from the document text so the workflow still completes.

## Demo Flow

1. Start Streamlit with `streamlit run app.py`.
2. Keep `Use bundled sample documents` enabled, or upload PAN and Aadhaar PDFs.
3. Click `Run KYC Analysis`.
4. Review customer data, identity score, compliance findings, risk score, decision, and timeline.
5. Use the manual override section to store a reviewer decision.
6. Download the generated audit PDF.

## Simulated Compliance

The MVP intentionally avoids real Aadhaar, PAN, AML, sanctions, or banking integrations. Compliance screening uses:

- `data/watchlist.csv`
- `data/blacklist.csv`

To test review and escalation paths, add names, PAN numbers, or masked Aadhaar values to those files.

## Agent Workflow

```text
Customer Upload
  -> Document Agent
  -> Identity Agent
  -> Compliance Agent
  -> Risk Agent
  -> Decision Agent
  -> Audit Agent
```

The workflow is implemented with `langgraph.graph.StateGraph` in `app.py`.

## SQLite Tables

- `kyc_cases`: extracted data, agent outputs, final recommendation, report path
- `reviewer_decisions`: human override decisions and notes

## JupyterLab Compatibility

From a JupyterLab terminal:

```bash
cd agentic_kyc
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

Open the forwarded `8501` URL in your environment.
