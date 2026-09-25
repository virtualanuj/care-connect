"""Contract harness: validate real responses against docs/openapi.yaml (the source of truth)."""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openapi_core import OpenAPI
from openapi_core.testing import MockRequest, MockResponse

from app.main import create_app
from tests.no_network import block_network

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "openapi.yaml"
HOST = "http://testserver"

__all__ = ["block_network"]

ContractCheck = Callable[[httpx.Response], None]


@pytest.fixture(scope="session")
def openapi_spec() -> OpenAPI:
    return OpenAPI.from_file_path(str(SPEC_PATH))


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def assert_contract(openapi_spec: OpenAPI) -> ContractCheck:
    """Fail unless the response matches the documented schema for its operation."""

    def check(response: httpx.Response) -> None:
        request = response.request
        mock_request = MockRequest(
            HOST,
            request.method.lower(),
            request.url.path,
            args=dict(request.url.params),
            headers=dict(request.headers),
            data=request.content,
            content_type=request.headers.get("content-type", "application/json"),
        )
        mock_response = MockResponse(
            response.content,
            status_code=response.status_code,
            headers=dict(response.headers),
            content_type=response.headers.get("content-type", "application/json"),
        )
        openapi_spec.validate_response(mock_request, mock_response)

    return check
