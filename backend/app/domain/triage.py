"""Triage constants shared by the service and the API."""

# Attached by the server to every stored result. It is never produced by a model.
TRIAGE_DISCLAIMER = (
    "This is an AI-generated suggestion to support clinical staff. It is not a diagnosis and "
    "does not replace professional judgment. In an emergency, call your local emergency number."
)

HISTORY_ENTRIES_FOR_CONTEXT = 10
MAX_SYMPTOMS_LENGTH = 4000
