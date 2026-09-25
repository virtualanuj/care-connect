"""Deterministic red-flag check for clearly emergent presentations (docs/standards.md, AI usage).

This runs *before* any AI call and can independently force urgency = emergency, so an AI
outage or a misled model can never be the only thing standing between a patient and a missed
emergency. It may only ever raise urgency.

Design bias: a false alarm costs staff a moment; a missed emergency can cost a life. So the
matcher errs towards flagging. Changes to this list are reviewed like code (docs/review.md) and
must be signed off by the clinical lead; bump RED_FLAG_LIST_VERSION when they change.
"""

import re

RED_FLAG_LIST_VERSION = "2026-09-25.1"

RED_FLAG_PHRASES: tuple[str, ...] = (
    # cardiac / respiratory
    "chest pain",
    "chest tightness",
    "chest pressure",
    "pressure in my chest",
    "pressure in the chest",
    "difficulty breathing",
    "trouble breathing",
    "shortness of breath",
    "struggling to breathe",
    "cant breathe",
    "cannot breathe",
    "can not breathe",
    "not breathing",
    # consciousness
    "unconscious",
    "unresponsive",
    "collapsed",
    "passed out",
    # bleeding
    "severe bleeding",
    "heavy bleeding",
    "bleeding heavily",
    "coughing up blood",
    "coughing blood",
    "vomiting blood",
    # stroke
    "stroke",
    "face drooping",
    "facial droop",
    "slurred speech",
    "sudden weakness",
    "sudden numbness",
    "sudden confusion",
    # neurological
    "seizure",
    "seizures",
    "convulsion",
    "convulsions",
    # allergy
    "anaphylaxis",
    "anaphylactic",
    "throat swelling",
    "swollen throat",
    "severe allergic reaction",
    # mental health / toxic
    "suicidal",
    "suicide",
    "want to die",
    "kill myself",
    "overdose",
    "poisoning",
    "poisoned",
)

_NEGATIONS = frozenset({"no", "not", "denies", "denied", "without", "never", "negative"})
# How many words before a phrase a negation may sit ("no chest pain", "without any chest pain").
_NEGATION_WINDOW = 2
_CLAUSE_BREAK = re.compile(r"[.;,:!?()\n]|\b(?:but|however|although|though|yet)\b")


def _tokens(text: str) -> list[str]:
    return re.findall(
        r"[a-z0-9]+", text.replace("'", "").replace("’", "").replace("-", " ").lower()
    )


def _clauses(text: str) -> list[list[str]]:
    lowered = text.lower().replace("'", "").replace("’", "")
    return [t for part in _CLAUSE_BREAK.split(lowered) if (t := _tokens(part))]


_PHRASE_TOKENS = tuple((phrase, _tokens(phrase)) for phrase in RED_FLAG_PHRASES)


def match_red_flags(text: str) -> list[str]:
    """The red-flag phrases present in `text` and not directly negated, without duplicates."""
    found: list[str] = []
    for tokens in _clauses(text):
        for phrase, words in _PHRASE_TOKENS:
            size = len(words)
            for start in range(len(tokens) - size + 1):
                if tokens[start : start + size] != words:
                    continue
                before = tokens[max(0, start - _NEGATION_WINDOW) : start]
                if any(word in _NEGATIONS for word in before):
                    continue
                if phrase not in found:
                    found.append(phrase)
    return found
