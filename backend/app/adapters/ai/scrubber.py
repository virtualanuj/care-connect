"""Best-effort removal of direct identifiers from free text before it reaches an AI provider.

Free text is where identifiers hide ("my wife Priya, 555-0102"), so this works on the text, not
just on structured fields. It replaces the patient's *known* identifiers wherever they appear
and also removes phone numbers, emails, and full dates in general. It cannot recognise an
arbitrary unknown person's name; that limitation is documented in docs/spec.md §5.1.
"""

import re
from re import Match

from app.domain.models import PatientIdentifiers

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATES = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"),
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\.?,?\s+\d{{4}}\b", re.IGNORECASE),
    re.compile(rf"\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),
)

# A run of digits with the usual separators; kept only if it holds at least 7 digits.
_PHONE = re.compile(r"(?<![\w.])\+?\(?\d[\d\s().\-]{5,}\d(?!\w)")
_MIN_PHONE_DIGITS = 7
_MIN_NAME_PART = 3

_RELATIVE = re.compile(
    r"\b((?i:my|his|her|their)\s+(?i:wife|husband|son|daughter|mother|father|brother|sister|"
    r"friend|neighbou?r|partner|aunt|uncle|grandmother|grandfather))\s+"
    r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
)


def _phone(match: Match[str]) -> str:
    digits = sum(ch.isdigit() for ch in match.group())
    return "[PHONE]" if digits >= _MIN_PHONE_DIGITS else match.group()


def scrub(text: str, identifiers: PatientIdentifiers) -> str:
    """Replace identifiers with placeholders ([NAME], [PHONE], [EMAIL], [DATE]). Idempotent."""
    out = _EMAIL.sub("[EMAIL]", text)
    for pattern in _DATES:
        out = pattern.sub("[DATE]", out)
    out = _PHONE.sub(_phone, out)

    parts = [p for p in identifiers.name.split() if p]
    if len(parts) > 1:
        full = r"\s+".join(re.escape(p) for p in parts)
        out = re.sub(rf"\b{full}\b", "[NAME]", out, flags=re.IGNORECASE)
    for part in parts:
        if len(part) >= _MIN_NAME_PART:
            out = re.sub(rf"\b{re.escape(part)}\b", "[NAME]", out, flags=re.IGNORECASE)

    return _RELATIVE.sub(r"\1 [NAME]", out)
