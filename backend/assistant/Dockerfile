FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/api/pyproject.toml backend/api/pyproject.toml
COPY backend/assistant/pyproject.toml backend/assistant/pyproject.toml
COPY backend/core/pyproject.toml backend/core/pyproject.toml
COPY backend/assistant/src/ backend/assistant/src/
COPY backend/assistant/product-skills/ backend/assistant/product-skills/
COPY backend/core/src/ backend/core/src/
RUN uv sync --frozen --package workbench-assistant --extra tracing --no-dev

RUN addgroup --system --gid 10001 app && \
    adduser --system --uid 10001 --ingroup app --home /app app && \
    mkdir -p /workspace && chown -R 10001:10001 /app /workspace

ENV WORKSPACE=/workspace
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

USER 10001:10001

CMD ["uvicorn", "workbench_assistant.server:app", "--host", "0.0.0.0", "--port", "8080"]
