from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok_without_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_returns_error_envelope_for_unknown_routes() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json() == {"code": "NOT_FOUND", "message": "Resource not found"}
