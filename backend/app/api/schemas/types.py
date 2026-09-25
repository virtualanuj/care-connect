from datetime import time
from typing import Annotated, Any

from pydantic import BeforeValidator, PlainSerializer, StringConstraints

# Deliberately lenient: one "@", no spaces, a dot in the domain. Real validation is sending mail.
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


def _parse_clock_time(value: Any) -> Any:
    """Accept only strict 'HH:MM' strings (clinic-local wall time)."""
    if isinstance(value, time):
        return value
    if isinstance(value, str) and len(value) == 5 and value[2] == ":":
        return time.fromisoformat(value)  # raises ValueError -> 400
    raise ValueError("Time must be HH:MM")


ClockTime = Annotated[
    time,
    BeforeValidator(_parse_clock_time),
    PlainSerializer(lambda value: value.strftime("%H:%M"), return_type=str),
]
