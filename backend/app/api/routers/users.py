import uuid

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import get_user_service, require_front_desk
from app.api.schemas.users import (
    ResetPasswordRequest,
    UserCreate,
    UserOut,
    UserPage,
    UserUpdate,
)
from app.domain.models import User
from app.services.user_service import UserService

router = APIRouter(tags=["Users"])


@router.get("/users", response_model=UserPage)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    actor: User = Depends(require_front_desk),
    service: UserService = Depends(get_user_service),
) -> UserPage:
    return UserPage.from_domain(service.list(actor, page, page_size), page, page_size)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    actor: User = Depends(require_front_desk),
    service: UserService = Depends(get_user_service),
) -> UserOut:
    user = service.create(actor, body.email, body.name, body.role, body.password)
    return UserOut.from_domain(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    actor: User = Depends(require_front_desk),
    service: UserService = Depends(get_user_service),
) -> UserOut:
    user = service.update(actor, user_id, name=body.name, role=body.role, active=body.active)
    return UserOut.from_domain(user)


@router.post("/users/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    actor: User = Depends(require_front_desk),
    service: UserService = Depends(get_user_service),
) -> Response:
    service.reset_password(actor, user_id, body.new_password)
    return Response(status_code=204)
