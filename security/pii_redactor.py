"""
PII Redaction module — Phase 4 upgrade.
Uses Microsoft Presidio with spaCy NER model (en_core_web_lg) instead of regex.
Catches named entities like 'John Smith at Acme Corp' that regex misses entirely.
"""

import logging
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from state.schema import IncidentState

logger = logging.getLogger(__name__)

# Initialize once at module level — these are expensive to construct
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Entities Presidio will detect and redact
ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "US_SSN",
    "LOCATION",
    "URL",
]

# Replace each entity type with a readable placeholder
OPERATORS = {
    entity: OperatorConfig("replace", {"new_value": f"[{entity}]"})
    for entity in ENTITIES
}


def redact_pii(text: str) -> dict:
    """
    Analyzes text for PII using Presidio's NER engine.
    Returns redacted text, detected entity types, and a summary.
    """
    results = analyzer.analyze(text=text, entities=ENTITIES, language="en")

    if not results:
        return {
            "redacted_text": text,
            "pii_detected": False,
            "pii_types": [],
            "redaction_summary": "No PII detected.",
        }

    anonymized = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=OPERATORS,
    )

    detected_types = list({r.entity_type for r in results})
    logger.info(f"[pii_redactor] Detected and redacted: {detected_types}")

    return {
        "redacted_text": anonymized.text,
        "pii_detected": True,
        "pii_types": detected_types,
        "redaction_summary": f"Redacted {len(results)} item(s): {', '.join(detected_types)}",
    }


def pii_redactor(state: IncidentState) -> dict:
    """
    LangGraph node — redacts PII from the alert before any LLM call.
    Writes redacted text to clean_alert in state.
    """
    result = redact_pii(state["alert"])

    return {
        "clean_alert": result["redacted_text"],
        "pii_detected": result["pii_detected"],
        "pii_types": result["pii_types"],
        "redaction_summary": result["redaction_summary"],
    }