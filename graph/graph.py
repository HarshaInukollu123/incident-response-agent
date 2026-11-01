"""
Incident Response Agent — LangGraph StateGraph

LangGraph concepts demonstrated:
  1. StateGraph with TypedDict schema
  2. Conditional edges (severity + confidence + HITL routing)
  3. Parallel execution via Send API (fan-out to workers)
  4. Human-in-the-Loop via interrupt_before
  5. Persistence via SQLiteSaver checkpointer
  6. Loop guards (investigation_rounds, revision_count)
"""

import logging
import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from nodes.severity_classifier import severity_classifier
from nodes.investigation_supervisor import investigation_supervisor
from nodes.root_cause_analysis import root_cause_analysis
from nodes.postmortem_writer import postmortem_writer
from nodes.communication_hub import communication_hub
from nodes.stubs import (
    alert_parser,
    deeper_investigation,
    deploy_worker,
    escalation_node,
    history_worker,
    hitl_review,
    incident_closed,
    metrics_worker,
    remediation_executor,
    runbook_worker,
    status_page_updater,
)
from state.schema import IncidentState

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.7
MAX_INVESTIGATION_ROUNDS = 2
MAX_REVISION_COUNT = 3
DB_PATH = os.getenv("SQLITE_DB_PATH", "./incident_agent.db")


# ── Conditional edge functions ─────────────────────────────────────────────────

def route_by_severity(state: IncidentState) -> str:
    """P1/P2 → communication_hub first. P3/P4 → investigate first."""
    severity = state.get("severity", "P3")
    if severity in ("P1", "P2"):
        return "communication_hub"
    return "investigation_supervisor"


def fan_out_workers(state: IncidentState):
    """
    Send API: returns a list of Send objects.
    LangGraph runs each worker node in parallel.
    """
    workers = state.get("active_workers", [])
    node_map = {
        "runbook_worker": "runbook_worker",
        "deploy_worker": "deploy_worker",
        "metrics_worker": "metrics_worker",
        "history_worker": "history_worker",
    }
    return [Send(node_map[w], state) for w in workers if w in node_map]


def route_by_confidence(state: IncidentState) -> str:
    """High confidence → HITL. Low confidence → deeper investigation."""
    confidence = state.get("confidence", 0.0)
    rounds = state.get("investigation_rounds", 0)

    if confidence >= CONFIDENCE_THRESHOLD:
        return "hitl_review"
    elif rounds >= MAX_INVESTIGATION_ROUNDS:
        return "hitl_review"   # forced after max rounds
    return "deeper_investigation"


def route_by_hitl(state: IncidentState) -> str:
    """Approved → fix it. Edit requested → redraft. Rejected → escalate."""
    approved = state.get("human_approved", False)
    feedback = state.get("human_feedback")
    revision_count = state.get("revision_count", 0)

    if approved:
        return "remediation_executor"
    elif feedback and revision_count < MAX_REVISION_COUNT:
        return "communication_hub"
    return "escalation_node"


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_graph():
    """Assembles and compiles the full StateGraph."""

    graph = StateGraph(IncidentState)

    # Register all nodes
    graph.add_node("alert_parser", alert_parser)
    graph.add_node("severity_classifier", severity_classifier)
    graph.add_node("communication_hub", communication_hub)
    graph.add_node("investigation_supervisor", investigation_supervisor)
    graph.add_node("runbook_worker", runbook_worker)
    graph.add_node("deploy_worker", deploy_worker)
    graph.add_node("metrics_worker", metrics_worker)
    graph.add_node("history_worker", history_worker)
    graph.add_node("root_cause_analysis", root_cause_analysis)
    graph.add_node("deeper_investigation", deeper_investigation)
    graph.add_node("hitl_review", hitl_review)
    graph.add_node("remediation_executor", remediation_executor)
    graph.add_node("status_page_updater", status_page_updater)
    graph.add_node("escalation_node", escalation_node)
    graph.add_node("postmortem_writer", postmortem_writer)
    graph.add_node("incident_closed", incident_closed)

    # Entry point
    graph.add_edge(START, "alert_parser")
    graph.add_edge("alert_parser", "severity_classifier")

    # Severity routing
    graph.add_conditional_edges(
        "severity_classifier",
        route_by_severity,
        {
            "communication_hub": "communication_hub",
            "investigation_supervisor": "investigation_supervisor",
        }
    )

    # P1/P2: open comms then investigate
    graph.add_edge("communication_hub", "investigation_supervisor")

    # Fan-out workers in parallel
    graph.add_conditional_edges(
        "investigation_supervisor",
        fan_out_workers,
        ["runbook_worker", "deploy_worker", "metrics_worker", "history_worker"]
    )

    # Fan-in: all workers → root cause
    graph.add_edge("runbook_worker", "root_cause_analysis")
    graph.add_edge("deploy_worker", "root_cause_analysis")
    graph.add_edge("metrics_worker", "root_cause_analysis")
    graph.add_edge("history_worker", "root_cause_analysis")

    # Confidence routing
    graph.add_conditional_edges(
        "root_cause_analysis",
        route_by_confidence,
        {
            "hitl_review": "hitl_review",
            "deeper_investigation": "deeper_investigation",
        }
    )

    # Loop: deeper investigation goes back to supervisor
    graph.add_edge("deeper_investigation", "investigation_supervisor")

    # HITL routing
    graph.add_conditional_edges(
        "hitl_review",
        route_by_hitl,
        {
            "remediation_executor": "remediation_executor",
            "communication_hub": "communication_hub",
            "escalation_node": "escalation_node",
        }
    )

    # Resolution path
    graph.add_edge("remediation_executor", "status_page_updater")
    graph.add_edge("status_page_updater", "postmortem_writer")
    graph.add_edge("postmortem_writer", "incident_closed")
    graph.add_edge("incident_closed", END)

    # Escalation path
    graph.add_edge("escalation_node", "postmortem_writer")

    # Compile with SQLiteSaver + HITL interrupt
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_review"],
    )


agent_graph = build_graph()