# LangGraph Incident Response Agent — Complete Documentation

> **Portfolio Project · Agentic AI Engineer Track**  
> An autonomous, production-grade incident response system powered by LangGraph, OpenAI GPT-4o, FastAPI, and Slack.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Tech Stack](#2-tech-stack)
3. [Folder Structure](#3-folder-structure)
4. [Core Concepts for Beginners](#4-core-concepts-for-beginners)
5. [Data Schema — IncidentState](#5-data-schema--incidentstate)
6. [Complete Application Flow](#6-complete-application-flow)
7. [LangGraph Pipeline — Node by Node](#7-langgraph-pipeline--node-by-node)
8. [Production Modules](#8-production-modules)
   - 8.1 PII Redaction
   - 8.2 Human-in-the-Loop (HITL)
   - 8.3 Loop Guards
   - 8.4 SQLite Persistence & Checkpointing
   - 8.5 Slack Integration (Block Kit + Socket Mode)
   - 8.6 FastAPI Webhook Layer
   - 8.7 Structured LLM Output (Pydantic)
   - 8.8 Confidence-Driven Routing
9. [API Reference](#9-api-reference)
10. [Environment Variables](#10-environment-variables)
11. [Setup & Running](#11-setup--running)
12. [Testing Each Phase](#12-testing-each-phase)
13. [How to Extend](#13-how-to-extend)

---

## 1. Project Overview

The **LangGraph Incident Response Agent** is a fully autonomous AI system that:

1. **Receives** incoming alerts from monitoring tools (PagerDuty, Datadog, custom webhooks)
2. **Classifies** incident severity (P1–P4) using GPT-4o-mini
3. **Investigates** root causes in parallel across four specialized worker agents (logs, metrics, database, network)
4. **Routes** based on confidence — if the analysis confidence is low (<0.7), it re-investigates (up to 2 rounds)
5. **Pauses for human approval** on P1/P2 incidents via Slack buttons before resolving
6. **Resolves** incidents through automated remediation steps
7. **Writes** a blameless postmortem document
8. **Notifies** stakeholders via Slack and creates Jira tickets

The system is built for real-world engineering teams. It demonstrates every advanced LangGraph pattern: multi-agent supervision, parallel fan-out with the Send API, Human-in-the-Loop (HITL) with SQLite-backed checkpointing, and confidence-driven conditional loops.

### What makes this portfolio-worthy?

| Pattern | Implementation |
|---|---|
| Multi-agent supervisor | `investigation_supervisor` dynamically selects workers |
| Parallel execution | `Send` API fans out to 4 workers simultaneously |
| HITL with persistence | `interrupt_before=["hitl_review"]` + `SQLiteSaver` |
| Conditional loops | Confidence score loop with max-round guard |
| Structured LLM output | `with_structured_output(PydanticModel)` on every node |
| PII redaction pre-LLM | Regex-based scrubbing before any data reaches GPT |
| Real Slack integration | Block Kit messages + Socket Mode button callbacks |
| Production API | FastAPI with lifespan context manager |

---

## 2. Tech Stack

### Core Framework

| Component | Technology | Why |
|---|---|---|
| Agent orchestration | **LangGraph 0.2+** | StateGraph, Send API, HITL, checkpointing |
| LLM calls | **LangChain + OpenAI** | `ChatOpenAI`, `with_structured_output` |
| LLM models | **GPT-4o + GPT-4o-mini** | 4o for reasoning, 4o-mini for classification |
| State schema | **TypedDict + Pydantic** | Type-safe state; structured LLM responses |
| Persistence | **SQLiteSaver** | Thread-based checkpointing for HITL resume |

### API & Integrations

| Component | Technology | Why |
|---|---|---|
| Webhook server | **FastAPI** | Async, modern, auto-docs at `/docs` |
| Slack messages | **Slack SDK WebClient** | Block Kit interactive messages |
| Slack buttons | **Slack Bolt + Socket Mode** | Real-time button callbacks, no ngrok |
| Environment config | **python-dotenv** | Secure credential loading |
| SSL certificates | **certifi** | Mac Python SSL fix |

### Developer Tools

| Component | Technology |
|---|---|
| Package management | `pip` + `requirements.txt` |
| Local dev server | `uvicorn` with `--reload` |
| Testing | Direct Python node calls |
| Type checking | Pydantic v2 |

---

## 3. Folder Structure

```
incident-response-agent/
│
├── main.py                    # Entry point for direct graph testing
├── requirements.txt           # All Python dependencies
├── .env                       # Secrets (never committed)
├── .env.example               # Template — copy to .env
├── .gitignore                 # Excludes .env, *.db, __pycache__, venv/
│
├── state/
│   └── schema.py              # IncidentState TypedDict — 37 fields
│
├── nodes/
│   ├── stubs.py               # 11 placeholder nodes (Phase 4 targets)
│   ├── severity_classifier.py # Node 1 — GPT-4o-mini, classifies P1–P4
│   ├── investigation_supervisor.py  # Node 3 — GPT-4o, selects workers
│   ├── root_cause_analysis.py # Node 4 (loop) — GPT-4o, confidence score
│   ├── postmortem_writer.py   # Node 5 — GPT-4o, blameless postmortem
│   └── communication_hub.py   # Node 6 — GPT-4o-mini, drafts Slack/Jira
│
├── graph/
│   └── graph.py               # StateGraph wiring — all nodes + edges
│
├── security/
│   └── pii_redactor.py        # Regex PII scrubbing (pre-LLM)
│
├── api/
│   ├── __init__.py
│   └── app.py                 # FastAPI app — /webhook/alert, /webhook/slack
│
├── integrations/
│   ├── __init__.py
│   ├── slack.py               # WebClient — send Block Kit messages
│   └── slack_socket.py        # Bolt + Socket Mode — button callbacks
│
└── data/
    └── incidents.db            # SQLite checkpoint store (auto-created)
```

### Key Design Decision: Why This Structure?

- **`nodes/`** — each node is its own file. This makes it easy to swap in a real implementation later without touching the graph.
- **`state/schema.py`** — single source of truth for state shape. Every node reads from and writes to this schema.
- **`integrations/`** — Slack is separated into two files because `slack.py` is for *sending* (called from nodes) and `slack_socket.py` is for *receiving* (runs as a background thread).
- **`security/`** — PII redaction is a separate module so it can be upgraded to `presidio` in Phase 4 without touching node code.

---

## 4. Core Concepts for Beginners

### What is LangGraph?

LangGraph is a framework for building stateful, multi-step AI agents. Think of it as a **flowchart where each box is an AI function** and the arrows between boxes can have conditions.

```
Alert comes in
     │
     ▼
[classify severity]  ─── P3/P4? ──► [low severity path]
     │
     P1/P2
     │
     ▼
[redact PII]
     │
     ▼
[run investigation]  ──► [4 workers in parallel]
     │
     ▼
[analyze root cause]  ─── confidence < 0.7? ──► re-investigate
     │
     confidence > 0.7
     │
     ▼
[human review in Slack]  ─── rejected? ──► [escalate]
     │
     approved
     │
     ▼
[apply fix] ──► [write postmortem] ──► [notify team]
```

### StateGraph vs. Graph

A regular graph just connects nodes. A **StateGraph** passes a shared dictionary (called `state`) between every node. Each node reads what it needs and writes back its updates. The state grows richer as the incident moves through the pipeline.

### What is the "Send API" (Parallel Execution)?

Normally, nodes run one after another. The `Send` API lets one node **fan out** to multiple nodes at the same time. In this project, `investigation_supervisor` sends the incident to four workers (logs, metrics, database, network) simultaneously. All four run in parallel, and their results are merged back into state.

### What is HITL (Human-in-the-Loop)?

For critical P1/P2 incidents, we don't want the AI to auto-apply fixes. The graph **pauses** at the `hitl_review` node and sends a Slack message with ✅ Approve / ❌ Reject buttons. When a human clicks a button, the graph **resumes** from where it paused.

This is possible because LangGraph's `SQLiteSaver` checkpointer saves the entire graph state to a database at every step. When the Slack callback arrives, we load the saved state and continue.

### What is a Conditional Edge?

A conditional edge is a function that decides which node to go to next. For example:

```python
def route_by_severity(state):
    if state["severity"] in ["P1", "P2"]:
        return "pii_redactor"
    else:
        return "low_severity_handler"
```

This project uses three conditional edges:
- **Severity router** — after classification: P1/P2 → full pipeline; P3/P4 → lightweight path
- **Confidence router** — after root cause analysis: confidence > 0.7 → proceed; ≤ 0.7 → re-investigate
- **HITL router** — after human review: approved → remediation; rejected → escalation

---

## 5. Data Schema — IncidentState

The `IncidentState` TypedDict in `state/schema.py` is the single shared dictionary passed through every node. All 37 fields are shown below, grouped by lifecycle phase.

```python
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages

class IncidentState(TypedDict):
    # ── Identity ──────────────────────────────────────────────────
    incident_id: str              # e.g. "INC-A3F2B1C4"
    source: str                   # e.g. "pagerduty", "datadog", "webhook"
    alert: str                    # Raw alert message text (PII-redacted)
    service: str                  # Affected service name
    environment: str              # "production", "staging", "dev"
    created_at: str               # ISO timestamp

    # ── Classification (Node 1: severity_classifier) ──────────────
    severity: str                 # "P1", "P2", "P3", "P4"
    incident_type: str            # "database", "network", "application", "security", "infrastructure"
    affected_systems: list[str]   # ["api-gateway", "postgres-primary"]
    classification_confidence: float  # 0.0–1.0

    # ── Security (Node 2: pii_redactor) ───────────────────────────
    pii_detected: bool            # True if PII was found and redacted
    pii_types: list[str]          # ["email", "phone", "ip_address"]
    redaction_summary: str        # Human-readable redaction report

    # ── Investigation (Node 3: investigation_supervisor + workers) ─
    investigation_plan: str       # Supervisor's reasoning for which workers to use
    workers_dispatched: list[str] # ["logs_worker", "metrics_worker"]
    log_findings: str             # From logs_worker
    metrics_findings: str         # From metrics_worker
    database_findings: str        # From database_worker
    network_findings: str         # From network_worker
    investigation_rounds: int     # 0, 1, or 2 (loop guard)

    # ── Root Cause (Node 4: root_cause_analysis) ──────────────────
    root_cause: str               # GPT-4o's root cause paragraph
    confidence: float             # 0.0–1.0 (> 0.7 exits loop)
    confidence_reason: str        # One sentence explaining the score

    # ── HITL (Node 5: hitl_review) ────────────────────────────────
    human_approved: Optional[bool]   # True/False after Slack button click
    human_feedback: Optional[str]    # "approved" / "rejected"
    human_reviewer: Optional[str]    # Slack user ID

    # ── Resolution (Node 6: resolution_engine) ────────────────────
    remediation_steps: list[str]  # Steps taken to resolve the incident
    resolution_status: str        # "resolved", "escalated", "failed"
    resolution_time: str          # ISO timestamp

    # ── Integrations (Node 7: communication_hub) ──────────────────
    slack_thread_id: str          # Slack message timestamp (thread key)
    jira_ticket_id: str           # e.g. "INC-A3F2B1C"
    stakeholders_notified: list[str]  # Slack user IDs notified

    # ── Postmortem (Node 8: postmortem_writer) ────────────────────
    postmortem_url: str           # e.g. "postmortem://INC-A3F2B1C4"

    # ── Audit Trail (all nodes append) ───────────────────────────
    timeline: Annotated[list[dict], append]  # Every node logs a timestamped entry
    messages: Annotated[list, add_messages]   # Full LLM conversation history
```

### Why `Annotated[list, append]`?

Normally, if two nodes both write to `timeline`, the second one overwrites the first. Using `Annotated[list, append]` with a custom reducer means LangGraph **merges all timeline entries** instead of replacing them. The same pattern applies to `messages` using LangGraph's built-in `add_messages` reducer.

---

## 6. Complete Application Flow

### End-to-End Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                     INCIDENT RESPONSE AGENT                          │
│                                                                      │
│  External Alert                                                      │
│  (PagerDuty / Datadog / curl)                                        │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────┐                                                     │
│  │  FastAPI    │  POST /webhook/alert                                │
│  │  Webhook    │  → builds IncidentState                             │
│  └──────┬──────┘  → streams graph events                            │
│         │                                                            │
│         ▼                                                            │
│  ┌─────────────────┐                                                 │
│  │ severity_       │  GPT-4o-mini → P1/P2/P3/P4                     │
│  │ classifier      │  incident_type, affected_systems                │
│  └────────┬────────┘                                                 │
│           │                                                          │
│    ┌──────┴──────┐                                                   │
│    │  Conditional │  P1/P2 → full pipeline                           │
│    │  Edge        │  P3/P4 → low_severity_handler                   │
│    └──────┬──────┘                                                   │
│           │ (P1/P2 path)                                             │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │  pii_redactor   │  Regex scrub: email, phone, SSN, IP, card      │
│  └────────┬────────┘                                                 │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────────────────────────────────────────┐            │
│  │  investigation_supervisor  (GPT-4o)                 │            │
│  │  Decides which workers to dispatch                  │            │
│  └───┬────────────────────────────────────────────┬───┘            │
│      │  Send API (parallel fan-out)                │                │
│      ▼                                             ▼                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │  logs_   │  │ metrics_ │  │ database_│  │ network_ │           │
│  │  worker  │  │  worker  │  │  worker  │  │  worker  │           │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│       └──────────────┴──────────────┴──────────────┘               │
│                              │ (merge into state)                   │
│                              ▼                                      │
│  ┌─────────────────┐                                                │
│  │ root_cause_     │  GPT-4o → root_cause + confidence             │
│  │ analysis        │                                                │
│  └────────┬────────┘                                                │
│           │                                                          │
│    ┌──────┴──────┐                                                   │
│    │  Confidence  │  > 0.7 → proceed                                │
│    │  Router      │  ≤ 0.7 → re-investigate (max 2 rounds)          │
│    └──────┬──────┘                                                   │
│           │ (confident)                                              │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │  communication_ │  GPT-4o-mini → drafts Slack message            │
│  │  hub            │  → sends Block Kit message with buttons         │
│  └────────┬────────┘  → creates Jira ticket stub                   │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐  ◄── GRAPH PAUSES HERE (SQLite checkpoint)     │
│  │  hitl_review    │                                                 │
│  │  (interrupt)    │  Waiting for Slack button click...             │
│  └────────┬────────┘                                                 │
│           │ (Slack Socket Mode callback resumes graph)              │
│    ┌──────┴──────┐                                                   │
│    │  HITL Router │  approved → resolution_engine                   │
│    └──────┬──────┘  rejected → escalation_handler                  │
│           │                                                          │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │ resolution_     │  Applies remediation steps                     │
│  │ engine          │                                                 │
│  └────────┬────────┘                                                 │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │ postmortem_     │  GPT-4o → blameless postmortem doc             │
│  │ writer          │  timeline_summary, action_items, lessons       │
│  └────────┬────────┘                                                 │
│           ▼                                                          │
│  ┌─────────────────┐                                                 │
│  │  END            │  Incident resolved ✓                           │
│  └─────────────────┘                                                 │
└──────────────────────────────────────────────────────────────────────┘
```

### What Happens During a P3/P4 Incident?

P3/P4 incidents follow a lightweight path: `severity_classifier` → `low_severity_handler` → `communication_hub` (abbreviated) → `END`. No HITL, no parallel investigation, no postmortem. This keeps noise low for minor alerts.

---

## 7. LangGraph Pipeline — Node by Node

The StateGraph is defined in `graph/graph.py`. It has 16 nodes total — 5 with real LLM calls (Phase 2) and 11 stubs (ready for Phase 4 real implementations).

### Node 1: `severity_classifier`
**File:** `nodes/severity_classifier.py`  
**Model:** GPT-4o-mini (fast, cheap, great at classification)  
**Input:** `alert`, `source`, `service`, `environment`  
**Output:** `severity`, `incident_type`, `affected_systems`, `classification_confidence`

This is the entry node. Every incident starts here. GPT-4o-mini receives the raw alert text and classifies it using a structured output schema:

```python
class SeverityOutput(BaseModel):
    severity: str              # "P1", "P2", "P3", "P4"
    incident_type: str         # "database", "network", "application", etc.
    affected_systems: list[str]
    classification_confidence: float
    reasoning: str
```

**Why GPT-4o-mini here?** Classification is fast and deterministic. We don't need GPT-4o's reasoning depth. Using 4o-mini keeps cost down for every incoming alert.

---

### Node 2: `pii_redactor`
**File:** `security/pii_redactor.py`  
**Model:** No LLM — pure Python regex  
**Input:** `alert` (raw text)  
**Output:** `alert` (redacted), `pii_detected`, `pii_types`, `redaction_summary`

This node runs **before any LLM call** on the investigation path. It scrubs:
- Email addresses → `[EMAIL]`
- Phone numbers → `[PHONE]`
- IP addresses → `[IP]`
- Credit card numbers → `[CARD]`
- Social Security Numbers → `[SSN]`

```python
PATTERNS = {
    "email": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    "phone": r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
    "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
}
```

**Why before LLM?** Once data reaches GPT, it enters OpenAI's infrastructure. PII redaction must happen in-process, before the first API call.

---

### Node 3: `investigation_supervisor`
**File:** `nodes/investigation_supervisor.py`  
**Model:** GPT-4o (complex multi-step reasoning)  
**Input:** `severity`, `incident_type`, `affected_systems`, `alert`  
**Output:** Dispatches workers via LangGraph `Send` API

This is the multi-agent supervisor. It decides which of the four workers to invoke and returns a list of `Send` commands:

```python
from langgraph.types import Send

def route_to_workers(state: IncidentState) -> list[Send]:
    workers = state["workers_dispatched"]
    return [Send(worker, state) for worker in workers]
```

GPT-4o reasons about the incident type and decides, for example, that a database timeout incident warrants `database_worker` and `metrics_worker`, but probably not `network_worker`.

**Why GPT-4o here?** The supervisor's reasoning determines the entire investigation strategy. This is where accuracy matters most.

---

### Node 4: `root_cause_analysis` (The Loop Node)
**File:** `nodes/root_cause_analysis.py`  
**Model:** GPT-4o  
**Input:** All four worker findings, `investigation_rounds`  
**Output:** `root_cause`, `confidence`, `confidence_reason`, incremented `investigation_rounds`

This node synthesizes findings from all workers into a single root cause explanation with a confidence score:

```python
class RootCauseOutput(BaseModel):
    root_cause: str              # Clear one-paragraph explanation
    confidence: float            # 0.0–1.0
    confidence_reason: str       # Why this score was assigned
```

**The confidence loop:**
```
root_cause_analysis
        │
   confidence > 0.7?
        │
   YES ─┤─── NO (and rounds < 2) ──► re-dispatch workers ──► root_cause_analysis (again)
        │
        └── YES ──► proceed to communication_hub
```

**Loop guard:** `investigation_rounds >= 2` forces exit even with low confidence. This prevents infinite loops if the evidence is genuinely ambiguous.

---

### Node 5: `hitl_review`
**File:** `nodes/stubs.py` (the HITL node is a pass-through; logic is in HITL interrupt mechanism)  
**How it works:** `interrupt_before=["hitl_review"]` tells LangGraph to pause BEFORE entering this node. The graph checkpoints itself to SQLite and returns control to the caller.

When a human clicks Approve or Reject in Slack:
```python
# In slack_socket.py:
agent_graph.update_state(
    config,
    {"human_approved": True, "human_feedback": "approved"},
    as_node="hitl_review"
)
# Resume the graph:
list(agent_graph.stream(None, config=config))
```

---

### Node 6: `postmortem_writer`
**File:** `nodes/postmortem_writer.py`  
**Model:** GPT-4o  
**Input:** Full incident state — root_cause, timeline, remediation_steps, affected_systems  
**Output:** `postmortem_url`, formatted postmortem as a `messages` entry

The postmortem follows a standard blameless format:

```python
class PostmortemOutput(BaseModel):
    title: str
    summary: str
    root_cause: str
    timeline_summary: str
    contributing_factors: list[str]
    action_items: list[str]
    lessons_learned: str
```

The full postmortem is serialized to markdown and stored in `state["messages"]` for retrieval.

---

### Node 7: `communication_hub`
**File:** `nodes/communication_hub.py`  
**Model:** GPT-4o-mini  
**Input:** `severity`, `incident_type`, `root_cause`, `affected_systems`, `slack_thread_id`  
**Output:** Sends Slack Block Kit message, stubs Jira ticket

This node has two responsibilities:
1. **Draft** a professional Slack status update using GPT-4o-mini
2. **Send** it via `integrations/slack.py` using the Slack WebClient

The initial notification (with HITL buttons) is also sent from here, before the graph pauses.

---

### Worker Nodes (Parallel, Phase 4 Real Implementations)

| Node | File | Purpose (stub → real) |
|---|---|---|
| `logs_worker` | `nodes/stubs.py` | Query Elasticsearch / CloudWatch Logs |
| `metrics_worker` | `nodes/stubs.py` | Query Datadog / Prometheus |
| `database_worker` | `nodes/stubs.py` | Query pg_stat_activity, slow query log |
| `network_worker` | `nodes/stubs.py` | Check VPC flow logs, DNS, latency |
| `resolution_engine` | `nodes/stubs.py` | Trigger runbooks, restart services |
| `escalation_handler` | `nodes/stubs.py` | PagerDuty escalation, on-call wake |
| `low_severity_handler` | `nodes/stubs.py` | Lightweight triage for P3/P4 |
| `knowledge_base_search` | `nodes/stubs.py` | RAG lookup of past incidents |
| `remediation_validator` | `nodes/stubs.py` | Check fix actually worked |
| `metrics_collector` | `nodes/stubs.py` | Collect post-resolution SLO data |
| `notification_manager` | `nodes/stubs.py` | Pagerduty, email, status page update |

---

## 8. Production Modules

### 8.1 PII Redaction

**File:** `security/pii_redactor.py`

**Current implementation:** Regex-based, zero external dependencies.

**How to use it:**

```python
from security.pii_redactor import redact_pii

result = redact_pii("User john@example.com reported error from 192.168.1.1")
# result["redacted_text"] → "User [EMAIL] reported error from [IP]"
# result["pii_detected"] → True
# result["pii_types"] → ["email", "ip_address"]
```

**Phase 4 upgrade:** Replace regex with [Microsoft Presidio](https://github.com/microsoft/presidio) for ML-powered NER detection (catches "John Smith at Acme Corp" as PII even without email format).

---

### 8.2 Human-in-the-Loop (HITL)

HITL is the most architecturally important feature. Here is exactly how it works:

**Step 1:** Graph is built with `interrupt_before`:
```python
from langgraph.checkpoint.sqlite import SqliteSaver

memory = SqliteSaver.from_conn_string("data/incidents.db")

agent_graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["hitl_review"]
)
```

**Step 2:** When the graph reaches `hitl_review`, it saves state to SQLite and returns control.

**Step 3:** FastAPI returns `{"status": "awaiting_approval"}` to the caller.

**Step 4:** Slack button click triggers Socket Mode callback in `slack_socket.py`.

**Step 5:** The callback loads the checkpoint and injects the human decision:
```python
config = {"configurable": {"thread_id": incident_id}}
agent_graph.update_state(config, {"human_approved": True}, as_node="hitl_review")
list(agent_graph.stream(None, config=config))  # Resume
```

**Why `thread_id`?** SQLiteSaver uses `thread_id` as the key for checkpoint lookup. By using `incident_id` as `thread_id`, we can always reload the exact graph state for any incident.

---

### 8.3 Loop Guards

The confidence loop has two exit conditions:

```python
def route_after_root_cause(state: IncidentState) -> str:
    if state["confidence"] > 0.7:
        return "communication_hub"       # Exit: confident
    elif state["investigation_rounds"] >= 2:
        return "communication_hub"       # Exit: max rounds hit
    else:
        return "investigation_supervisor" # Loop: re-investigate
```

**Why both conditions?** Without the rounds guard, a truly ambiguous incident (broken monitoring, sparse logs) could loop forever. The guard ensures the agent always makes progress, even with incomplete information.

---

### 8.4 SQLite Persistence & Checkpointing

**File:** `data/incidents.db` (auto-created)

LangGraph's `SqliteSaver` stores a checkpoint after every node execution. This provides:

- **HITL resume** — graph state survives across HTTP requests
- **Auditability** — full node-by-node state history queryable from SQLite
- **Crash recovery** — if the server restarts mid-incident, state is preserved

**Retrieve past incident state:**
```python
config = {"configurable": {"thread_id": "INC-A3F2B1C4"}}
state = agent_graph.get_state(config)
print(state.values["root_cause"])
print(state.values["timeline"])
```

**Phase 4 upgrade:** Replace SQLiteSaver with `PostgresSaver` for multi-instance deployments.

---

### 8.5 Slack Integration

**Files:** `integrations/slack.py` and `integrations/slack_socket.py`

#### Sending Messages (`slack.py`)

```python
from slack_sdk import WebClient
import ssl, certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"], ssl=ssl_context)
```

> **Note:** The `certifi` SSL fix is required on macOS Python installations from python.org. The system Python does not include root CA certificates.

**Block Kit message structure:**
```
┌────────────────────────────────────────────┐
│ 🔴  P1 Incident — INC-A3F2B1C4            │
├────────────────────────────────────────────┤
│ Type:     database                         │
│ Affected: api-gateway, postgres-primary    │
│ Jira:     INC-A3F2B1C                     │
│ Status:   🔴 P1 — Awaiting Approval       │
├────────────────────────────────────────────┤
│ Alert:                                     │
│ Database connection pool exhausted. Lat... │
├────────────────────────────────────────────┤
│  [✅ Approve Incident]  [❌ Reject]        │
└────────────────────────────────────────────┘
```

#### Receiving Button Clicks (`slack_socket.py`)

Slack Bolt with Socket Mode eliminates the need for a public webhook URL during development:

```python
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

app = App(token=os.environ["SLACK_BOT_TOKEN"])

@app.action("approve_incident")
def handle_approve(ack, body, client):
    ack()  # Must acknowledge within 3 seconds
    incident_id = body["actions"][0]["value"]
    # Resume LangGraph...
```

Socket Mode uses a persistent WebSocket connection. The `start_socket_listener()` function runs in a daemon thread, started via FastAPI's lifespan context manager.

---

### 8.6 FastAPI Webhook Layer

**File:** `api/app.py`

```python
# CRITICAL: load_dotenv() must be the FIRST two lines
# before any import that triggers ChatOpenAI initialization
from dotenv import load_dotenv
load_dotenv()
```

**Why first?** `slack_socket.py` imports `graph.graph` at module level. `graph.graph` constructs `ChatOpenAI()`, which reads `OPENAI_API_KEY` immediately. If `load_dotenv()` hasn't run yet, the key is `None` and the import fails.

**Lifespan context manager:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(target=start_socket_listener, daemon=True)
    thread.start()
    yield  # App runs here

app = FastAPI(lifespan=lifespan)  # Pass function reference, not string
```

**Common mistake:** `FastAPI(lifespan="lifespan")` passes the string name. The correct form passes the function reference.

---

### 8.7 Structured LLM Output (Pydantic)

Every LLM node uses `with_structured_output()` to guarantee the model returns exactly the fields we expect, as Python types:

```python
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

class SeverityOutput(BaseModel):
    severity: str = Field(description="P1, P2, P3, or P4")
    incident_type: str = Field(description="One of: database, network, application, security, infrastructure")
    affected_systems: list[str] = Field(description="List of affected service names")
    classification_confidence: float = Field(description="0.0 to 1.0")

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured_llm = llm.with_structured_output(SeverityOutput)

result: SeverityOutput = structured_llm.invoke(prompt)
# result.severity → "P1" (guaranteed, not "The severity is P1")
```

`temperature=0` is used on all classification and analysis nodes for deterministic, reproducible outputs.

---

### 8.8 Confidence-Driven Routing

The confidence score from `root_cause_analysis` drives the most important routing decision in the pipeline. Here is how it was calibrated:

| Scenario | Confidence | Outcome |
|---|---|---|
| Workers returned rich findings | 0.80–0.95 | Exits loop on round 1 |
| Workers returned partial data | 0.65–0.70 | Re-investigates on round 2 |
| Workers are stubs (no data) | 0.60–0.65 | Loop guard forces exit after 2 rounds |

The confidence score is not just a number — it represents GPT-4o's epistemic uncertainty. The model is explicitly prompted to be conservative: "Only score above 0.7 if the evidence clearly supports the root cause."

---

## 9. API Reference

### `POST /webhook/alert`

Receives an incoming alert and starts the incident response pipeline.

**Request:**
```json
{
  "source": "pagerduty",
  "message": "Database connection pool exhausted. Latency spike to 8000ms on postgres-primary.",
  "service": "api-gateway",
  "environment": "production"
}
```

**Response (P1/P2 — graph pauses at HITL):**
```json
{
  "incident_id": "INC-A3F2B1C4",
  "severity": "P1",
  "status": "awaiting_approval",
  "jira_ticket": "INC-A3F2B1C",
  "slack_thread": "1702394832.123456",
  "message": "Graph paused at HITL — approve via Slack"
}
```

**Response (P3/P4 — resolved immediately):**
```json
{
  "incident_id": "INC-B7D4E2F1",
  "severity": "P4",
  "status": "resolved",
  "jira_ticket": "INC-B7D4E2F",
  "slack_thread": "1702394901.654321",
  "message": "Incident resolved"
}
```

**Testing with curl:**
```bash
curl -X POST http://localhost:8000/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "source": "datadog",
    "message": "CPU usage 98% on prod-api-server-1 for 5 minutes. OOM killer triggered.",
    "service": "api-server",
    "environment": "production"
  }'
```

---

### `POST /webhook/slack`

Receives Slack interactive payload when a user clicks Approve or Reject.

> **Note:** In development, button callbacks are handled via Socket Mode (no public URL needed). This endpoint is for production deployments using Slack's HTTP Events API.

**Request:** Standard Slack interactive payload (URL-encoded form with `payload` JSON field)

**Behavior:**
1. Parses `incident_id` from button action value
2. Calls `agent_graph.update_state()` with `human_approved: True/False`
3. Resumes graph with `agent_graph.stream(None, config=config)`
4. Updates Slack message to show decision

---

### `GET /health`

Simple health check for load balancers and monitoring.

**Response:**
```json
{
  "status": "healthy",
  "service": "incident-response-agent"
}
```

---

### Interactive API Docs

FastAPI auto-generates documentation at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 10. Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```bash
# OpenAI
OPENAI_API_KEY=sk-...            # Your OpenAI API key

# Slack Bot
SLACK_BOT_TOKEN=xoxb-...        # Bot OAuth token (from OAuth & Permissions)
SLACK_APP_TOKEN=xapp-...        # App-level token (for Socket Mode)
SLACK_CHANNEL_ID=C0XXXXXXXXX    # Channel ID for incident notifications

# Optional: Jira Integration (Phase 4)
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=your.email@company.com
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=INC

# Optional: Database (Phase 4)
POSTGRES_DSN=postgresql://user:pass@localhost:5432/incidents
```

### How to get Slack credentials

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → Create New App → From Scratch
2. **Bot Token:** OAuth & Permissions → Bot Token Scopes → Add `chat:write`, `chat:write.public` → Install to Workspace → copy `xoxb-...`
3. **App Token:** Basic Information → App-Level Tokens → Generate Token → scope: `connections:write` → copy `xapp-...`
4. **Enable Socket Mode:** Socket Mode → Enable Socket Mode (toggle)
5. **Enable Interactivity:** Interactivity & Shortcuts → Enable → (URL can be placeholder for Socket Mode)
6. **Channel ID:** Right-click channel in Slack → View Channel Details → Copy Channel ID (`C0...`)

---

## 11. Setup & Running

### Prerequisites

- Python 3.11+
- OpenAI API key (GPT-4o access recommended)
- Slack workspace with admin access

### Installation

```bash
# Clone the project
git clone https://github.com/yourusername/incident-response-agent.git
cd incident-response-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate    # Mac/Linux
# venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Set up credentials
cp .env.example .env
# Edit .env with your API keys
```

### Running Locally

#### Option A: Direct graph test (no FastAPI, no Slack)

```bash
python main.py
```

This runs a hardcoded test incident through the full graph and prints results.

#### Option B: Full API server with Slack integration

```bash
uvicorn api.app:app --reload --port 8000
```

The server starts Slack Socket Mode in a background thread. Send a test alert:

```bash
curl -X POST http://localhost:8000/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "source": "pagerduty",
    "message": "Production database primary is not responding. Replica failover in progress.",
    "service": "postgres",
    "environment": "production"
  }'
```

Watch your Slack channel for the incident notification. Click ✅ Approve or ❌ Reject to resume the graph.

---

## 12. Testing Each Phase

### Phase 1: Stubs (All 16 nodes run, no LLM)

```bash
# Run main.py with all real nodes commented out and stubs only
python main.py
# Expected: Graph completes with placeholder values in all state fields
```

### Phase 2: Real LLM Nodes

Test each node individually before wiring into the full graph:

```bash
# Test severity classifier
python -c "
from nodes.severity_classifier import severity_classifier
from state.schema import IncidentState

state = IncidentState(
    alert='Database CPU 100%, 500 errors/sec on postgres-primary',
    source='datadog', service='api', environment='production',
    # ... other required fields with defaults
)
result = severity_classifier(state)
print(result['severity'], result['classification_confidence'])
"
```

### Phase 3: Full API + Slack

1. Start server: `uvicorn api.app:app --reload`
2. Send alert via curl (see Section 9)
3. Check Slack for notification message
4. Click ✅ Approve — graph should resume and log resolution
5. Check `/health` endpoint: `curl http://localhost:8000/health`

### Confidence Loop Test

Send an alert with minimal information to trigger low confidence:

```bash
curl -X POST http://localhost:8000/webhook/alert \
  -H "Content-Type: application/json" \
  -d '{
    "source": "monitoring",
    "message": "Something went wrong",
    "service": "unknown",
    "environment": "production"
  }'
```

Watch logs for `investigation_rounds` incrementing from 0 → 1 → 2 (loop guard fires).

---

## 13. How to Extend

### Add a New Worker Node

1. Create `nodes/my_new_worker.py` with a function that reads from state and returns findings:

```python
def my_new_worker(state: IncidentState) -> dict:
    # Query your data source here
    return {
        "my_findings": "Found X in source Y",
        "timeline": [{"timestamp": now, "node": "my_new_worker", "summary": "..."}]
    }
```

2. Add a new field to `IncidentState` in `state/schema.py`:

```python
my_findings: str
```

3. Register the node in `graph/graph.py`:

```python
graph_builder.add_node("my_new_worker", my_new_worker)
```

4. Update `investigation_supervisor.py` to include `"my_new_worker"` as an option in its worker selection prompt.

---

### Add a Real Jira Integration

Replace the stub in `communication_hub.py`:

```python
import requests

def create_jira_ticket(incident_id, summary, description):
    response = requests.post(
        f"{os.environ['JIRA_URL']}/rest/api/3/issue",
        auth=(os.environ['JIRA_EMAIL'], os.environ['JIRA_API_TOKEN']),
        json={
            "fields": {
                "project": {"key": os.environ['JIRA_PROJECT_KEY']},
                "summary": summary,
                "description": {"type": "doc", "version": 1, "content": [...]},
                "issuetype": {"name": "Incident"}
            }
        }
    )
    return response.json()["key"]
```

---

### Upgrade PII Redaction to Presidio

```bash
pip install presidio-analyzer presidio-anonymizer
python -m spacy download en_core_web_lg
```

Replace regex patterns in `security/pii_redactor.py`:

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

def redact_pii(text: str) -> dict:
    results = analyzer.analyze(text=text, entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "IP_ADDRESS"], language="en")
    anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
    return {"redacted_text": anonymized.text, "pii_detected": bool(results), ...}
```

---

### Switch to PostgreSQL Checkpointer

```bash
pip install langgraph-checkpoint-postgres psycopg
```

```python
from langgraph.checkpoint.postgres import PostgresSaver

memory = PostgresSaver.from_conn_string(os.environ["POSTGRES_DSN"])
agent_graph = graph_builder.compile(checkpointer=memory, interrupt_before=["hitl_review"])
```

This enables multi-instance deployments where different FastAPI pods can all access the same incident state.

---

*Last updated: Phase 3 complete — FastAPI webhook + Slack HITL integration working.*
