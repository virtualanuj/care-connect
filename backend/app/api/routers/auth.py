from fastapi import APIRouter, Depends, Request

from app.api.deps import current_user, get_auth_service
from app.api.schemas.auth import LoginRequest, TokenResponse
from app.api.schemas.users import UserOut
from app.domain.models import User
from app.services.auth_service import AuthService

router = APIRouter(tags=["Auth"])


@router.post("/auth/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, auth: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    client_id = request.client.host if request.client else "unknown"
    result = auth.login(body.email, body.password, client_id)
    return TokenResponse(access_token=result.token, expires_in=result.expires_in, role=result.role)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> UserOut:
    return UserOut.from_domain(user)
