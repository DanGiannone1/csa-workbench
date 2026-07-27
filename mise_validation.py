"""Client for the local Microsoft Entra authentication sidecar.

The sidecar is the authoritative token validator and emits the Microsoft
Identity Web key-discovery telemetry required by S360.  Application code keeps
the product-specific authorization checks after validation succeeds.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx


class TokenRejected(Exception):
    """The sidecar or an application authorization check rejected a token."""


class ValidationUnavailable(Exception):
    """The local validation service could not produce a trustworthy result."""


@dataclass(frozen=True, slots=True)
class MiseValidationConfig:
    endpoint: str
    timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "MiseValidationConfig":
        return cls(endpoint=(os.getenv("MISE_VALIDATION_ENDPOINT") or "").strip())

    def validate(self) -> None:
        parsed = urlsplit(self.endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.port is None
            or parsed.path != "/Validate"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "MISE_VALIDATION_ENDPOINT must be an explicit loopback HTTP URL ending in /Validate"
            )
        if not 0 < self.timeout_seconds <= 30:
            raise ValueError("MISE validation timeout must be greater than zero and at most 30 seconds")


class MiseTokenValidator:
    """Forward a bearer token only to the loopback Microsoft validation sidecar."""

    _MAX_RESPONSE_BYTES = 128 * 1024

    def __init__(
        self,
        config: MiseValidationConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        config.validate()
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=config.timeout_seconds,
            transport=transport,
            trust_env=False,
        )

    async def verify(self, token: str) -> dict[str, Any]:
        if not token:
            raise TokenRejected("Empty bearer token")
        try:
            response = await self._client.get(
                self.config.endpoint,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise ValidationUnavailable("Microsoft token validation sidecar is unavailable") from exc

        if response.status_code in {400, 401, 403}:
            raise TokenRejected("Bearer token rejected by Microsoft token validation")
        if response.status_code != 200:
            raise ValidationUnavailable(
                f"Microsoft token validation sidecar returned status {response.status_code}"
            )
        if len(response.content) > self._MAX_RESPONSE_BYTES:
            raise ValidationUnavailable("Microsoft token validation response exceeded the size limit")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ValidationUnavailable("Microsoft token validation response was not JSON") from exc
        if not isinstance(payload, dict):
            raise ValidationUnavailable("Microsoft token validation response was malformed")
        if payload.get("protocol") != "Bearer" or payload.get("token") != token:
            raise ValidationUnavailable("Microsoft token validation response did not match the request")
        claims = payload.get("claims")
        if not isinstance(claims, dict) or not claims or not all(isinstance(name, str) for name in claims):
            raise ValidationUnavailable("Microsoft token validation response omitted trusted claims")
        return claims

    async def close(self) -> None:
        await self._client.aclose()
