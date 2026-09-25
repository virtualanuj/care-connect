from app.api.schemas.base import CamelModel
from app.api.schemas.types import Email
from app.domain.models import Role


class LoginRequest(CamelModel):
    email: Email
    password: str


class TokenResponse(CamelModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: Role
