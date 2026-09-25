import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.postgres.models import UserRow
from app.domain.errors import UserAlreadyExists
from app.domain.models import Page, User


def _to_domain(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        role=row.role,
        password_hash=row.password_hash,
        active=row.active,
    )


class PostgresUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> None:
        row = UserRow(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            password_hash=user.password_hash,
            active=user.active,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as error:
            if "users_email_lower_key" in str(error.orig):
                raise UserAlreadyExists("A user with this email already exists") from error
            raise

    def get(self, user_id: uuid.UUID) -> User | None:
        row = self._session.get(UserRow, user_id)
        return _to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        row = self._session.scalars(
            select(UserRow).where(func.lower(UserRow.email) == email.lower())
        ).first()
        return _to_domain(row) if row else None

    def list(self, page: int, page_size: int) -> Page[User]:
        total = self._session.scalar(select(func.count()).select_from(UserRow)) or 0
        rows = self._session.scalars(
            select(UserRow)
            .order_by(func.lower(UserRow.email))
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return Page(items=[_to_domain(r) for r in rows], total=total)

    def update(self, user: User) -> None:
        row = self._session.get(UserRow, user.id)
        if row is None:
            return
        row.name = user.name
        row.role = user.role
        row.password_hash = user.password_hash
        row.active = user.active
        self._session.flush()
