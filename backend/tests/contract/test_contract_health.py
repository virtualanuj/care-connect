import httpx
import pytest
from fastapi.testclient import TestClient
from openapi_core.validation.response.exceptions import ResponseValidationError

from tests.contract.conftest import ContractCheck


def test_health_response_matches_openapi(
    client: TestClient, assert_contract: ContractCheck
) -> None:
    assert_contract(client.get("/api/v1/health"))


def test_contract_check_fails_when_a_response_field_is_missing(
    client: TestClient, assert_contract: ContractCheck
) -> None:
    real = client.get("/api/v1/health")
    drifted = httpx.Response(200, json={"state": "ok"}, request=real.request)

    with pytest.raises(ResponseValidationError):
        assert_contract(drifted)


def test_contract_check_fails_when_a_field_has_the_wrong_type(
    client: TestClient, assert_contract: ContractCheck
) -> None:
    real = client.get("/api/v1/health")
    drifted = httpx.Response(200, json={"status": 123}, request=real.request)

    with pytest.raises(ResponseValidationError):
        assert_contract(drifted)
