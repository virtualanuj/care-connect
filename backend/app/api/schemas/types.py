from typing import Annotated

from pydantic import StringConstraints

# Deliberately lenient: one "@", no spaces, a dot in the domain. Real validation is sending mail.
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
