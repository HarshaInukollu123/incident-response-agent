"""
Placeholder node implementations for Phase 1.

Each function:
  - Accepts IncidentState
  - Logs that it ran
  - Returns a minimal state update

These will be replaced with real LLM calls in Phase 2.
"""

import logging
from datetime import datetime, timezone

from state.schema import IncidentState
from security.pii_redactor import redact_pii

logger = logging.getLogger(__name__)


def _log(node_name: str, state: IncidentState) -> dict:
    """Helper: log the node fired and return a timeline event."""
    logger.info(f"[{node_name}] fired for incident {state.get('incident_id', 'unknown')}")
    return {
        "timeline": [{"timestamp": datetime.now(timezone.utc).isoformat(),
                       "node": node_name,
                       "summary": f"{node_name} executed (stub)"}]
    }


def alert_parser(state: IncidentState) -> dict:
    """Parses raw alert and redacts PII before any LLM sees it."""
    update = _log("alert_parser", state)

    raw = state.get("raw_alert", "")
    clean, found = redact_pii(raw)

    if found:
        logger.info(f"[alert_parser] Redacted PII types: {found}")

    update["clean_alert"] = clean
    return update


def severity_classifier(state: IncidentState) -> dict:
    """Classifies severity and incident type."""
    update = _log("severity_classifier", state)
    update["severity"] = "P2"
    update["incident_type"] = "database"
    update["affected_systems"] = ["payments-api"]
    update["escalation_deadline"] = None
    update["escalated"] = False
    return update


def communication_hub(state: IncidentState) -> dict:
    """Opens Slack thread and creates Jira + PagerDuty tickets."""
    update = _log("communication_hub", state)
    update["slack_thread_id"] = "STUB-THREAD-001"
    update["jira_ticket_id"] = "INC-STUB-001"
    update["pd_incident_id"] = "PD-STUB-001"
    return update


def investigation_supervisor(state: IncidentState) -> dict:
    """Decides which workers to activate based on incident_type."""
    update = _log("investigation_supervisor", state)
    update["active_workers"] = ["runbook_worker", "deploy_worker",
                                 "metrics_worker", "history_worker"]
    update["worker_priorities"] = {
        "runbook_worker": 0.9,
        "deploy_worker": 0.8,
        "metrics_worker": 0.7,
        "history_worker": 0.6,
    }
    return update


def runbook_worker(state: IncidentState) -> dict:
    """RAG search over runbooks for relevant steps."""
    update = _log("runbook_worker", state)
    update["runbook_steps"] = ["[STUB] Check DB connection pool",
                                "[STUB] Restart replica"]
    return update


def deploy_worker(state: IncidentState) -> dict:
    """Fetches recent deploys from GitHub."""
    update = _log("deploy_worker", state)
    update["recent_deploys"] = [{"sha": "abc123",
                                  "message": "[STUB] Deploy at 14:32"}]
    return update


def metrics_worker(state: IncidentState) -> dict:
    """Fetches anomalies from Prometheus."""
    update = _log("metrics_worker", state)
    update["metric_anomalies"] = [{"metric": "db_connections",
                                    "value": 498,
                                    "threshold": 100}]
    return update


def history_worker(state: IncidentState) -> dict:
    """RAG search over past postmortems for similar incidents."""
    update = _log("history_worker", state)
    update["similar_incidents"] = [{"id": "INC-2024-001",
                                     "summary": "[STUB] Similar DB spike"}]
    return update


def root_cause_analysis(state: IncidentState) -> dict:
    """Synthesizes all worker findings into a root cause."""
    update = _log("root_cause_analysis", state)
    update["root_cause"] = "[STUB] Connection pool exhaustion due to query lock"
    update["confidence"] = 0.85
    update["confidence_reason"] = "[STUB] High metric anomaly + matching runbook"
    update["investigation_rounds"] = state.get("investigation_rounds", 0) + 1
    return update


def deeper_investigation(state: IncidentState) -> dict:
    """Called when confidence < 0.7. Runs another investigation pass."""
    update = _log("deeper_investigation", state)
    update["confidence"] = 0.75
    return update


def hitl_review(state: IncidentState) -> dict:
    """Pauses graph for human approval via Slack Block Kit buttons."""
    update = _log("hitl_review", state)
    update["human_approved"] = True
    update["human_feedback"] = None
    update["revision_count"] = state.get("revision_count", 0)
    update["status_page_draft"] = "[STUB] Investigating database connectivity issue."
    return update


def remediation_executor(state: IncidentState) -> dict:
    """Executes approved remediation steps."""
    return _log("remediation_executor", state)


def status_page_updater(state: IncidentState) -> dict:
    """Posts approved status update to status page."""
    return _log("status_page_updater", state)


def escalation_node(state: IncidentState) -> dict:
    """Escalates incident if HITL rejected or timed out."""
    update = _log("escalation_node", state)
    update["escalated"] = True
    return update


def postmortem_writer(state: IncidentState) -> dict:
    """Writes postmortem to GitHub."""
    update = _log("postmortem_writer", state)
    update["postmortem_url"] = "https://github.com/stub/postmortem-001"
    update["resolved_at"] = datetime.now(timezone.utc)
    return update


def incident_closed(state: IncidentState) -> dict:
    """Marks the incident as fully resolved."""
    return _log("incident_closed", state)