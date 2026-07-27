from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mise_validation import (
    MiseTokenValidator,
    MiseValidationConfig,
    TokenRejected,
    ValidationUnavailable,
)


def _validator(handler) -> MiseTokenValidator:
    return MiseTokenValidator(
        MiseValidationConfig("http://127.0.0.1:8081/Validate"),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.parametrize("endpoint", [
    "", "https://127.0.0.1:8081/Validate", "http://sidecar:8081/Validate",
    "http://127.0.0.1:8081/healthz", "http://user@127.0.0.1:8081/Validate",
    "http://127.0.0.1:8081/Validate?forward=true", "http://127.0.0.1/Validate",
])
def test_sidecar_endpoint_must_be_explicit_loopback_http(endpoint: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        MiseValidationConfig(endpoint).validate()


def test_sidecar_returns_only_claims_from_matching_validation_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer token"
        return httpx.Response(200, json={
            "protocol": "Bearer", "token": "token",
            "claims": {"tid": "tenant", "aud": "api", "scp": "access_as_user"},
        })

    validator = _validator(handler)
    claims = asyncio.run(validator.verify("token"))
    asyncio.run(validator.close())
    assert claims == {"tid": "tenant", "aud": "api", "scp": "access_as_user"}


@pytest.mark.parametrize("status", [400, 401, 403])
def test_sidecar_token_rejections_are_authentication_failures(status: int) -> None:
    validator = _validator(lambda _request: httpx.Response(status))
    with pytest.raises(TokenRejected):
        asyncio.run(validator.verify("bad-token"))
    asyncio.run(validator.close())


@pytest.mark.parametrize("response", [
    httpx.Response(500),
    httpx.Response(200, text="not-json"),
    httpx.Response(200, json={"protocol": "Bearer", "token": "different", "claims": {}}),
    httpx.Response(200, json={"protocol": "Bearer", "token": "token", "claims": {}}),
    httpx.Response(200, json={"protocol": "Bearer", "token": "token", "claims": []}),
])
def test_sidecar_untrustworthy_responses_fail_closed_as_unavailable(response: httpx.Response) -> None:
    validator = _validator(lambda _request: response)
    with pytest.raises(ValidationUnavailable):
        asyncio.run(validator.verify("token"))
    asyncio.run(validator.close())


def test_sidecar_network_failure_fails_closed_without_proxy_fallback() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unavailable", request=request)

    validator = _validator(handler)
    with pytest.raises(ValidationUnavailable):
        asyncio.run(validator.verify("token"))
    asyncio.run(validator.close())
