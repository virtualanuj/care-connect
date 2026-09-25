from fastapi import FastAPI

from app.api.routers import health


def create_app() -> FastAPI:
    app = FastAPI(title="CareConnect API", version="0.2.0", openapi_url="/api/v1/openapi.json")
    app.include_router(health.router)
    return app


app = create_app()
