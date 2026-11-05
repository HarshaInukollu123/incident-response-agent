"""
Slack Socket Mode handler for HITL button callbacks.
Listens for Approve/Reject button clicks and resumes the paused LangGraph checkpoint.
"""
import logging
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from graph.graph import agent_graph

logger = logging.getLogger(__name__)

app = App(token=os.environ["SLACK_BOT_TOKEN"])


@app.action("approve_incident")
def handle_approve(ack, body, client):
    """Resumes graph with human_approved=True when Approve is clicked."""
    ack()
    incident_id = body["actions"][0]["value"]
    logger.info(f"[slack_socket] ✅ Approved: {incident_id}")

    config = {"configurable": {"thread_id": incident_id}}

    agent_graph.update_state(
        config,
        {"human_approved": True, "human_feedback": "approved"},
        as_node="hitl_review"
    )

    list(agent_graph.stream(None, config=config))

    client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text=f"✅ Incident {incident_id} — Approved. Remediation in progress.",
        blocks=[{
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"✅ *Incident {incident_id} — Approved*\nRemediation is now in progress."}
        }]
    )


@app.action("reject_incident")
def handle_reject(ack, body, client):
    """Resumes graph with human_approved=False when Reject is clicked."""
    ack()
    incident_id = body["actions"][0]["value"]
    logger.info(f"[slack_socket] ❌ Rejected: {incident_id}")

    config = {"configurable": {"thread_id": incident_id}}

    agent_graph.update_state(
        config,
        {"human_approved": False, "human_feedback": "rejected"},
        as_node="hitl_review"
    )

    list(agent_graph.stream(None, config=config))

    client.chat_update(
        channel=body["channel"]["id"],
        ts=body["message"]["ts"],
        text=f"❌ Incident {incident_id} — Rejected. Escalated.",
        blocks=[{
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"❌ *Incident {incident_id} — Rejected*\nIncident has been escalated."}
        }]
    )


def start_socket_listener():
    """Starts the Socket Mode listener in a background thread."""
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()