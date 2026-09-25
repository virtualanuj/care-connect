from sqlalchemy.exc import IntegrityError


def violates(error: IntegrityError, constraint: str) -> bool:
    """True if the database error was caused by the named constraint or index."""
    return constraint in str(error.orig)
