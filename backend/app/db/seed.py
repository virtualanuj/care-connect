"""Idempotent seed data. Run with: uv run python -m app.db.seed"""

import sys
import uuid

from sqlalchemy.orm import Session

from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.config import get_settings
from app.db.session import get_session_factory
from app.domain.models import Role, User
from app.domain.ports import PasswordHasher
from app.services.user_service import validate_password


def seed_admin(session: Session, hasher: PasswordHasher, email: str, password: str) -> bool:
    """Create the initial front-desk admin if absent. Returns True if a user was created.

    An existing user is never modified (so re-running cannot reset a changed password).
    """
    validate_password(password)
    users = PostgresUserRepository(session)
    if users.get_by_email(email) is not None:
        return False
    users.add(
        User(
            id=uuid.uuid4(),
            email=email.strip().lower(),
            name="Front Desk Admin",
            role=Role.FRONT_DESK_ADMIN,
            password_hash=hasher.hash(password),
        )
    )
    return True


def main() -> int:
    settings = get_settings()
    if not settings.seed_admin_email or not settings.seed_admin_password:
        print("Set SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD to seed the admin user.")
        return 1
    with get_session_factory()() as session:
        created = seed_admin(
            session, Argon2PasswordHasher(), settings.seed_admin_email, settings.seed_admin_password
        )
        session.commit()
    print("Admin user created." if created else "Admin user already exists; nothing changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
