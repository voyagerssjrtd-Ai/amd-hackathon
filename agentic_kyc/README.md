# AGENTS_002 - Agentic KYC Intelligence Platform

Complete 5-day hackathon MVP for agentic customer due diligence using Streamlit, Python 3.12, LangGraph, SQLite, simulated compliance datasets, and an OpenAI-compatible AMD vLLM endpoint.

## What It Demonstrates

- PAN and Aadhaar PDF text extraction
- Scanned PDF and direct image upload support through a vision-capable OpenAI-compatible model
- LLM-assisted structured JSON extraction with deterministic fallback parsing
- Identity comparison across documents
- Simulated watchlist and blacklist screening
- Explainable risk scoring
- Final agent recommendation: `APPROVE`, `REVIEW`, or `ESCALATE`
- Human reviewer override stored in SQLite
- Downloadable PDF audit report
- Agent execution timeline in the Streamlit dashboard

## Agent Reasoning Model

The platform uses an LLM-first agent design:

- Document Agent asks the multimodal LLM to extract each document separately.
- Entity Resolution Agent builds the canonical customer entity from document evidence.
- Identity Agent asks the LLM to compare PAN evidence against Aadhaar evidence.
- Compliance Agent uses deterministic CSV screening for evidence, then asks the LLM to interpret the findings.
- Financial Agent analyzes an optional bank statement or payslip.
- Risk Agent asks the LLM for an explainable risk score.
- Decision Agent asks the LLM for the final recommendation.

Deterministic guardrails are still applied after LLM outputs for demo safety. For example, missing PAN number can never be approved, blacklist hits always escalate, and watchlist hits always require review.

## Enterprise-Style Agentic Architecture

```text
Streamlit UI
  -> LangGraph Orchestrator
  -> Specialized Agents
  -> MCP-style Tool Layer
  -> SQLite Evidence Store
```

Agents:

- Document Agent
- Entity Resolution Agent
- Identity Agent
- Compliance Agent
- Financial Agent
- Risk Agent
- Decision Agent
- Audit Agent

MCP-style local tools:

- `identity.validate_pan`
- `identity.compare_identity_evidence`
- `screening.search_watchlists`
- `financial.analyze_document`

Every run stores agent timeline rows in `agent_execution_logs` and structured evidence in `agent_evidence`.

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

## AMD vLLM Configuration

The `.env` file is configured for a local OpenAI-compatible vLLM endpoint:

```env
BASE_URL=http://localhost:8000/v1
MODEL_NAME=Qwen/Qwen2.5-VL-7B-Instruct
OPENAI_API_KEY=EMPTY
DATABASE_PATH=database/kyc.db
```

Use the multimodal VL model for scanned PDFs and direct image uploads:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-VL-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --trust-remote-code \
  --max-model-len 8192
```

Verify the model server:

```bash
curl -s http://127.0.0.1:8000/v1/models | python -m json.tool
```

You should see `Qwen/Qwen2.5-VL-7B-Instruct`.

For text-only PDF demos, `Qwen/Qwen2.5-7B-Instruct` also works, but it cannot read scanned PDFs or uploaded images.


## Cloudflare Tunnel For External Demo Link

Streamlit does not provide a built-in temporary public URL like Gradio `share=True`. Use Cloudflare Tunnel to expose the local Streamlit server.

Download `cloudflared` in the project folder:

```bash
wget -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared
```

Run Streamlit in terminal 1:

```bash
streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
```

Run Cloudflare Tunnel in terminal 2:

```bash
./cloudflared tunnel --url http://127.0.0.1:8501
```

Cloudflare prints a temporary public URL like:

```text
https://your-random-name.trycloudflare.com
```

Open that URL in your browser. Keep both terminals running. If you stop `cloudflared`, the link stops working. If you restart it, a new link is generated.

The message below is harmless for quick tunnels:

```text
Cannot determine default configuration path
```

## Recommended Hackathon Run Order

Terminal 1 - start multimodal vLLM:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-VL-7B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --trust-remote-code \
  --max-model-len 8192
```

Terminal 2 - start Streamlit:

```bash
streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
```

Terminal 3 - create external link:

```bash
./cloudflared tunnel --url http://127.0.0.1:8501
```

## Demo Flow

1. Start vLLM, Streamlit, and Cloudflare Tunnel.
2. Open the `trycloudflare.com` URL.
3. Keep `Use bundled sample documents` enabled, or upload all KYC files through the single multi-file uploader.
4. The Document Agent classifies each file as PAN, Aadhaar, financial, or unknown using extracted text and file-name fallback.
5. Click `Run KYC Analysis`.
6. Review customer data, OCR/VL previews, identity score, compliance findings, risk score, decision, and timeline.
7. Use the manual override section to store a reviewer decision.
8. Download the generated audit PDF.

## OCR And Image Handling

The extraction pipeline handles:

- text PDFs through `pdfplumber` and `pypdf`
- scanned PDFs by rendering pages with PyMuPDF
- direct image uploads through the multimodal OpenAI-compatible vLLM call

The Streamlit dashboard shows document classification and text previews so reviewers can validate whether OCR/VL capture worked for each file.

## Simulated Compliance

The MVP intentionally avoids real Aadhaar, PAN, AML, sanctions, or banking integrations. Compliance screening uses:

- `data/watchlist.csv`
- `data/blacklist.csv`

To test review and escalation paths, add names, PAN numbers, or masked Aadhaar values to those files.

## Agent Workflow

```text
Customer Upload
  -> Document Agent
  -> Entity Resolution Agent
  -> Identity Agent
  -> Compliance Agent
  -> Financial Agent
  -> Risk Agent
  -> Decision Agent
  -> Audit Agent
```

The workflow is implemented with `langgraph.graph.StateGraph` in `app.py`.

## SQLite Tables

- `kyc_cases`: extracted data, agent outputs, final recommendation, report path
- `reviewer_decisions`: human override decisions and notes
- `agent_execution_logs`: auditable timeline of each agent action
- `agent_evidence`: structured evidence emitted by every agent

## Qdrant Compliance RAG

The compliance tools can use embedded local Qdrant at `database/qdrant`.
Embedded Qdrant allows only one active client for the same storage folder. If
Streamlit reruns or multiple terminals collide, the app now falls back to an
in-memory index instead of crashing.

Compliance RAG flow:

1. Exact tools screen watchlist, blacklist, and PEP CSV files.
2. Qdrant indexes compliance knowledge from `data/compliance_knowledge/`.
3. The Compliance Agent builds a semantic query from exact findings, customer
   fields, and extracted document text.
4. Retrieved RAG context is passed to the LLM compliance reasoning step and
   stored as tool evidence.

For true concurrent access, run Qdrant as a server and set:

```env
QDRANT_URL=http://127.0.0.1:6333
```

Then start Qdrant separately:

```bash
docker run -p 6333:6333 qdrant/qdrant
```

If Qdrant dependencies are unavailable, compliance screening still works from
CSV files and records `QDRANT_UNAVAILABLE` as tool evidence.

If Hugging Face prints unauthenticated download warnings for the embedding
model, optionally set:

```bash
export HF_TOKEN=your_huggingface_token
```
