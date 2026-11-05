"""
Slack integration for the Incident Response Agent.
Sends incident notifications with Block Kit Approve/Reject buttons.
Uses Socket Mode — no public URL needed for local development.
"""
import logging
import os
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import ssl
import certifi

# Fix Mac SSL certificate issue
ssl_context = ssl.create_default_context(cafile=certifi.where())

client = WebClient(
    token=os.environ["SLACK_BOT_TOKEN"],
    ssl=ssl_context
)
logger = logging.getLogger(__name__)



def send_incident_notification(
    incident_id: str,
    severity: str,
    incident_type: str,
    affected_systems: list[str],
    alert: str,
    jira_ticket_id: str,
) -> str:
    """
    Sends a Slack Block Kit message with Approve and Reject buttons.
    Returns the Slack thread timestamp (ts) used as slack_thread_id in state.
    """
    channel = os.environ["SLACK_CHANNEL_ID"]

    severity_emoji = {"P1": "🔴", "P2": "🟠", "P3": "🟡", "P4": "🟢"}.get(severity, "⚪")

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{severity_emoji} {severity} Incident — {incident_id}"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Type:*\n{incident_type}"},
                {"type": "mrkdwn", "text": f"*Affected:*\n{', '.join(affected_systems)}"},
                {"type": "mrkdwn", "text": f"*Jira:*\n{jira_ticket_id}"},
                {"type": "mrkdwn", "text": f"*Status:*\nAwaiting Approval"},
            ]
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Alert:*\n{alert[:300]}"}
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve"},
                    "style": "primary",
                    "action_id": "approve_incident",
                    "value": incident_id
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "action_id": "reject_incident",
                    "value": incident_id
                }
            ]
        }
    ]

    try:
        response = client.chat_postMessage(
            channel=channel,
            text=f"{severity_emoji} {severity} Incident {incident_id} — Awaiting Approval",
            blocks=blocks
        )
        ts = response["ts"]
        logger.info(f"[slack] Message sent for {incident_id} | ts={ts}")
        return ts

    except SlackApiError as e:
        logger.error(f"[slack] Failed to send message: {e.response['error']}")
        raise


def update_incident_message(slack_thread_id: str, incident_id: str, approved: bool) -> None:
    """
    Updates the original Slack message after human decision — replaces buttons with result.
    """
    channel = os.environ["SLACK_CHANNEL_ID"]
    status = "✅ Approved — remediation in progress" if approved else "❌ Rejected — incident escalated"

    try:
        client.chat_update(
            channel=channel,
            ts=slack_thread_id,
            text=f"Incident {incident_id} — {status}",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Incident {incident_id}*\n{status}"}
                }
            ]
        )
        logger.info(f"[slack] Message updated for {incident_id} → {status}")
    except SlackApiError as e:
        logger.error(f"[slack] Failed to update message: {e.response['error']}")