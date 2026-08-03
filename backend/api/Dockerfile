FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/api/pyproject.toml backend/api/pyproject.toml
COPY backend/assistant/pyproject.toml backend/assistant/pyproject.toml
COPY backend/core/pyproject.toml backend/core/pyproject.toml
COPY backend/api/src/ backend/api/src/
COPY backend/core/src/ backend/core/src/
RUN uv sync --frozen --package workbench-api --extra tracing

ENV PATH="/app/.venv/bin:$PATH"

RUN adduser --disabled-password --gecos "" --uid 1000 appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "workbench_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
