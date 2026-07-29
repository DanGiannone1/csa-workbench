"""Optional Azure Monitor tracing for the orchestrator API.

Activates only when APPLICATIONINSIGHTS_CONNECTION_STRING is set (the deployed
Container App provides it; local development normally leaves it unset) and never
raises into startup. The session runtime has its own equivalent shim in
session-container/tracing.py.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI

logger = logging.getLogger(__name__)

_enabled = False


def setup_tracing(app: FastAPI) -> None:
    """Initialize Azure Monitor tracing and FastAPI instrumentation if configured."""
    global _enabled

    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not conn_str:
        logger.debug("Tracing: No connection string found, tracing disabled.")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource

        resource_attrs = {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "csa-workbench-api"),
            "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "csa-workbench"),
        }
        configure_azure_monitor(
            connection_string=conn_str,
            resource=Resource.create(resource_attrs),
            disable_logging=True,
            disable_metrics=True,
            enable_live_metrics=False,
            instrumentation_options={"fastapi": {"enabled": False}},
        )
        FastAPIInstrumentor.instrument_app(app)
        _enabled = True
        logger.info("Tracing enabled: service=%s", resource_attrs["service.name"])

    except ImportError:
        logger.warning(
            "Tracing: APPLICATIONINSIGHTS_CONNECTION_STRING is set but OTel packages are missing."
        )
    except Exception:
        logger.exception("Tracing: Failed to initialize OpenTelemetry.")


def is_enabled() -> bool:
    """Return True if tracing is active."""
    return _enabled
