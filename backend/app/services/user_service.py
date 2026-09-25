import uuid
from collections.abc import Callable

from app.domain.errors import Forbidden, NotFound, ValidationFailed
from app.domain.models import AuditAction, Page, Role, User
from app.domain.ports import PasswordHasher, UserRepository
from app.services.audit_service import AuditService

MIN_PASSWORD_LENGTH = 12


def require_front_desk(actor: User) -> None:
    if actor.role != Role.FRONT_DESK_ADMIN:
        raise Forbidden("Only front-desk staff can manage users")


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationFailed(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")


class UserService:
    def __init__(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        audit: AuditService,
        new_id: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._audit = audit
        self._new_id = new_id

    def create(self, actor: User, email: str, name: str, role: Role, password: str) -> User:
        require_front_desk(actor)
        validate_password(password)
        user = User(
            id=self._new_id(),
            email=email.strip().lower(),
            name=name.strip(),
            role=role,
            password_hash=self._hasher.hash(password),
        )
        self._users.add(user)
        self._audit.record(
            AuditAction.USER_CREATED, actor.id, "user", user.id, f"role={role.value}"
        )
        return user

    def list(self, actor: User, page: int, page_size: int) -> Page[User]:
        require_front_desk(actor)
        return self._users.list(page, page_size)

    def update(
        self,
        actor: User,
        user_id: uuid.UUID,
        name: str | None = None,
        role: Role | None = None,
        active: bool | None = None,
    ) -> User:
        require_front_desk(actor)
        user = self._users.get(user_id)
        if user is None:
            raise NotFound("User not found")

        changes: list[str] = []
        if name is not None and name.strip() != user.name:
            changes.append("name changed")
            user.name = name.strip()
        if role is not None and role != user.role:
            if user_id == actor.id:
                raise ValidationFailed("You cannot change your own role")
            changes.append(f"role: {user.role.value} -> {role.value}")
            user.role = role
        if active is not None and active != user.active:
            if user_id == actor.id and not active:
                raise ValidationFailed("You cannot deactivate your own account")
            changes.append(f"active: {user.active} -> {active}")
            user.active = active

        if changes:
            self._users.update(user)
            self._audit.record(
                AuditAction.USER_UPDATED, actor.id, "user", user.id, "; ".join(changes)
            )
        return user

    def reset_password(self, actor: User, user_id: uuid.UUID, new_password: str) -> None:
        require_front_desk(actor)
        validate_password(new_password)
        user = self._users.get(user_id)
        if user is None:
            raise NotFound("User not found")
        user.password_hash = self._hasher.hash(new_password)
        self._users.update(user)
        self._audit.record(AuditAction.PASSWORD_RESET, actor.id, "user", user.id)
