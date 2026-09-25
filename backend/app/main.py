import secrets

from fastapi import FastAPI

from app.adapters.ai.factory import build_llm_provider
from app.adapters.argon2_hasher import Argon2PasswordHasher
from app.adapters.clock import SystemClock
from app.adapters.jwt_codec import JwtTokenCodec
from app.adapters.rate_limiter import InMemoryRateLimiter
from app.api.errors import register_error_handlers
from app.api.routers import (
    appointments,
    audit,
    auth,
    availability,
    clinic_settings,
    doctors,
    health,
    patients,
    queue,
    slots,
    specialties,
    triage,
    users,
    visit_notes,
)
from app.config import Settings, get_settings
from app.domain.ports import Clock, LLMProvider

API_PREFIX = "/api/v1"  # matches `servers` in docs/openapi.yaml
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_MINUTES = 15


def create_app(
    settings: Settings | None = None,
    clock: Clock | None = None,
    llm: LLMProvider | None = None,
) -> FastAPI:
    from datetime import timedelta

    settings = settings or get_settings()
    clock = clock or SystemClock()

    app = FastAPI(
        title="CareConnect API", version="0.2.0", openapi_url=f"{API_PREFIX}/openapi.json"
    )
    app.state.clock = clock
    app.state.hasher = Argon2PasswordHasher()
    app.state.llm = llm or build_llm_provider(settings)
    # In dev without JWT_SECRET, use a per-process secret (tokens die on restart).
    app.state.tokens = JwtTokenCodec(settings.jwt_secret or secrets.token_urlsafe(48))
    app.state.default_phone_region = settings.default_phone_region
    app.state.token_ttl_seconds = settings.jwt_ttl_minutes * 60
    app.state.limiter = InMemoryRateLimiter(
        clock, max_failures=LOGIN_MAX_FAILURES, window=timedelta(minutes=LOGIN_WINDOW_MINUTES)
    )

    register_error_handlers(app)
    routers = (
        health.router,
        auth.router,
        users.router,
        audit.router,
        clinic_settings.router,
        specialties.router,
        doctors.router,
        availability.router,
        patients.router,
        slots.router,
        appointments.router,
        queue.router,
        triage.router,
        visit_notes.router,
    )
    for router in routers:
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
