"""
main.py — Entry point for the Incident Response Agent.

Run with:
    python main.py

What this does:
  1. Fires a mock alert through the graph
  2. Graph runs until it hits hitl_review (pauses)
  3. Simulates a human clicking Approve in Slack
  4. Graph resumes and runs to completion
  5. Prints the final state and full timeline
"""
from dotenv import load_dotenv
load_dotenv()
import logging
import os
import uuid
from datetime import datetime, timezone
from graph.graph import agent_graph



logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)



def run_mock_incident():
    """Fire a mock incident through the agent graph."""

    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

    # ── Initial state ──────────────────────────────────────────────────────────
    initial_state = {
        "incident_id": incident_id,
        "alert_source": "prometheus",
        "raw_alert": (
            "ALERT: High database connection pool usage on payments-api. "
            "Current: 498/500 connections. "
            "Customer john.doe@bank.com reported transaction failures. "
            "Service: payments-api | Region: us-east-1 | Severity: critical"
        ),
        "clean_alert": "",
        "severity": "P1",
        "incident_type": "",
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

    # thread_id = incident_id means each incident has its own checkpointed state
    config = {"configurable": {"thread_id": incident_id}}

    print("\n" + "="*60)
    print(f"  INCIDENT: {incident_id}")
    print("="*60 + "\n")

    # ── Phase 1: Run until HITL pause ─────────────────────────────────────────
    print("  Running graph...\n")
    for event in agent_graph.stream(initial_state, config):
        for node_name, node_output in event.items():
            if node_name == "__end__" or not isinstance(node_output, dict):
                continue
            for t in node_output.get("timeline", []):
                print(f"  ✓ {t['node']}")

    # ── Check if graph paused at HITL ─────────────────────────────────────────
    current_state = agent_graph.get_state(config)

    if "hitl_review" in current_state.next:
        print("\n  ⏸  Paused at hitl_review")
        print("  [Simulating Slack ✅ Approve click...]\n")

        # Simulate human approval
        # In production: FastAPI receives Slack button click and calls this
        agent_graph.update_state(
            config,
            {
                "human_approved": True,
                "human_feedback": None,
                "status_page_draft": (
                    "We are investigating elevated database connection "
                    "errors on payments-api. Updates every 15 minutes."
                ),
            },
            as_node="hitl_review",
        )

        # ── Resume graph after HITL ────────────────────────────────────────────
        for event in agent_graph.stream(None, config):
            for node_name, node_output in event.items():
                if node_name == "__end__" or not isinstance(node_output, dict):
                    continue
                for t in node_output.get("timeline", []):
                    print(f"  ✓ {t['node']}")

    # ── Final state ────────────────────────────────────────────────────────────
    final = agent_graph.get_state(config).values

    print("\n" + "="*60)
    print("  INCIDENT RESOLVED")
    print("="*60)
    print(f"  Severity   : {final.get('severity')}")
    print(f"  Root Cause : {final.get('root_cause')}")
    print(f"  Confidence : {final.get('confidence')}")
    print(f"  Jira       : {final.get('jira_ticket_id')}")
    print(f"  Postmortem : {final.get('postmortem_url')}")
    print(f"  Resolved   : {final.get('resolved_at')}")

    print("\n  TIMELINE:")
    for event in final.get("timeline", []):
        print(f"    {event['timestamp']} | {event['node']}")
    print()


if __name__ == "__main__":
    run_mock_incident()