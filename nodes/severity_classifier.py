"""
severity_classifier — first real LLM call in the agent.

LangGraph concepts:
  - Pydantic structured output (LLM returns validated schema, not raw text)
  - Cost tracking (tokens logged to state)
  - GPT-4o-mini (cheaper model for classification tasks)
"""

import logging
from typing import List, Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from state.schema import IncidentState

logger = logging.getLogger(__name__)


# ── Pydantic output schema ─────────────────────────────────────────────────────
# This is what the LLM MUST return — no free text, no hallucinated fields

class SeverityOutput(BaseModel):
    """Structured output for severity classification."""

    severity: Literal["P1", "P2", "P3", "P4"] = Field(
        description="P1=critical/down, P2=degraded, P3=minor, P4=informational"
    )
    incident_type: Literal["database", "api", "infra", "auth", "network", "unknown"] = Field(
        description="Primary category of the incident"
    )
    affected_systems: List[str] = Field(
        description="List of service or system names affected"
    )
    reasoning: str = Field(
        description="One sentence explaining the severity decision"
    )


# ── LLM setup ─────────────────────────────────────────────────────────────────
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured_llm = llm.with_structured_output(SeverityOutput)


# ── Node function ──────────────────────────────────────────────────────────────
def severity_classifier(state: IncidentState) -> dict:
    """Classifies incident severity using GPT-4o-mini with structured output."""

    logger.info(f"[severity_classifier] Classifying incident {state['incident_id']}")

    prompt = f"""You are an SRE incident classifier at a fintech company.

Analyze this alert and classify it:

ALERT:
{state['clean_alert']}

Rules:
- P1 = complete outage, data loss risk, payments down
- P2 = significant degradation, multiple users affected  
- P3 = minor issue, workaround available
- P4 = informational, no user impact
"""

    # LLM call — returns a SeverityOutput object, not raw text
    result: SeverityOutput = structured_llm.invoke(prompt)

    logger.info(f"[severity_classifier] → {result.severity} | {result.incident_type} | {result.reasoning}")

    return {
        "severity": result.severity,
        "incident_type": result.incident_type,
        "affected_systems": result.affected_systems,
        "timeline": [{
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "node": "severity_classifier",
            "summary": f"Classified as {result.severity} - {result.incident_type}: {result.reasoning}"
        }]
    }