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

## Streamlit In JupyterLab

In many JupyterLab hackathon environments, `localhost` is inside the remote container, not your laptop. Start Streamlit with a public bind address:

```bash
streamlit run app.py \
  --server.address 0.0.0.0 \
  --server.port 8501 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
```

Check that Streamlit is alive inside the environment:

```bash
curl http://127.0.0.1:8501
```

If this returns HTML, the app is running.

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
3. Keep `Use bundled sample documents` enabled, or upload PAN and Aadhaar PDFs/images.
4. Click `Run KYC Analysis`.
5. Review customer data, identity score, compliance findings, risk score, decision, and timeline.
6. Use the manual override section to store a reviewer decision.
7. Download the generated audit PDF.

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
