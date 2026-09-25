import uuid

from app.domain.errors import UserAlreadyExists
from app.domain.models import AuditAction, AuditEntry, Page, User


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}

    def add(self, user: User) -> None:
        if self.get_by_email(user.email) is not None:
            raise UserAlreadyExists("A user with this email already exists")
        self.users[user.id] = user

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def list(self, page: int, page_size: int) -> Page[User]:
        ordered = sorted(self.users.values(), key=lambda u: u.email.lower())
        start = (page - 1) * page_size
        return Page(items=ordered[start : start + page_size], total=len(ordered))

    def update(self, user: User) -> None:
        self.users[user.id] = user


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []

    def add(self, entry: AuditEntry) -> None:
        self.entries.append(entry)

    def list(self, action: AuditAction | None, page: int, page_size: int) -> Page[AuditEntry]:
        matching = [e for e in self.entries if action is None or e.action == action]
        matching.sort(key=lambda e: e.created_at, reverse=True)
        start = (page - 1) * page_size
        return Page(items=matching[start : start + page_size], total=len(matching))
