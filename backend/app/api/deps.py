"""Dependency wiring: builds services per request and enforces authentication and roles."""

from collections.abc import Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.adapters.postgres.audit_repository import PostgresAuditRepository
from app.adapters.postgres.user_repository import PostgresUserRepository
from app.db.session import get_session
from app.domain.errors import Forbidden, Unauthenticated
from app.domain.models import Role, User
from app.domain.ports import Clock
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.user_service import UserService

_bearer = HTTPBearer(auto_error=False)


def get_clock(request: Request) -> Clock:
    clock: Clock = request.app.state.clock
    return clock


def get_audit_service(
    session: Session = Depends(get_session), clock: Clock = Depends(get_clock)
) -> AuditService:
    return AuditService(PostgresAuditRepository(session), clock)


def get_user_service(
    request: Request,
    session: Session = Depends(get_session),
    audit: AuditService = Depends(get_audit_service),
) -> UserService:
    return UserService(PostgresUserRepository(session), request.app.state.hasher, audit)


def get_auth_service(
    request: Request,
    session: Session = Depends(get_session),
    clock: Clock = Depends(get_clock),
) -> AuthService:
    state = request.app.state
    return AuthService(
        PostgresUserRepository(session),
        state.hasher,
        state.tokens,
        clock,
        state.limiter,
        ttl_seconds=state.token_ttl_seconds,
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    """Resolve the bearer token to the current *active* user, loaded from the database."""
    if credentials is None:
        raise Unauthenticated("Authentication required")
    return auth.authenticate(credentials.credentials)


def require_roles(*roles: Role) -> Callable[[User], User]:
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise Forbidden("Not permitted")
        return user

    return dependency


require_front_desk = require_roles(Role.FRONT_DESK_ADMIN)
