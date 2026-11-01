"""
PII Redactor — strips sensitive data before any LLM call.

Runs in alert_parser node as the first thing that happens
to every incoming alert.
"""

import re

# Patterns to detect and redact
PII_PATTERNS = {
    "EMAIL":      r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "IP_ADDRESS": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "SSN":        r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD":r"\b(?:\d[ -]?){13,16}\b",
    "ACCOUNT_NUM":r"ACC-\d{6,}",
    "PHONE":      r"\b(\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
}


def redact_pii(text: str) -> tuple[str, list[str]]:
    """
    Scans text for PII and replaces with [TYPE REDACTED].

    Returns:
        clean_text  — text with PII removed
        found       — list of PII types that were found
    """
    found = []

    for label, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            found.append(label)
            text = re.sub(
                pattern,
                f"[{label} REDACTED]",
                text,
                flags=re.IGNORECASE
            )

    return text, found