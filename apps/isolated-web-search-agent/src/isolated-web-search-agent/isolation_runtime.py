from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from isolation_contracts import normalize_research_task, validate_findings_payload


SAFE_ENV_KEYS = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TMP", "TEMP"}

# Non-secret configuration the worker needs to select and tune the web provider.
# These are intentionally forwarded through the otherwise-sanitized environment.
FORWARDED_ENV_KEYS = {
    "WEB_RESEARCH_MODE",
    "WEB_RESEARCH_HTTP_TIMEOUT_SECONDS",
    "WEB_RESEARCH_MAX_REDIRECTS",
    "WEB_RESEARCH_MAX_BYTES",
    "WEB_RESEARCH_USER_AGENT",
    # Network egress config for restricted environments (may carry proxy creds;
    # the operator opts in by setting them in the parent process).
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
}


def run_research_in_subprocess(task_payload: dict[str, Any], timeout_seconds: int = 30) -> dict[str, Any]:
    task = normalize_research_task(task_payload)
    worker = Path(__file__).with_name("web_subagent_worker.py")
    env = _sanitized_environment()
    for key, value in os.environ.items():
        if value and key.upper() in FORWARDED_ENV_KEYS:
            env[key] = value
    env.setdefault("WEB_RESEARCH_MODE", os.getenv("WEB_RESEARCH_MODE", "mock"))
    result = subprocess.run(
        [sys.executable, str(worker)],
        input=json.dumps(task.to_wire()),
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        return {
            "status": "error",
            "errorCode": "subagent_process_failed",
            "claims": [],
            "citations": [],
            "guardrails": {"rawWebContentReturned": False, "privilegedToolsAvailable": False},
        }
    payload = json.loads(result.stdout)
    return validate_findings_payload(payload, max_chars=task.budget.max_findings_chars)


def _sanitized_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key.upper() in SAFE_ENV_KEYS}