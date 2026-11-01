"""
Root cause analysis node.
Synthesizes investigation data from all workers and produces a root cause
with a confidence score. Confidence >0.7 proceeds to resolution; ≤0.7
triggers another investigation round (max 2 rounds).
"""
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from state.schema import IncidentState

logger = logging.getLogger(__name__)


class RootCauseOutput(BaseModel):
    """Structured output for root cause analysis. Used with GPT-4o via with_structured_output."""
    root_cause: str = Field(description="Clear one-paragraph explanation of what caused this incident")
    confidence: float = Field(description="Confidence score 0.0 to 1.0. >0.7 means ready to proceed to resolution")
    confidence_reason: str = Field(description="One sentence explaining why this confidence score was assigned")


llm = ChatOpenAI(model="gpt-4o", temperature=0)
structured_llm = llm.with_structured_output(RootCauseOutput)


def root_cause_analysis(state: IncidentState) -> dict:
    """
    Reads all worker findings from state and calls GPT-4o to synthesize a root cause.
    Returns root_cause, confidence score, and increments investigation_rounds.
    Confidence drives the next edge: >0.7 → proceed, ≤0.7 → re-investigate.
    """
    logger.info(f"[root_cause_analysis] Analyzing root cause for {state['incident_id']} (round {state['investigation_rounds']})")

    prompt = f"""You are a senior SRE performing root cause analysis.

Incident Summary:
- ID: {state['incident_id']}
- Severity: {state['severity']}
- Type: {state['incident_type']}
- Affected Systems: {state['affected_systems']}
- Alert: {state['clean_alert']}

Investigation Data:
- Runbook Steps Found: {state.get('runbook_steps', [])}
- Recent Deploys: {state.get('recent_deploys', [])}
- Metric Anomalies: {state.get('metric_anomalies', [])}
- Similar Past Incidents: {state.get('similar_incidents', [])}
- Investigation Round: {state['investigation_rounds']} of 2

Based on all available data, determine the root cause.
Assign confidence >0.7 only if you have strong evidence.
If data is sparse, assign lower confidence so another investigation round runs."""

    result: RootCauseOutput = structured_llm.invoke(prompt)

    logger.info(f"[root_cause_analysis] Confidence: {result.confidence:.2f} | {result.confidence_reason}")

    return {
        "root_cause": result.root_cause,
        "confidence": result.confidence,
        "confidence_reason": result.confidence_reason,
        "investigation_rounds": state["investigation_rounds"] + 1,
        "timeline": [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "root_cause_analysis",
            "summary": f"Root cause identified (confidence: {result.confidence:.2f}): {result.root_cause[:100]}..."
        }]
    }