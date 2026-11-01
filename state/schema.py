""" this file defines the schema for the shared state of the Incident Response Agent."""
from __future__ import annotations

import operator
from datetime import datetime
from typing import Annotated, Dict, List, Literal, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def append(existing: list, new: list) -> list:
    """Reducer: appends new items instead of overwriting."""
    return existing + new


class IncidentState(TypedDict):

    """
    Shared state for the Incident Response Agent.
    Passed between all nodes in the LangGraph StateGraph.
    """    
    # Alert ingestion
    incident_id: str
    alert_source: str
    raw_alert: str
    clean_alert: str

    # Classification
    severity: Literal["P1", "P2", "P3", "P4"]
    incident_type: str
    affected_systems: List[str]

    # Supervisor / worker routing
    active_workers: List[str]
    worker_priorities: Dict[str, float]

    # Worker results
    runbook_steps: List[str]
    recent_deploys: List[dict]
    metric_anomalies: List[dict]
    similar_incidents: List[dict]

    # Loop guard
    investigation_rounds: int

    # Root cause
    root_cause: str
    confidence: float
    confidence_reason: str

    # External IDs
    slack_thread_id: str
    jira_ticket_id: str
    pd_incident_id: str

    # Communication
    status_page_draft: str
    revision_count: int

    # HITL
    human_approved: bool
    human_feedback: Optional[str]

    # Escalation
    escalation_deadline: Optional[datetime]
    escalated: bool

    # Cost tracking
    llm_cost_usd: float
    token_usage: Dict[str, int]

    # Append-only (reducers)
    timeline: Annotated[List[dict], append]
    messages: Annotated[List, add_messages]

    # Lifecycle
    started_at: datetime
    resolved_at: Optional[datetime]
    postmortem_url: Optional[str]