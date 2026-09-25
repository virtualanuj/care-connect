class FakePasswordHasher:
    """Fast, reversible stand-in for Argon2 (tests only)."""

    def hash(self, password: str) -> str:
        return f"hashed::{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed::{password}"
