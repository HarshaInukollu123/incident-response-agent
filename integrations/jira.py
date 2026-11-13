"""
Jira REST API integration.
Creates incident tickets using the Jira REST API v3.
Authentication uses Basic Auth: email + API token (base64 encoded).
"""

import os
import requests
from requests.auth import HTTPBasicAuth
import logging
logger = logging.getLogger(__name__)

JIRA_URL = os.environ["JIRA_URL"]
JIRA_EMAIL = os.environ["JIRA_EMAIL"]
JIRA_API_TOKEN = os.environ["JIRA_API_TOKEN"]
JIRA_PROJECT_KEY = os.environ["JIRA_PROJECT_KEY"]

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}


def create_jira_ticket(
    incident_id: str,
    severity: str,
    incident_type: str,
    affected_systems: list[str],
    summary: str,
) -> str:
    """
    Creates a Jira issue for the incident.
    Returns the ticket key e.g. 'KAN-5'.
    Description uses Atlassian Document Format (ADF) — required by API v3.
    """
    affected = ", ".join(affected_systems)

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": f"[{severity}] {incident_id} — {summary}",
            "issuetype": {"name": "Task"},
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"Incident ID: {incident_id}\n"
                                    f"Severity: {severity}\n"
                                    f"Type: {incident_type}\n"
                                    f"Affected Systems: {affected}"
                                ),
                            }
                        ],
                    }
                ],
            },
        }
    }

    response = requests.post(
        f"{JIRA_URL}/rest/api/3/issue",
        json=payload,
        headers=headers,
        auth=auth,
    )
    response.raise_for_status()
    return response.json()["key"]   # e.g. "KAN-5"

def update_jira_status(ticket_key: str, target_status: str) -> bool:
    """
    Moves a Jira ticket to a new status using transition IDs.
    target_status should match the Jira column name e.g. 'In Progress', 'Done'.
    Returns True if successful, False if transition not found.
    """
    # Step 1: Get available transitions for this ticket
    r = requests.get(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_key}/transitions",
        headers=headers,
        auth=auth,
    )
    r.raise_for_status()
    transitions = r.json().get("transitions", [])

    # Step 2: Find the transition that matches target_status
    transition_id = None
    for t in transitions:
        if t["to"]["name"].lower() == target_status.lower():
            transition_id = t["id"]
            break

    if not transition_id:
        logger.warning(f"[jira] Transition '{target_status}' not found for {ticket_key}")
        logger.warning(f"[jira] Available: {[t['to']['name'] for t in transitions]}")
        return False

    # Step 3: Apply the transition
    r = requests.post(
        f"{JIRA_URL}/rest/api/3/issue/{ticket_key}/transitions",
        headers=headers,
        auth=auth,
        json={"transition": {"id": transition_id}},
    )
    r.raise_for_status()
    logger.info(f"[jira] {ticket_key} moved to '{target_status}'")
    return True