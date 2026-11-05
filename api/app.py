"""
FastAPI application for the Incident Response Agent.
Exposes two endpoints:
  POST /webhook/alert  — receives incoming alerts from PagerDuty, Datadog, etc.
  POST /webhook/slack  — receives Slack interactive button callbacks (HITL approve/reject)
"""
from dotenv import load_dotenv

load_dotenv()

import logging
import uuid
import threading
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from contextlib import asynccontextmanager
from integrations.slack_socket import start_socket_listener


from graph.graph import agent_graph

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Slack Socket Mode listener on startup."""
    thread = threading.Thread(target=start_socket_listener, daemon=True)
    thread.start()
    logger.info("[app] Slack Socket Mode listener started")
    yield

app = FastAPI(
    title="Incident Response Agent",
    description="Autonomous incident response powered by LangGraph",
    version="1.0.0",
    lifespan=lifespan
)
# ── Request model for incoming alerts ────────────────────────────────────────

class AlertPayload(BaseModel):
    """Incoming alert payload from PagerDuty, Datadog, or any monitoring tool."""
    source: str
    message: str
    service: str = "unknown"
    environment: str = "production"


# ── POST /webhook/alert ───────────────────────────────────────────────────────

@app.post("/webhook/alert")
async def receive_alert(payload: AlertPayload):
    """
    Receives an alert and triggers the LangGraph incident response agent.
    Returns the incident_id immediately — the graph runs asynchronously.
    In production this would be a background task; here it runs synchronously
    so we can return the final state for testing.
    """
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"[webhook] Alert received → {incident_id} from {payload.source}")

    initial_state = {
        "incident_id": incident_id,
        "alert_source": payload.source,
        "raw_alert": payload.message,
        "clean_alert": "",
        "severity": "P3",
        "incident_type": "unknown",
        "affected_systems": [],
        "active_workers": [],
        "worker_priorities": {},
        "runbook_steps": [],
        "recent_deploys": [],
        "metric_anomalies": [],
        "similar_incidents": [],
        "investigation_rounds": 0,
        "root_cause": "",
        "confidence": 0.0,
        "confidence_reason": "",
        "slack_thread_id": "",
        "jira_ticket_id": "",
        "pd_incident_id": "",
        "status_page_draft": "",
        "revision_count": 0,
        "human_approved": False,
        "human_feedback": None,
        "escalation_deadline": None,
        "escalated": False,
        "llm_cost_usd": 0.0,
        "token_usage": {},
        "timeline": [],
        "messages": [],
        "started_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "postmortem_url": None,
    }

    config = {"configurable": {"thread_id": incident_id}}

    # Run graph until it hits hitl_review interrupt
    events = list(agent_graph.stream(initial_state, config=config))

    # Check if paused at HITL
    state = agent_graph.get_state(config)
    is_paused = bool(state.next)

    return {
        "incident_id": incident_id,
        "severity": state.values.get("severity"),
        "status": "awaiting_approval" if is_paused else "resolved",
        "jira_ticket": state.values.get("jira_ticket_id"),
        "slack_thread": state.values.get("slack_thread_id"),
        "message": "Graph paused at HITL — approve via Slack" if is_paused else "Incident resolved"
    }


# ── POST /webhook/slack ───────────────────────────────────────────────────────

@app.post("/webhook/slack")
async def slack_callback(request: Request):
    """
    Receives Slack interactive button callbacks (approve/reject).
    Resumes the paused LangGraph checkpoint using the incident_id as thread_id.
    In Phase 3 this will verify the Slack signing secret before processing.
    """
    form = await request.form()
    import json
    payload = json.loads(form.get("payload", "{}"))

    action = payload.get("actions", [{}])[0].get("action_id", "")
    incident_id = payload.get("actions", [{}])[0].get("value", "")

    if not incident_id:
        raise HTTPException(status_code=400, detail="Missing incident_id in callback")

    approved = action == "approve_incident"
    logger.info(f"[slack_callback] {'✅ Approved' if approved else '❌ Rejected'} → {incident_id}")

    config = {"configurable": {"thread_id": incident_id}}

    # Resume the paused graph with the human decision
    agent_graph.update_state(
        config,
        {"human_approved": approved, "human_feedback": action},
        as_node="hitl_review"
    )

    # Continue running the graph after HITL
    list(agent_graph.stream(None, config=config))

    return {"status": "ok", "incident_id": incident_id, "approved": approved}


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "incident-response-agent"}

