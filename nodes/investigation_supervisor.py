"""
investigation_supervisor — decides which workers to activate.

LangGraph concepts:
  - Supervisor pattern (multi-agent coordination)
  - GPT-4o with structured output
  - State-driven routing decisions
"""

import logging
from typing import Dict, List

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from state.schema import IncidentState

logger = logging.getLogger(__name__)


# ── Pydantic output schema ─────────────────────────────────────────────────────

class SupervisorOutput(BaseModel):
    """Which workers to activate and why."""

    active_workers: List[str] = Field(
        description=(
            "Workers to activate. Choose from: "
            "runbook_worker, deploy_worker, metrics_worker, history_worker"
        )
    )
    worker_priorities: Dict[str, float] = Field(
        description="Priority score 0.0-1.0 for each active worker"
    )
    reasoning: str = Field(
        description="Why these workers were selected"
    )


# ── LLM setup ─────────────────────────────────────────────────────────────────

llm = ChatOpenAI(model="gpt-4o", temperature=0)
structured_llm = llm.with_structured_output(SupervisorOutput)


# ── Node function ──────────────────────────────────────────────────────────────

def investigation_supervisor(state: IncidentState) -> dict:
    """Uses GPT-4o to decide which workers are relevant for this incident."""

    logger.info(f"[investigation_supervisor] Deciding workers for {state['incident_id']}")

    prompt = f"""You are an SRE investigation supervisor.

Incident Details:
- Severity: {state['severity']}
- Type: {state['incident_type']}
- Affected Systems: {state['affected_systems']}
- Alert: {state['clean_alert']}

Available workers:
- runbook_worker    : searches runbooks for remediation steps (always useful)
- deploy_worker     : checks recent GitHub deployments (useful if deploy may have caused this)
- metrics_worker    : fetches Prometheus anomalies (useful for performance/resource issues)
- history_worker    : searches past postmortems for similar incidents (always useful)

Decide which workers to activate. You do NOT need to activate all of them.
Assign each a priority score from 0.0 to 1.0.
"""

    result: SupervisorOutput = structured_llm.invoke(prompt)

    logger.info(f"[investigation_supervisor] Activating: {result.active_workers}")
    logger.info(f"[investigation_supervisor] Reasoning: {result.reasoning}")

    return {
        "active_workers": result.active_workers,
        "worker_priorities": result.worker_priorities,
        "timeline": [{
            "timestamp": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
            "node": "investigation_supervisor",
            "summary": f"Activated workers: {result.active_workers} — {result.reasoning}"
        }]
    }