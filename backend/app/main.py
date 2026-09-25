from fastapi import FastAPI

from app.api.errors import register_error_handlers
from app.api.routers import health

API_PREFIX = "/api/v1"  # matches `servers` in docs/openapi.yaml


def create_app() -> FastAPI:
    app = FastAPI(
        title="CareConnect API", version="0.2.0", openapi_url=f"{API_PREFIX}/openapi.json"
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
