# 🚨 LangGraph Incident Response Agent

An autonomous AI agent that classifies, investigates, and resolves production incidents — with Human-in-the-Loop approval via Slack.

> **Portfolio Project · Agentic AI Engineer Track**

---

## What This Does

When a production alert fires, this agent:

1. **Classifies** severity (P1–P4) with GPT-4o-mini
2. **Redacts PII** before any data reaches an LLM
3. **Investigates** root causes using 4 parallel worker agents (logs, metrics, database, network)
4. **Loops** until confident (> 0.7) or max rounds hit
5. **Pauses** for human approval via Slack button — graph persists to SQLite
6. **Resolves** the incident after approval
7. **Writes** a blameless postmortem with GPT-4o
8. **Notifies** via Slack and creates a Jira ticket

---

## Architecture Highlights

| Pattern | Where |
|---|---|
| `StateGraph` with 16 nodes | `graph/graph.py` |
| Parallel fan-out (`Send` API) | `investigation_supervisor` → 4 workers |
| Confidence loop with guard | `root_cause_analysis` → conditional edge |
| HITL + SQLite checkpoint | `interrupt_before=["hitl_review"]` |
| Slack Block Kit + Socket Mode | `integrations/slack.py` + `slack_socket.py` |
| FastAPI webhook | `api/app.py` |
| Pydantic structured output | All 5 LLM nodes |
| PII redaction (pre-LLM) | `security/pii_redactor.py` |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/yourusername/incident-response-agent.git
cd incident-response-agent
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure credentials
cp .env.example .env
# Fill in OPENAI_API_KEY, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SLACK_CHANNEL_ID

# 3. Start the server
uvicorn api.app:app --reload --port 8000

# 4. Send a test alert
curl -X POST http://localhost:8000/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "source": "pagerduty",
    "message": "Production database primary is not responding. 500 errors/sec.",
    "service": "postgres",
    "environment": "production"
  }'

# 5. Check Slack — click ✅ Approve to resume the graph
```

---

## Project Structure

```
incident-response-agent/
├── api/app.py                  # FastAPI — POST /webhook/alert, /webhook/slack
├── graph/graph.py              # LangGraph StateGraph wiring
├── state/schema.py             # IncidentState TypedDict (37 fields)
├── nodes/
│   ├── severity_classifier.py  # GPT-4o-mini — P1/P2/P3/P4
│   ├── investigation_supervisor.py  # GPT-4o — selects workers
│   ├── root_cause_analysis.py  # GPT-4o — confidence loop
│   ├── postmortem_writer.py    # GPT-4o — blameless postmortem
│   ├── communication_hub.py    # GPT-4o-mini — Slack + Jira
│   └── stubs.py                # 11 placeholder nodes (Phase 4)
├── integrations/
│   ├── slack.py                # WebClient — send Block Kit messages
│   └── slack_socket.py         # Bolt + Socket Mode — button callbacks
├── security/pii_redactor.py    # Regex PII scrubbing
├── requirements.txt
├── .env.example
└── documentation.md            # Full end-to-end documentation
```

---

## Environment Variables

```env
OPENAI_API_KEY=sk-...
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_CHANNEL_ID=C0XXXXXXXXX
```

See [documentation.md](documentation.md) for the full list including Jira and PostgreSQL variables.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/webhook/alert` | Receive incoming alert, start pipeline |
| `POST` | `/webhook/slack` | Slack interactive payload (HTTP mode) |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI (auto-generated) |

---

## Key Design Decisions

**Why LangGraph over a simple chain?**  
Incidents require branching (severity routing), loops (confidence re-investigation), parallel execution (4 workers), and stateful pause/resume (HITL). These patterns need a graph, not a chain.

**Why SQLiteSaver?**  
The HITL pause can last minutes to hours (waiting for a human to click Approve). The graph state must survive across HTTP requests. SQLiteSaver persists state using `thread_id = incident_id` as the key.

**Why Socket Mode instead of ngrok?**  
Slack Socket Mode uses a persistent WebSocket from your server to Slack. No public URL, no tunneling tools, no firewall configuration needed. Perfect for local development.

**Why `load_dotenv()` as the very first line?**  
`slack_socket.py` imports `graph.graph` at module level, which constructs `ChatOpenAI()` immediately. If `load_dotenv()` hasn't run, `OPENAI_API_KEY` is `None` and the import crashes.

---

## Phases

| Phase | Status | Description |
|---|---|---|
| Phase 1 | ✅ Complete | 16-node skeleton with stubs — full graph runs |
| Phase 2 | ✅ Complete | 5 real LLM nodes — GPT-4o and GPT-4o-mini |
| Phase 3 | ✅ Complete | FastAPI webhook + Slack HITL integration |
| Phase 4 | 🔜 Planned | Presidio PII, Jira API, PostgreSQL, rate limiting |

---

## Tech Stack

`LangGraph` · `LangChain` · `OpenAI GPT-4o` · `FastAPI` · `Slack SDK` · `Slack Bolt` · `SQLiteSaver` · `Pydantic` · `uvicorn` · `python-dotenv` · `certifi`

---

For complete documentation including node-by-node explanations, the full IncidentState schema, production module deep-dives, and extension guides, see [documentation.md](documentation.md).
