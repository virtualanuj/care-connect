"""Patient identity: (E.164 phone, normalized name). Pure functions, no I/O."""

import re
import unicodedata

import phonenumbers

from app.domain.errors import ValidationFailed

_WHITESPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """NFKC, trim, collapse internal whitespace, case-fold."""
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFKC", name).strip()).casefold()


def normalize_phone(raw: str, default_region: str) -> str:
    """Return the E.164 form of `raw`, or raise ValidationFailed if it is not a valid number."""
    try:
        parsed = phonenumbers.parse(raw.strip(), default_region)
    except phonenumbers.NumberParseException as error:
        raise ValidationFailed("Enter a valid phone number") from error
    if not phonenumbers.is_valid_number(parsed):
        raise ValidationFailed("Enter a valid phone number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
