"""
Communication hub node.
Drafts Slack incident notification and Jira ticket description using GPT-4o-mini.
Actual API calls to Slack and Jira are stubbed here — Phase 3 replaces them
with real integrations using webhooks and the Jira REST API.
"""
import logging
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from state.schema import IncidentState

logger = logging.getLogger(__name__)


class CommunicationOutput(BaseModel):
    """Structured output containing drafted Slack message and Jira ticket content."""
    slack_message: str = Field(description="Slack incident notification message, concise and actionable")
    jira_summary: str = Field(description="One-line Jira ticket title")
    jira_description: str = Field(description="Jira ticket body with incident details, impact, and next steps")


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
structured_llm = llm.with_structured_output(CommunicationOutput)


def communication_hub(state: IncidentState) -> dict:
    """
    Drafts Slack and Jira content using GPT-4o-mini based on severity and alert.
    Stubs the actual API calls — Phase 3 wires real Slack webhooks and Jira REST API.
    Returns slack_thread_id and jira_ticket_id (stubbed) plus drafted content in messages.
    """
    logger.info(f"[communication_hub] Drafting communications for {state['incident_id']} ({state['severity']})")

    prompt = f"""You are an SRE drafting incident communications.

Incident:
- ID: {state['incident_id']}
- Severity: {state['severity']}
- Type: {state['incident_type']}
- Affected Systems: {state['affected_systems']}
- Alert: {state['clean_alert']}

Draft:
1. A Slack message for the #incidents channel — clear, urgent for P1/P2, calm for P3/P4
2. A Jira ticket summary (one line)
3. A Jira ticket description with: what happened, impact, affected systems, initial steps

Keep Slack message under 200 characters. Be factual, not alarming."""

    result: CommunicationOutput = structured_llm.invoke(prompt)

    # --- STUB: Phase 3 replaces these with real API calls ---
    slack_thread_id = f"SLACK-STUB-{state['incident_id'][:8]}"
    jira_ticket_id = f"INC-STUB-{state['incident_id'][:8]}"
    # --------------------------------------------------------

    logger.info(f"[communication_hub] Slack drafted | Jira: {jira_ticket_id}")

    return {
        "slack_thread_id": slack_thread_id,
        "jira_ticket_id": jira_ticket_id,
        "timeline": [{
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node": "communication_hub",
            "summary": f"Drafted Slack + Jira for {state['severity']} incident. Jira: {jira_ticket_id}"
        }],
        "messages": [{
            "role": "assistant",
            "content": f"**Slack:** {result.slack_message}\n\n**Jira ({jira_ticket_id}):** {result.jira_summary}\n\n{result.jira_description}"
        }]
    }